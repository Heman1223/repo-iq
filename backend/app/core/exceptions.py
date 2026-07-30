"""Domain exceptions and the FastAPI handlers that render them.

Each error carries a stable machine-readable ``code`` so the frontend can
localise/branch on failures without string-matching messages.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base class for every expected, user-facing failure."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "app_error"
    default_message: str = "Something went wrong."

    def __init__(self, message: str | None = None, *, hint: str | None = None) -> None:
        self.message = message or self.default_message
        self.hint = hint
        super().__init__(self.message)

    def to_payload(self) -> dict[str, object]:
        return {"error": {"code": self.code, "message": self.message, "hint": self.hint}}


# --- Repository / URL --------------------------------------------------------


class InvalidRepositoryURL(AppError):
    code = "invalid_repository_url"
    default_message = "That does not look like a valid public GitHub repository URL."


class RepositoryNotFound(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "repository_not_found"
    default_message = "Repository not found on GitHub."


class PrivateRepositoryError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "private_repository"
    default_message = "This repository is private. Only public repositories are supported."


class EmptyRepositoryError(AppError):
    code = "empty_repository"
    default_message = "The repository contains no readable source files to index."


class UnsupportedRepositoryError(AppError):
    code = "unsupported_repository"
    default_message = "This repository is too large or unsupported."


class CloneError(AppError):
    status_code = status.HTTP_502_BAD_GATEWAY
    code = "clone_failed"
    default_message = "Failed to clone the repository."


class GitHubAPIError(AppError):
    status_code = status.HTTP_502_BAD_GATEWAY
    code = "github_api_error"
    default_message = "The GitHub API could not be reached."


# --- Indexing / retrieval ----------------------------------------------------


class RepositoryNotIndexed(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "repository_not_indexed"
    default_message = "This repository has not been indexed yet."


class IndexingInProgress(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "indexing_in_progress"
    default_message = "This repository is still being indexed."


class EmbeddingError(AppError):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    code = "embedding_failed"
    default_message = "Failed to generate embeddings for this repository."


class VectorStoreError(AppError):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    code = "vector_store_error"
    default_message = "The vector database could not complete the request."


# --- LLM ---------------------------------------------------------------------


class LLMNotConfigured(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "llm_not_configured"
    default_message = "GEMINI_API_KEY is not configured on the server."


class LLMError(AppError):
    status_code = status.HTTP_502_BAD_GATEWAY
    code = "llm_error"
    default_message = "The Gemini API returned an error."


def register_exception_handlers(app: FastAPI) -> None:
    """Attach JSON error handlers so responses share one envelope shape."""

    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        logger.warning("AppError [%s]: %s", exc.code, exc.message)
        return JSONResponse(status_code=exc.status_code, content=exc.to_payload())

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        return JSONResponse(
            status_code=422,  # Unprocessable Content
            content={
                "error": {
                    "code": "validation_error",
                    "message": first.get("msg", "Invalid request payload."),
                    "hint": ".".join(str(part) for part in first.get("loc", [])) or None,
                }
            },
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled server error: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "An unexpected server error occurred.",
                    "hint": None,
                }
            },
        )
