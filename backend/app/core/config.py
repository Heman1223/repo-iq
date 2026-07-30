"""Application configuration.

Every tunable value lives here and is overridable through environment
variables (see ``.env.example``). Nothing in the codebase should hardcode
paths, model names, limits or credentials.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> backend/
BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Typed, validated application settings."""

    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- App -----------------------------------------------------------------
    app_name: str = "GitHub Repository AI Assistant"
    app_version: str = "1.0.0"
    # Empty prefix keeps the documented routes at the root: POST /clone, /ask...
    api_prefix: str = ""
    debug: bool = False
    log_level: str = "INFO"

    # Comma separated list of allowed browser origins.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- Storage -------------------------------------------------------------
    repositories_dir: Path = BACKEND_DIR / "repositories"
    chroma_dir: Path = BACKEND_DIR / "chroma_db"
    # Small JSON cache so indexed repositories survive a server restart. Left
    # unset it follows `chroma_dir`, keeping the registry beside the vectors it
    # describes even when CHROMA_DIR is overridden.
    index_cache_file: Path | None = None

    # --- GitHub / git --------------------------------------------------------
    github_api_base: str = "https://api.github.com"
    # Optional: raises the anonymous rate limit for metadata lookups only.
    github_token: str = ""
    allowed_git_hosts: str = "github.com,www.github.com"
    clone_depth: int = 1
    clone_timeout_seconds: int = 300
    http_timeout_seconds: float = 20.0

    # --- File scanning -------------------------------------------------------
    max_file_size_bytes: int = 400_000
    max_files_per_repo: int = 4_000
    max_total_bytes: int = 40_000_000

    # --- Chunking ------------------------------------------------------------
    chunk_size: int = 1_200
    chunk_overlap: int = 180

    # --- Embeddings ----------------------------------------------------------
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_batch_size: int = 64
    # Chroma rejects very large single writes; insert in slices.
    vector_upsert_batch_size: int = 256

    # --- Retrieval -----------------------------------------------------------
    retrieval_top_k: int = 8
    # Broader sweep used when building whole-repository summaries.
    summary_top_k: int = 5
    # Coarse guard only. Measured on real repositories, the distance bands for
    # relevant (~0.40-0.77) and off-topic (~0.67-0.85) questions overlap, so a
    # tight cutoff would drop good questions. Grounding is enforced by the
    # prompt's sentinel rule; this simply discards obvious garbage.
    max_match_distance: float = 1.55

    # --- LLM (Gemini) --------------------------------------------------------
    gemini_api_key: str = Field(default="", repr=False)
    # The `-latest` alias keeps working as Google retires specific versions;
    # pin a concrete model (e.g. gemini-3.6-flash) for reproducible behaviour.
    gemini_model: str = "gemini-flash-latest"
    gemini_temperature: float = 0.2
    gemini_max_output_tokens: int = 2_048
    # Gemini 3 reasoning depth: "minimal" | "low" | "medium" | "high".
    # Empty uses the model's own default. Lower is faster and cheaper; measured
    # answer quality on repository questions is comparable at "minimal".
    gemini_thinking_level: str = ""
    # Conversation turns replayed back to the model for follow-up questions.
    max_history_turns: int = 6

    @field_validator("repositories_dir", "chroma_dir", "index_cache_file")
    @classmethod
    def _absolute(cls, value: Path | None) -> Path | None:
        """Resolve relative overrides against the backend directory."""
        if value is None:
            return None
        path = Path(value)
        return path if path.is_absolute() else (BACKEND_DIR / path).resolve()

    @model_validator(mode="after")
    def _default_cache_beside_vectors(self) -> Settings:
        """Place the index registry inside ``chroma_dir`` unless told otherwise."""
        if self.index_cache_file is None:
            # `object.__setattr__` avoids re-triggering validation on assignment.
            object.__setattr__(self, "index_cache_file", self.chroma_dir / "index_cache.json")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def allowed_git_host_list(self) -> list[str]:
        return [host.strip().lower() for host in self.allowed_git_hosts.split(",") if host.strip()]

    @property
    def llm_configured(self) -> bool:
        return bool(self.gemini_api_key.strip())

    def ensure_directories(self) -> None:
        """Create the on-disk working directories if they do not exist yet."""
        self.repositories_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_dir.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor (import-safe, test-overridable)."""
    return Settings()


settings = get_settings()
