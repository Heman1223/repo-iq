"""ChromaDB persistence layer.

One collection per repository keeps deletes cheap (re-indexing simply drops the
collection) and keeps similarity search naturally scoped. Embeddings are always
supplied explicitly by :mod:`app.services.embedding_service`, so Chroma never
downloads an embedding model of its own.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Sequence

from app.core.config import settings
from app.core.exceptions import VectorStoreError

if TYPE_CHECKING:  # pragma: no cover
    from chromadb.api import ClientAPI
    from chromadb.api.models.Collection import Collection

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RetrievedChunk:
    """A similarity-search hit, already converted to a 0..1 relevance score."""

    text: str
    file_path: str
    language: str
    chunk_index: int
    start_line: int
    end_line: int
    distance: float

    @property
    def relevance(self) -> float:
        """Cosine distance (0..2) mapped to an intuitive 0..1 score."""
        return max(0.0, min(1.0, 1.0 - self.distance / 2.0))


class VectorStore:
    """Thin, dependency-injectable facade over a persistent Chroma client."""

    def __init__(self) -> None:
        self._client: ClientAPI | None = None
        self._lock = threading.Lock()

    # -- lifecycle -----------------------------------------------------------

    @property
    def is_ready(self) -> bool:
        return self._client is not None

    def _get_client(self) -> ClientAPI:
        if self._client is not None:
            return self._client

        with self._lock:
            if self._client is None:
                try:
                    import chromadb
                    from chromadb.config import Settings as ChromaSettings

                    settings.chroma_dir.mkdir(parents=True, exist_ok=True)
                    self._client = chromadb.PersistentClient(
                        path=str(settings.chroma_dir),
                        settings=ChromaSettings(anonymized_telemetry=False, allow_reset=True),
                    )
                    logger.info("ChromaDB ready at %s", settings.chroma_dir)
                except Exception as exc:
                    raise VectorStoreError(f"Could not open the vector database: {exc}") from exc
        return self._client

    def warm_up(self) -> None:
        """Open the database on startup so /health reports honestly."""
        try:
            self._get_client()
        except VectorStoreError as exc:  # pragma: no cover
            logger.warning("Vector store warm-up failed: %s", exc)

    # -- collections ---------------------------------------------------------

    def get_or_create_collection(self, name: str, metadata: dict[str, Any] | None = None):
        """Fetch a collection, creating it with cosine similarity if missing."""
        client = self._get_client()
        try:
            return client.get_or_create_collection(
                name=name,
                metadata={"hnsw:space": "cosine", **(metadata or {})},
            )
        except Exception as exc:
            raise VectorStoreError(f"Could not open collection '{name}': {exc}") from exc

    def get_collection(self, name: str) -> Collection | None:
        """Return an existing collection, or ``None`` when it does not exist."""
        try:
            return self._get_client().get_collection(name=name)
        except Exception:
            return None

    def drop_collection(self, name: str) -> None:
        """Delete a collection if present (used by force re-index)."""
        try:
            self._get_client().delete_collection(name=name)
            logger.info("Dropped collection %s", name)
        except Exception:
            logger.debug("Collection %s did not exist; nothing to drop", name)

    def count(self, name: str) -> int:
        collection = self.get_collection(name)
        if collection is None:
            return 0
        try:
            return int(collection.count())
        except Exception:  # pragma: no cover
            return 0

    def list_collections(self) -> list[str]:
        """Collection names. Chroma >= 0.6 returns names, older versions objects."""
        try:
            entries = self._get_client().list_collections()
        except Exception:  # pragma: no cover
            return []
        return [entry if isinstance(entry, str) else getattr(entry, "name", str(entry))
                for entry in entries]

    # -- writes --------------------------------------------------------------

    def add_documents(
        self,
        collection_name: str,
        ids: Sequence[str],
        documents: Sequence[str],
        embeddings: Sequence[Sequence[float]],
        metadatas: Sequence[dict[str, Any]],
    ) -> int:
        """Upsert documents in slices Chroma is comfortable with."""
        if not ids:
            return 0
        if not (len(ids) == len(documents) == len(embeddings) == len(metadatas)):
            raise VectorStoreError("Mismatched lengths supplied to the vector store.")

        collection = self.get_or_create_collection(collection_name)
        batch = settings.vector_upsert_batch_size
        written = 0

        try:
            for start in range(0, len(ids), batch):
                stop = start + batch
                collection.upsert(
                    ids=list(ids[start:stop]),
                    documents=list(documents[start:stop]),
                    embeddings=[list(vector) for vector in embeddings[start:stop]],
                    metadatas=list(metadatas[start:stop]),
                )
                written += len(ids[start:stop])
        except Exception as exc:
            raise VectorStoreError(f"Failed to write vectors: {exc}") from exc

        return written

    # -- reads ---------------------------------------------------------------

    def similarity_search(
        self,
        collection_name: str,
        query_embedding: Sequence[float],
        top_k: int,
        max_distance: float | None = None,
    ) -> list[RetrievedChunk]:
        """Return the ``top_k`` nearest chunks, filtered by distance threshold."""
        collection = self.get_collection(collection_name)
        if collection is None:
            return []

        limit = max(1, min(top_k, max(collection.count(), 1)))
        try:
            response = collection.query(
                query_embeddings=[list(query_embedding)],
                n_results=limit,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:
            raise VectorStoreError(f"Similarity search failed: {exc}") from exc

        documents = (response.get("documents") or [[]])[0]
        metadatas = (response.get("metadatas") or [[]])[0]
        distances = (response.get("distances") or [[]])[0]
        threshold = settings.max_match_distance if max_distance is None else max_distance

        hits: list[RetrievedChunk] = []
        for document, metadata, distance in zip(documents, metadatas, distances):
            if document is None or distance is None or float(distance) > threshold:
                continue
            meta = metadata or {}
            hits.append(
                RetrievedChunk(
                    text=document,
                    file_path=str(meta.get("file_path", "unknown")),
                    language=str(meta.get("language", "")) or "text",
                    chunk_index=int(meta.get("chunk_index", 0) or 0),
                    start_line=int(meta.get("start_line", 0) or 0),
                    end_line=int(meta.get("end_line", 0) or 0),
                    distance=float(distance),
                )
            )
        return hits


vector_store = VectorStore()
