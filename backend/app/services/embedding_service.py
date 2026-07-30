"""Local embedding generation with sentence-transformers.

The model (``all-MiniLM-L6-v2``, 384 dimensions) runs entirely on this machine —
no paid embedding API is involved. Loading is lazy and thread-safe so server
startup stays fast and the weights are only paid for once.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Callable, Sequence

from app.core.config import settings
from app.core.exceptions import EmbeddingError

if TYPE_CHECKING:  # pragma: no cover - import cost avoided at runtime
    from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int], None]


class EmbeddingService:
    """Thread-safe singleton wrapper around a local SentenceTransformer."""

    def __init__(self, model_name: str | None = None, batch_size: int | None = None) -> None:
        self._model_name = model_name or settings.embedding_model_name
        self._batch_size = batch_size or settings.embedding_batch_size
        self._model: SentenceTransformer | None = None
        self._lock = threading.Lock()

    # -- properties ----------------------------------------------------------

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    @property
    def dimensions(self) -> int:
        """Embedding width; loads the model on first access."""
        model = self._ensure_model()
        # `get_sentence_embedding_dimension` was renamed in sentence-transformers 5.
        getter = getattr(model, "get_embedding_dimension", None) or getattr(
            model, "get_sentence_embedding_dimension"
        )
        return int(getter() or 0)

    # -- public API ----------------------------------------------------------

    def embed_documents(
        self,
        texts: Sequence[str],
        on_progress: ProgressCallback | None = None,
    ) -> list[list[float]]:
        """Embed repository chunks in batches, reporting progress as it goes."""
        if not texts:
            return []

        model = self._ensure_model()
        vectors: list[list[float]] = []
        total = len(texts)

        try:
            for start in range(0, total, self._batch_size):
                batch = list(texts[start : start + self._batch_size])
                encoded = model.encode(
                    batch,
                    batch_size=self._batch_size,
                    convert_to_numpy=True,
                    normalize_embeddings=True,
                    show_progress_bar=False,
                )
                vectors.extend(vector.tolist() for vector in encoded)
                if on_progress is not None:
                    on_progress(min(start + len(batch), total), total)
        except Exception as exc:
            logger.exception("Embedding generation failed")
            raise EmbeddingError(f"Embedding generation failed: {exc}") from exc

        return vectors

    def embed_query(self, text: str) -> list[float]:
        """Embed a single user question."""
        model = self._ensure_model()
        try:
            vector = model.encode(
                [text],
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )[0]
        except Exception as exc:
            raise EmbeddingError(f"Could not embed the question: {exc}") from exc
        return vector.tolist()

    def warm_up(self) -> None:
        """Preload weights (called on startup) so the first query is fast."""
        try:
            self._ensure_model()
        except EmbeddingError as exc:  # pragma: no cover - offline first run
            logger.warning("Embedding model warm-up skipped: %s", exc)

    # -- internals -----------------------------------------------------------

    def _ensure_model(self) -> SentenceTransformer:
        if self._model is not None:
            return self._model

        with self._lock:
            if self._model is None:
                logger.info("Loading embedding model '%s' ...", self._model_name)
                try:
                    from sentence_transformers import SentenceTransformer

                    self._model = SentenceTransformer(self._model_name)
                except Exception as exc:
                    raise EmbeddingError(
                        f"Could not load embedding model '{self._model_name}'. "
                        "The first run needs internet access to download the weights."
                    ) from exc
                logger.info("Embedding model ready (%d dimensions)", self.dimensions)
        return self._model


embedding_service = EmbeddingService()
