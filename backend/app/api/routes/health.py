"""Health and readiness endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings
from app.models.schemas import HealthResponse
from app.services.embedding_service import embedding_service
from app.services.index_cache import index_cache
from app.services.llm_service import llm_service
from app.services.vector_store import vector_store

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse, summary="Service health check")
def health() -> HealthResponse:
    """Report configuration and subsystem readiness.

    Returns ``degraded`` (still HTTP 200) when the Gemini key is missing: indexing
    and retrieval work, but answers cannot be generated.
    """
    return HealthResponse(
        status="ok" if llm_service.is_configured else "degraded",
        app=settings.app_name,
        version=settings.app_version,
        llm_configured=llm_service.is_configured,
        llm_model=llm_service.model,
        embedding_model=embedding_service.model_name,
        embedding_model_loaded=embedding_service.is_loaded,
        vector_store_ready=vector_store.is_ready,
        indexed_repositories=index_cache.count(),
    )
