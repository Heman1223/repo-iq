"""Indexing orchestrator.

Owns the end-to-end pipeline

    validate -> clone -> read files -> chunk -> embed -> store -> finalize

and the in-memory job registry that ``GET /status`` polls. Each stage publishes
progress so the frontend loading screen mirrors what the server is really doing.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime

from app.core.config import settings
from app.core.exceptions import (
    AppError,
    EmptyRepositoryError,
    IndexingInProgress,
    RepositoryNotIndexed,
)
from app.models.schemas import (
    IndexedRepositorySummary,
    IndexStage,
    IndexStats,
    IndexStatus,
    RepositoryMetadata,
)
from app.services.chunking_service import chunking_service
from app.services.embedding_service import embedding_service
from app.services.file_service import file_service
from app.services.git_service import git_service
from app.services.github_service import github_service
from app.services.index_cache import IndexRecord, index_cache
from app.services.vector_store import vector_store
from app.utils.repo_url import RepoRef, parse_github_url

logger = logging.getLogger(__name__)

# Human-readable copy for each stage, surfaced directly in the loading screen.
STAGE_MESSAGES: dict[IndexStage, str] = {
    IndexStage.QUEUED: "Queued",
    IndexStage.VALIDATING: "Validating repository",
    IndexStage.CLONING: "Cloning repository",
    IndexStage.READING_FILES: "Reading repository files",
    IndexStage.CHUNKING: "Splitting files into chunks",
    IndexStage.EMBEDDING: "Generating embeddings",
    IndexStage.STORING: "Creating vector database",
    IndexStage.FINALIZING: "Almost ready",
    IndexStage.READY: "Repository indexed",
    IndexStage.FAILED: "Indexing failed",
}

# Fraction of the progress bar allotted to each stage boundary.
_STAGE_PROGRESS: dict[IndexStage, float] = {
    IndexStage.QUEUED: 0.01,
    IndexStage.VALIDATING: 0.05,
    IndexStage.CLONING: 0.20,
    IndexStage.READING_FILES: 0.35,
    IndexStage.CHUNKING: 0.45,
    IndexStage.EMBEDDING: 0.50,  # grows to 0.88 while batches are encoded
    IndexStage.STORING: 0.90,
    IndexStage.FINALIZING: 0.96,
    IndexStage.READY: 1.0,
    IndexStage.FAILED: 1.0,
}

_EMBED_PROGRESS_START = 0.50
_EMBED_PROGRESS_END = 0.88


@dataclass(slots=True)
class IndexJob:
    """Mutable progress record for one repository indexing run."""

    repo: RepoRef
    stage: IndexStage = IndexStage.QUEUED
    progress: float = 0.01
    message: str = STAGE_MESSAGES[IndexStage.QUEUED]
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None
    reused_existing_index: bool = False
    metadata: RepositoryMetadata | None = None
    stats: IndexStats | None = None

    @property
    def is_active(self) -> bool:
        return self.stage not in (IndexStage.READY, IndexStage.FAILED)

    def to_status(self) -> IndexStatus:
        return IndexStatus(
            repo_id=self.repo.repo_id,
            full_name=self.repo.full_name,
            html_url=self.repo.html_url,
            stage=self.stage,
            progress=round(self.progress, 4),
            message=self.message,
            is_ready=self.stage is IndexStage.READY,
            error_code=self.error_code,
            error_message=self.error_message,
            started_at=self.started_at,
            completed_at=self.completed_at,
            reused_existing_index=self.reused_existing_index,
            metadata=self.metadata,
            stats=self.stats,
        )


class IndexingService:
    """Coordinates the RAG ingestion pipeline and tracks job progress."""

    def __init__(self) -> None:
        self._jobs: dict[str, IndexJob] = {}
        self._lock = threading.RLock()

    # -- job registry --------------------------------------------------------

    def _get_job(self, repo_id: str) -> IndexJob | None:
        with self._lock:
            return self._jobs.get(repo_id)

    def _set_stage(
        self,
        repo_id: str,
        stage: IndexStage,
        *,
        message: str | None = None,
        progress: float | None = None,
    ) -> None:
        with self._lock:
            job = self._jobs.get(repo_id)
            if job is None:
                return
            job.stage = stage
            job.message = message or STAGE_MESSAGES[stage]
            job.progress = _STAGE_PROGRESS[stage] if progress is None else progress
        logger.info("[%s] %s (%.0f%%)", repo_id, message or STAGE_MESSAGES[stage],
                    (progress if progress is not None else _STAGE_PROGRESS[stage]) * 100)

    # -- public API ----------------------------------------------------------

    def prepare(self, repo_url: str, *, force: bool = False) -> tuple[RepoRef, IndexStatus, bool]:
        """Validate a URL and decide whether work is actually required.

        Returns:
            ``(repo, status, needs_indexing)``. When ``needs_indexing`` is False the
            returned status is already terminal — either a reusable existing index or
            a run that is still in flight.
        """
        repo = parse_github_url(repo_url)
        repo_id = repo.repo_id

        with self._lock:
            existing_job = self._jobs.get(repo_id)
            if existing_job is not None and existing_job.is_active:
                # Idempotent: a duplicate submit just re-attaches to the live job.
                return repo, existing_job.to_status(), False

            if not force:
                record = index_cache.get(repo_id)
                if record is not None and vector_store.count(record.collection_name) > 0:
                    logger.info("Reusing existing index for %s", repo.full_name)
                    job = IndexJob(
                        repo=repo,
                        stage=IndexStage.READY,
                        progress=1.0,
                        message="Loaded from existing index",
                        completed_at=record.indexed_at,
                        reused_existing_index=True,
                        metadata=record.metadata,
                        stats=record.stats,
                    )
                    self._jobs[repo_id] = job
                    return repo, job.to_status(), False

            job = IndexJob(repo=repo)
            self._jobs[repo_id] = job
            return repo, job.to_status(), True

    def run(self, repo: RepoRef, *, force: bool = False) -> None:
        """Execute the full pipeline. Safe to call from a background task."""
        repo_id = repo.repo_id
        started = time.perf_counter()

        try:
            self._execute(repo, force=force, started=started)
        except AppError as exc:
            self._fail(repo_id, exc.code, exc.message)
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Unexpected indexing failure for %s", repo.full_name)
            self._fail(repo_id, "internal_error", f"Unexpected indexing error: {exc}")

    def get_status(self, repo_id: str) -> IndexStatus:
        """Current status for ``repo_id``, rehydrating from cache if needed."""
        job = self._get_job(repo_id)
        if job is not None:
            return job.to_status()

        record = index_cache.get(repo_id)
        if record is None:
            raise RepositoryNotIndexed(
                "No index found for this repository. Index it first via POST /clone."
            )

        return IndexStatus(
            repo_id=record.repo_id,
            full_name=record.full_name,
            html_url=record.html_url,
            stage=IndexStage.READY,
            progress=1.0,
            message="Loaded from existing index",
            is_ready=True,
            started_at=record.indexed_at,
            completed_at=record.indexed_at,
            reused_existing_index=True,
            metadata=record.metadata,
            stats=record.stats,
        )

    def require_ready(self, repo_id: str) -> IndexRecord:
        """Return the index record, or explain why it is not usable yet."""
        record = index_cache.get(repo_id)
        if record is not None and vector_store.count(record.collection_name) > 0:
            return record

        job = self._get_job(repo_id)
        if job is not None and job.is_active:
            raise IndexingInProgress(
                f"'{job.repo.full_name}' is still being indexed ({job.message.lower()})."
            )
        if job is not None and job.stage is IndexStage.FAILED:
            raise RepositoryNotIndexed(
                job.error_message or "Indexing failed for this repository. Please re-index it."
            )
        raise RepositoryNotIndexed(
            "This repository has not been indexed yet. Submit it via POST /clone first."
        )

    def list_repositories(self) -> list[IndexedRepositorySummary]:
        return [
            IndexedRepositorySummary(
                repo_id=record.repo_id,
                full_name=record.full_name,
                html_url=record.html_url,
                stage=IndexStage.READY,
                indexed_at=record.indexed_at,
                total_chunks=record.stats.total_chunks,
            )
            for record in index_cache.all()
        ]

    def delete_index(self, repo_id: str) -> None:
        """Drop vectors, cache entry and any clone for ``repo_id``."""
        record = index_cache.get(repo_id)
        if record is None:
            raise RepositoryNotIndexed()
        vector_store.drop_collection(record.collection_name)
        index_cache.remove(repo_id)
        with self._lock:
            self._jobs.pop(repo_id, None)

    # -- pipeline ------------------------------------------------------------

    def _execute(self, repo: RepoRef, *, force: bool, started: float) -> None:
        repo_id = repo.repo_id

        # 1. Validate against the GitHub API (404/private fail fast here).
        self._set_stage(repo_id, IndexStage.VALIDATING)
        metadata = self._fetch_metadata(repo)
        with self._lock:
            if job := self._jobs.get(repo_id):
                job.metadata = metadata

        # 2. Clone (shallow, read-only).
        self._set_stage(repo_id, IndexStage.CLONING)
        clone = git_service.clone(repo, force=True)

        try:
            # 3. Read the indexable subset of files.
            self._set_stage(repo_id, IndexStage.READING_FILES)
            scan = file_service.scan_repository(clone.path)
            if not scan.files:
                raise EmptyRepositoryError(
                    "No readable source files were found. The repository may contain only "
                    "binaries, assets or ignored files."
                )
            tree_outline = file_service.build_tree_outline(clone.path, scan.files)
            top_level = file_service.top_level_entries(clone.path)
            self._set_stage(
                repo_id,
                IndexStage.READING_FILES,
                message=f"Read {len(scan.files)} files",
            )

            # 4. Chunk with overlap.
            self._set_stage(repo_id, IndexStage.CHUNKING)
            chunking = chunking_service.chunk_files(scan.files)
            if not chunking.chunks:
                raise EmptyRepositoryError("The repository produced no indexable text chunks.")

            # 5. Embed locally, streaming progress into the job.
            self._set_stage(
                repo_id,
                IndexStage.EMBEDDING,
                message=f"Generating embeddings for {len(chunking.chunks)} chunks",
            )
            vectors = embedding_service.embed_documents(
                [chunk.text for chunk in chunking.chunks],
                on_progress=lambda done, total: self._report_embedding_progress(
                    repo_id, done, total
                ),
            )

            # 6. Persist to Chroma (always from a clean collection).
            self._set_stage(repo_id, IndexStage.STORING)
            collection_name = repo.collection_name
            vector_store.drop_collection(collection_name)
            vector_store.add_documents(
                collection_name=collection_name,
                ids=[chunk.chunk_id for chunk in chunking.chunks],
                documents=[chunk.text for chunk in chunking.chunks],
                embeddings=vectors,
                metadatas=[
                    chunk.to_metadata(repo_id, repo.full_name) for chunk in chunking.chunks
                ],
            )

            # 7. Record the result and release the working copy.
            self._set_stage(repo_id, IndexStage.FINALIZING)
            elapsed = time.perf_counter() - started
            stats = IndexStats(
                total_files_scanned=scan.scanned,
                total_files_indexed=len(scan.files),
                total_files_skipped=scan.skipped,
                total_chunks=len(chunking.chunks),
                total_characters=scan.total_characters,
                embedding_model=embedding_service.model_name,
                embedding_dimensions=len(vectors[0]) if vectors else 0,
                vector_count=vector_store.count(collection_name),
                languages=scan.languages,
                top_level_entries=top_level,
                indexing_seconds=round(elapsed, 2),
                indexed_at=datetime.now(),
            )
            metadata = metadata.model_copy(update={"default_branch": clone.default_branch})
            index_cache.put(
                IndexRecord(
                    repo_id=repo_id,
                    full_name=repo.full_name,
                    html_url=repo.html_url,
                    collection_name=collection_name,
                    metadata=metadata,
                    stats=stats,
                    tree_outline=tree_outline,
                )
            )
        finally:
            # The clone is disposable: Chroma is the source of truth from here on.
            git_service.cleanup(repo)

        with self._lock:
            if job := self._jobs.get(repo_id):
                job.metadata = metadata
                job.stats = stats
                job.completed_at = datetime.now()
        self._set_stage(
            repo_id,
            IndexStage.READY,
            message=f"Indexed {stats.total_files_indexed} files into {stats.total_chunks} chunks",
        )
        logger.info("Indexed %s in %.2fs", repo.full_name, stats.indexing_seconds)

    def _fetch_metadata(self, repo: RepoRef) -> RepositoryMetadata:
        """GitHub metadata, degrading gracefully when only the API is unavailable."""
        from app.core.exceptions import GitHubAPIError

        try:
            return github_service.fetch_metadata(repo)
        except GitHubAPIError as exc:
            # Rate limiting must not block indexing — the clone can still succeed.
            logger.warning("Continuing without GitHub metadata: %s", exc.message)
            return github_service.fallback_metadata(repo)

    def _report_embedding_progress(self, repo_id: str, done: int, total: int) -> None:
        fraction = done / max(total, 1)
        progress = _EMBED_PROGRESS_START + fraction * (_EMBED_PROGRESS_END - _EMBED_PROGRESS_START)
        with self._lock:
            job = self._jobs.get(repo_id)
            if job is None or job.stage is not IndexStage.EMBEDDING:
                return
            job.progress = progress
            job.message = f"Generating embeddings ({done}/{total} chunks)"

    def _fail(self, repo_id: str, code: str, message: str) -> None:
        with self._lock:
            job = self._jobs.get(repo_id)
            if job is None:
                return
            job.stage = IndexStage.FAILED
            job.progress = 1.0
            job.message = STAGE_MESSAGES[IndexStage.FAILED]
            job.error_code = code
            job.error_message = message
            job.completed_at = datetime.now()
        logger.error("[%s] indexing failed (%s): %s", repo_id, code, message)


indexing_service = IndexingService()

__all__ = ["IndexingService", "IndexJob", "indexing_service", "STAGE_MESSAGES"]
