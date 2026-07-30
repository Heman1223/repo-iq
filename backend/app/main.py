"""FastAPI application entry point.

Run with::

    uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging_config import configure_logging
from app.services.embedding_service import embedding_service
from app.services.vector_store import vector_store

logger = logging.getLogger(__name__)

DESCRIPTION = """
Retrieval-Augmented Generation over any public GitHub repository.

**Pipeline** — clone → filter files → chunk → embed locally with
`all-MiniLM-L6-v2` → store in ChromaDB → retrieve top matches → answer with
Google Gemini, citing the exact files the answer came from.
"""


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Prepare storage and warm heavy singletons without blocking startup."""
    configure_logging()
    settings.ensure_directories()

    logger.info("%s v%s starting", settings.app_name, settings.app_version)
    logger.info("Vector store: %s", settings.chroma_dir)
    logger.info("Embedding model: %s", settings.embedding_model_name)
    if not settings.llm_configured:
        logger.warning(
            "GEMINI_API_KEY is not set — indexing works, but /ask and /summary will "
            "return 503 until it is configured in backend/.env"
        )

    vector_store.warm_up()
    # Loading the transformer takes a few seconds; do it off the event loop so the
    # first request is fast but startup is not delayed.
    threading.Thread(target=embedding_service.warm_up, name="embed-warmup", daemon=True).start()

    yield

    logger.info("%s shutting down", settings.app_name)


def create_app() -> FastAPI:
    """Application factory — keeps the app testable and configuration-driven."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=DESCRIPTION,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_prefix)

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
            "health": f"{settings.api_prefix}/health",
        }

    return app


app = create_app()
