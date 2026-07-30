"""Repository indexing endpoints: /clone, /status, /summary, /repositories."""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Query, status

from app.models.schemas import (
    CloneRequest,
    CloneResponse,
    IndexStatus,
    RepositoryListResponse,
    SummaryResponse,
)
from app.services.indexing_service import indexing_service
from app.services.rag_service import rag_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["repository"])


@router.post(
    "/clone",
    response_model=CloneResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Clone and index a public GitHub repository",
)
def clone_repository(payload: CloneRequest, background: BackgroundTasks) -> CloneResponse:
    """Kick off (or reuse) an index for the supplied repository URL.

    The request returns as soon as the job is registered; the client then polls
    ``GET /status`` for progress. Submitting an already-indexed repository is a
    no-op unless ``force_reindex`` is set.
    """
    repo, index_status, needs_indexing = indexing_service.prepare(
        payload.repo_url, force=payload.force_reindex
    )

    if needs_indexing:
        # Runs in FastAPI's threadpool: the pipeline is CPU/IO bound and blocking.
        background.add_task(indexing_service.run, repo, force=payload.force_reindex)
        logger.info("Queued indexing job for %s", repo.full_name)

    return CloneResponse(
        repo_id=repo.repo_id,
        full_name=repo.full_name,
        already_indexed=not needs_indexing and index_status.is_ready,
        status=index_status,
    )


@router.get("/status", response_model=IndexStatus, summary="Poll indexing progress")
def get_status(
    repo_id: str = Query(..., min_length=1, max_length=200, description="Identifier from /clone."),
) -> IndexStatus:
    """Return the live pipeline stage, progress fraction and dashboard stats."""
    return indexing_service.get_status(repo_id)


@router.get(
    "/summary",
    response_model=SummaryResponse,
    summary="Generate an AI onboarding briefing for an indexed repository",
)
def get_summary(
    repo_id: str = Query(..., min_length=1, max_length=200),
    refresh: bool = Query(False, description="Bypass the cached briefing and regenerate it."),
) -> SummaryResponse:
    """Multi-facet retrieval plus one Gemini call, cached after the first run."""
    return rag_service.summarize_repository(repo_id, refresh=refresh)


@router.get(
    "/repositories",
    response_model=RepositoryListResponse,
    summary="List every repository indexed on this server",
)
def list_repositories() -> RepositoryListResponse:
    return RepositoryListResponse(repositories=indexing_service.list_repositories())


@router.delete(
    "/repositories/{repo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a repository's vectors and cached metadata",
)
def delete_repository(repo_id: str) -> None:
    indexing_service.delete_index(repo_id)
