"""Google Gemini integration.

Every LLM call in the application goes through this module. Nothing else imports
the Gemini SDK, so swapping providers means editing one file.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Any

from app.core.config import settings
from app.core.exceptions import LLMError, LLMNotConfigured
from app.models.schemas import ChatTurn

if TYPE_CHECKING:  # pragma: no cover
    from google.genai import Client

logger = logging.getLogger(__name__)

_TRANSIENT_HINTS = ("429", "resource_exhausted", "rate limit", "quota")


class LLMService:
    """Stateless wrapper around the Gemini ``generate_content`` endpoint."""

    def __init__(self, model: str | None = None) -> None:
        self._model = model or settings.gemini_model
        self._client: Client | None = None
        self._lock = threading.Lock()

    # -- properties ----------------------------------------------------------

    @property
    def model(self) -> str:
        return self._model

    @property
    def is_configured(self) -> bool:
        return settings.llm_configured

    # -- public API ----------------------------------------------------------

    def generate(
        self,
        *,
        prompt: str,
        system_instruction: str,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ) -> str:
        """Run one grounded completion and return the model's text.

        Raises:
            LLMNotConfigured: no ``GEMINI_API_KEY`` is present.
            LLMError: the API rejected the request or returned no usable text.
        """
        client = self._ensure_client()
        config = self._build_config(
            system_instruction=system_instruction,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )

        try:
            response = client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=config,
            )
        except Exception as exc:
            # Not every model accepts `thinking_level`. Rather than failing every
            # answer because of one env value, drop it and try once more.
            if self._is_thinking_rejection(exc) and settings.gemini_thinking_level:
                logger.warning(
                    "Model '%s' rejected GEMINI_THINKING_LEVEL=%s; retrying without it",
                    self._model,
                    settings.gemini_thinking_level,
                )
                try:
                    response = client.models.generate_content(
                        model=self._model,
                        contents=prompt,
                        config=self._build_config(
                            system_instruction=system_instruction,
                            temperature=temperature,
                            max_output_tokens=max_output_tokens,
                            thinking=False,
                        ),
                    )
                except Exception as retry_exc:
                    raise self._translate(retry_exc) from retry_exc
            else:
                raise self._translate(exc) from exc

        text = self._extract_text(response)
        if not text:
            raise LLMError(
                "Gemini returned an empty response. This usually means the request was "
                "blocked by a safety filter or the output token limit was too low."
            )
        return text

    def chat_history_as_text(self, history: list[ChatTurn]) -> str:
        """Flatten recent turns into a compact transcript for follow-up context."""
        if not history:
            return ""

        recent = history[-settings.max_history_turns :]
        lines = [
            f"{'User' if turn.role == 'user' else 'Assistant'}: {turn.content.strip()[:600]}"
            for turn in recent
            if turn.content.strip()
        ]
        return "\n".join(lines)

    # -- internals -----------------------------------------------------------

    def _ensure_client(self) -> Client:
        if not self.is_configured:
            raise LLMNotConfigured(
                "GEMINI_API_KEY is missing. Add it to backend/.env and restart the server."
            )
        if self._client is not None:
            return self._client

        with self._lock:
            if self._client is None:
                try:
                    from google import genai

                    self._client = genai.Client(api_key=settings.gemini_api_key.strip())
                    logger.info("Gemini client initialised (model=%s)", self._model)
                except Exception as exc:
                    raise LLMError(f"Could not initialise the Gemini client: {exc}") from exc
        return self._client

    def _build_config(
        self,
        *,
        system_instruction: str,
        temperature: float | None,
        max_output_tokens: int | None,
        thinking: bool = True,
    ) -> Any:
        """Build a ``GenerateContentConfig``, falling back to a plain dict."""
        values = {
            "system_instruction": system_instruction,
            "temperature": settings.gemini_temperature if temperature is None else temperature,
            "max_output_tokens": (
                settings.gemini_max_output_tokens if max_output_tokens is None else max_output_tokens
            ),
        }
        try:
            from google.genai import types

            level = settings.gemini_thinking_level.strip().lower()
            if thinking and level:
                values["thinking_config"] = types.ThinkingConfig(thinking_level=level)
            return types.GenerateContentConfig(**values)
        except Exception:  # pragma: no cover - SDK shape drift
            values.pop("thinking_config", None)
            return values

    @staticmethod
    def _is_thinking_rejection(exc: Exception) -> bool:
        """True when the failure looks like an unsupported thinking setting."""
        lowered = str(exc).lower()
        return "invalid_argument" in lowered or "invalid argument" in lowered

    @staticmethod
    def _extract_text(response: Any) -> str:
        """Read text from the response, tolerating multi-part candidates."""
        text = getattr(response, "text", None)
        if isinstance(text, str) and text.strip():
            return text.strip()

        parts: list[str] = []
        for candidate in getattr(response, "candidates", None) or []:
            content = getattr(candidate, "content", None)
            for part in getattr(content, "parts", None) or []:
                value = getattr(part, "text", None)
                if isinstance(value, str) and value.strip():
                    parts.append(value.strip())
        return "\n".join(parts).strip()

    @staticmethod
    def _translate(exc: Exception) -> LLMError:
        """Convert SDK exceptions into a friendly, actionable message."""
        detail = str(exc)
        lowered = detail.lower()

        if "api key" in lowered or "api_key" in lowered or "unauthenticated" in lowered:
            return LLMError("Gemini rejected the API key. Verify GEMINI_API_KEY in backend/.env.")
        if any(hint in lowered for hint in _TRANSIENT_HINTS):
            return LLMError("Gemini rate limit reached. Please wait a moment and try again.")
        # Retired models answer 404 NOT_FOUND / "no longer available to new users".
        if (
            "not_found" in lowered
            or "no longer available" in lowered
            or ("not found" in lowered and "model" in lowered)
        ):
            return LLMError(
                f"Gemini model '{settings.gemini_model}' is unavailable for this key "
                "(it may have been retired). Set GEMINI_MODEL in backend/.env to a model "
                "you have access to, such as 'gemini-flash-latest'."
            )
        if "unavailable" in lowered or "503" in lowered:
            return LLMError(
                f"Gemini model '{settings.gemini_model}' is temporarily overloaded. "
                "Retry in a moment, or switch GEMINI_MODEL in backend/.env."
            )
        if "deadline" in lowered or "timeout" in lowered:
            return LLMError("Gemini timed out. Try a narrower question.")

        logger.error("Gemini call failed: %s", detail[:500])
        return LLMError(f"Gemini API error: {detail[:200]}")


llm_service = LLMService()
