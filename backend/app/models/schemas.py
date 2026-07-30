"""Pydantic request/response contracts shared by every API route."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class IndexStage(str, Enum):
    """Ordered pipeline stages, surfaced verbatim in the loading screen."""

    QUEUED = "queued"
    VALIDATING = "validating"
    CLONING = "cloning"
    READING_FILES = "reading_files"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    STORING = "storing"
    FINALIZING = "finalizing"
    READY = "ready"
    FAILED = "failed"


# --- Repository metadata -----------------------------------------------------


class RepositoryMetadata(BaseModel):
    """Public repository facts fetched from the GitHub REST API."""

    full_name: str
    name: str
    owner: str
    html_url: str
    description: str | None = None
    language: str | None = None
    stars: int = 0
    forks: int = 0
    watchers: int = 0
    open_issues: int = 0
    size_kb: int = 0
    default_branch: str = "main"
    topics: list[str] = Field(default_factory=list)
    license_name: str | None = None
    is_fork: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None
    pushed_at: datetime | None = None


class IndexStats(BaseModel):
    """Everything the dashboard reports about a completed index."""

    total_files_scanned: int = 0
    total_files_indexed: int = 0
    total_files_skipped: int = 0
    total_chunks: int = 0
    total_characters: int = 0
    embedding_model: str
    embedding_dimensions: int = 0
    vector_count: int = 0
    languages: dict[str, int] = Field(default_factory=dict)
    top_level_entries: list[str] = Field(default_factory=list)
    indexing_seconds: float = 0.0
    indexed_at: datetime | None = None


class IndexStatus(BaseModel):
    """Live progress for one repository indexing job."""

    repo_id: str
    full_name: str
    html_url: str
    stage: IndexStage
    progress: float = Field(0.0, ge=0.0, le=1.0)
    message: str = ""
    is_ready: bool = False
    error_code: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    reused_existing_index: bool = False
    metadata: RepositoryMetadata | None = None
    stats: IndexStats | None = None


# --- /clone ------------------------------------------------------------------


class CloneRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {"repo_url": "https://github.com/tiangolo/fastapi", "force_reindex": False}
    })

    repo_url: str = Field(..., min_length=4, max_length=400, description="Public GitHub URL.")
    force_reindex: bool = Field(
        False, description="Discard any existing vectors and re-index from scratch."
    )


class CloneResponse(BaseModel):
    repo_id: str
    full_name: str
    already_indexed: bool
    status: IndexStatus


# --- /ask --------------------------------------------------------------------


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., max_length=8_000)


class SourceReference(BaseModel):
    """One retrieved chunk, shown under an answer as a citation."""

    file_path: str
    language: str | None = None
    chunk_index: int = 0
    start_line: int | None = None
    end_line: int | None = None
    relevance: float = Field(0.0, ge=0.0, le=1.0)
    snippet: str = ""


class AskRequest(BaseModel):
    repo_id: str = Field(..., min_length=1, max_length=200)
    question: str = Field(..., min_length=2, max_length=2_000)
    history: list[ChatTurn] = Field(default_factory=list)
    top_k: int | None = Field(None, ge=1, le=25)


class AskResponse(BaseModel):
    repo_id: str
    question: str
    answer: str
    sources: list[SourceReference] = Field(default_factory=list)
    grounded: bool = Field(True, description="False when retrieval found nothing relevant.")
    model: str
    retrieved_chunks: int = 0
    elapsed_ms: int = 0


# --- /summary ----------------------------------------------------------------


class SummaryResponse(BaseModel):
    repo_id: str
    full_name: str
    summary: str
    sources: list[SourceReference] = Field(default_factory=list)
    model: str
    cached: bool = False
    generated_at: datetime


# --- misc --------------------------------------------------------------------


class IndexedRepositorySummary(BaseModel):
    repo_id: str
    full_name: str
    html_url: str
    stage: IndexStage
    indexed_at: datetime | None = None
    total_chunks: int = 0


class RepositoryListResponse(BaseModel):
    repositories: list[IndexedRepositorySummary] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    app: str
    version: str
    llm_configured: bool
    llm_model: str
    embedding_model: str
    embedding_model_loaded: bool
    vector_store_ready: bool
    indexed_repositories: int
