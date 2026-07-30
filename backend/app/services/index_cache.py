"""Durable registry of indexed repositories.

Chroma stores the vectors; this small JSON cache stores everything *around* them
(GitHub metadata, index statistics, directory outline, generated summary) so a
server restart does not force a re-index and repeated questions never re-clone.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from app.core.config import settings
from app.models.schemas import IndexStats, RepositoryMetadata

logger = logging.getLogger(__name__)


class IndexRecord(BaseModel):
    """Everything known about one successfully indexed repository."""

    repo_id: str
    full_name: str
    html_url: str
    collection_name: str
    metadata: RepositoryMetadata
    stats: IndexStats
    tree_outline: str = ""
    summary: str | None = None
    summary_generated_at: datetime | None = None
    indexed_at: datetime = Field(default_factory=datetime.now)


class IndexCache:
    """Thread-safe, atomically persisted ``repo_id -> IndexRecord`` map."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or settings.index_cache_file
        self._lock = threading.RLock()
        self._records: dict[str, IndexRecord] = {}
        self._loaded = False

    # -- persistence ---------------------------------------------------------

    def _load(self) -> None:
        if self._loaded:
            return

        self._loaded = True
        if not self._path.exists():
            return

        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Ignoring unreadable index cache (%s): %s", self._path.name, exc)
            return

        for repo_id, payload in (raw or {}).items():
            try:
                self._records[repo_id] = IndexRecord.model_validate(payload)
            except ValidationError as exc:
                logger.warning("Dropping stale cache entry '%s': %s", repo_id, exc.error_count())

        logger.info("Loaded %d indexed repositor%s from cache",
                    len(self._records), "y" if len(self._records) == 1 else "ies")

    def _flush(self) -> None:
        """Write the cache via a temp file so a crash cannot corrupt it."""
        payload = {
            repo_id: json.loads(record.model_dump_json())
            for repo_id, record in self._records.items()
        }
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self._path.with_suffix(".tmp")
            temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            temp_path.replace(self._path)
        except OSError as exc:  # pragma: no cover
            logger.warning("Could not persist index cache: %s", exc)

    # -- accessors -----------------------------------------------------------

    def get(self, repo_id: str) -> IndexRecord | None:
        with self._lock:
            self._load()
            return self._records.get(repo_id)

    def all(self) -> list[IndexRecord]:
        with self._lock:
            self._load()
            return sorted(
                self._records.values(), key=lambda record: record.indexed_at, reverse=True
            )

    def count(self) -> int:
        with self._lock:
            self._load()
            return len(self._records)

    def put(self, record: IndexRecord) -> IndexRecord:
        with self._lock:
            self._load()
            self._records[record.repo_id] = record
            self._flush()
            return record

    def remove(self, repo_id: str) -> None:
        with self._lock:
            self._load()
            if self._records.pop(repo_id, None) is not None:
                self._flush()

    def save_summary(self, repo_id: str, summary: str) -> None:
        """Cache a generated briefing so /summary is instant on repeat calls."""
        with self._lock:
            self._load()
            record = self._records.get(repo_id)
            if record is None:
                return
            record.summary = summary
            record.summary_generated_at = datetime.now()
            self._flush()


index_cache = IndexCache()
