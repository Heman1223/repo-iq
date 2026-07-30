"""Module 8 — AI response quality, tested at every layer below the LLM itself.

The generation call is mocked so grounding logic, citation assembly and the
"no answer" contract can be verified deterministically and without an API key.
The prompts sent to Gemini are captured and asserted on.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.core.config import settings
from app.models.schemas import AskRequest, ChatTurn, IndexStats, RepositoryMetadata
from app.services import prompts
from app.services.index_cache import IndexRecord
from app.services.rag_service import rag_service
from app.services.vector_store import RetrievedChunk


def make_record() -> IndexRecord:
    return IndexRecord(
        repo_id="owner__repo",
        full_name="owner/repo",
        html_url="https://github.com/owner/repo",
        collection_name="repo-owner-repo-deadbeef",
        metadata=RepositoryMetadata(
            full_name="owner/repo",
            name="repo",
            owner="owner",
            html_url="https://github.com/owner/repo",
            description="A demo service",
        ),
        stats=IndexStats(embedding_model="all-MiniLM-L6-v2", total_chunks=42),
        tree_outline="src/ -> app.py, auth.py\nsrc/api/ -> routes.py",
    )


def make_hits() -> list[RetrievedChunk]:
    return [
        RetrievedChunk(
            text="def create_access_token(user):\n    return jwt.encode({'sub': user.id}, SECRET)",
            file_path="src/auth/token.py",
            language="python",
            chunk_index=0,
            start_line=12,
            end_line=14,
            distance=0.31,
        ),
        RetrievedChunk(
            text="router.post('/login', login_handler)",
            file_path="src/api/routes.py",
            language="python",
            chunk_index=3,
            start_line=48,
            end_line=49,
            distance=0.52,
        ),
    ]


@pytest.fixture
def grounded_context():
    """Patch retrieval + the index so only the LLM boundary remains mocked."""
    with (
        patch("app.services.indexing_service.IndexingService.require_ready", return_value=make_record()),
        patch("app.services.rag_service.RagService._retrieve", return_value=make_hits()),
    ):
        yield


class TestGroundedAnswers:
    """TC_AI_001 / TC_AI_003 / TC_AI_007 — answers carry correct citations."""

    def test_answer_includes_sources_with_line_ranges(self, grounded_context) -> None:
        with patch(
            "app.services.llm_service.LLMService.generate",
            return_value="JWTs are signed in `src/auth/token.py`.",
        ):
            response = rag_service.answer_question(
                AskRequest(repo_id="owner__repo", question="Where is the JWT generated?")
            )

        assert response.grounded is True
        assert response.retrieved_chunks == 2
        assert [source.file_path for source in response.sources] == [
            "src/auth/token.py",
            "src/api/routes.py",
        ]
        assert response.sources[0].start_line == 12
        assert response.sources[0].end_line == 14
        assert 0.0 <= response.sources[0].relevance <= 1.0
        assert response.sources[0].snippet
        assert response.elapsed_ms >= 0

    def test_sources_are_ordered_by_relevance(self, grounded_context) -> None:
        with patch("app.services.llm_service.LLMService.generate", return_value="Answer."):
            response = rag_service.answer_question(
                AskRequest(repo_id="owner__repo", question="How does auth work?")
            )
        relevances = [source.relevance for source in response.sources]
        assert relevances == sorted(relevances, reverse=True)

    def test_snippets_are_truncated_for_the_ui(self, grounded_context) -> None:
        long_hit = RetrievedChunk(
            text="x = 1\n" * 500,
            file_path="src/long.py",
            language="python",
            chunk_index=0,
            start_line=1,
            end_line=500,
            distance=0.2,
        )
        with (
            patch("app.services.rag_service.RagService._retrieve", return_value=[long_hit]),
            patch("app.services.llm_service.LLMService.generate", return_value="Answer."),
        ):
            response = rag_service.answer_question(
                AskRequest(repo_id="owner__repo", question="What is in long.py?")
            )
        assert len(response.sources[0].snippet) < 500
        assert response.sources[0].snippet.endswith("...")


class TestNoAnswerContract:
    """TC_AI_004 / TC_AI_005 / TC_CODE_004 — the assistant admits ignorance."""

    def test_empty_retrieval_returns_the_sentinel_without_calling_the_llm(self) -> None:
        with (
            patch("app.services.indexing_service.IndexingService.require_ready", return_value=make_record()),
            patch("app.services.rag_service.RagService._retrieve", return_value=[]),
            patch("app.services.llm_service.LLMService.generate") as generate,
        ):
            response = rag_service.answer_question(
                AskRequest(repo_id="owner__repo", question="Does this project mine cryptocurrency?")
            )

        generate.assert_not_called()          # no tokens spent on a hopeless question
        assert response.answer == prompts.NO_ANSWER_SENTINEL
        assert response.grounded is False
        assert response.sources == []
        assert response.retrieved_chunks == 0

    def test_sentinel_from_the_model_suppresses_citations(self, grounded_context) -> None:
        """TC_AI_004 — if the model says it cannot answer, no sources are implied."""
        with patch(
            "app.services.llm_service.LLMService.generate",
            return_value=prompts.NO_ANSWER_SENTINEL,
        ):
            response = rag_service.answer_question(
                AskRequest(repo_id="owner__repo", question="Where is the Kafka consumer?")
            )

        assert response.grounded is False
        assert response.sources == []

    def test_sentinel_detection_is_case_insensitive(self, grounded_context) -> None:
        with patch(
            "app.services.llm_service.LLMService.generate",
            return_value="i couldn't find that information in the indexed repository.",
        ):
            response = rag_service.answer_question(
                AskRequest(repo_id="owner__repo", question="Where is the GraphQL schema?")
            )
        assert response.grounded is False


class TestPromptConstruction:
    """TC_AI_006 — the hallucination defences are actually sent to the model."""

    def _capture_prompt(self, question: str, history: list[ChatTurn] | None = None) -> dict:
        captured: dict[str, str] = {}

        def fake_generate(*, prompt: str, system_instruction: str, **_: object) -> str:
            captured["prompt"] = prompt
            captured["system"] = system_instruction
            return "Answer."

        with (
            patch("app.services.indexing_service.IndexingService.require_ready", return_value=make_record()),
            patch("app.services.rag_service.RagService._retrieve", return_value=make_hits()),
            patch("app.services.llm_service.LLMService.generate", side_effect=fake_generate),
        ):
            rag_service.answer_question(
                AskRequest(repo_id="owner__repo", question=question, history=history or [])
            )
        return captured

    def test_system_instruction_enforces_grounding(self) -> None:
        captured = self._capture_prompt("How does auth work?")
        system = captured["system"]

        assert prompts.NO_ANSWER_SENTINEL in system
        assert "Never invent files" in system
        assert "only" in system.lower()

    def test_retrieved_context_is_labelled_with_file_paths_and_lines(self) -> None:
        prompt = self._capture_prompt("How does auth work?")["prompt"]

        assert "FILE: src/auth/token.py (lines 12-14, language: python)" in prompt
        assert "FILE: src/api/routes.py (lines 48-49, language: python)" in prompt
        assert "<<<BEGIN CONTEXT>>>" in prompt and "<<<END CONTEXT>>>" in prompt

    def test_whole_repository_is_never_sent(self) -> None:
        """Only the retrieved chunks appear — this is RAG, not a full-repo dump."""
        prompt = self._capture_prompt("How does auth work?")["prompt"]
        assert "create_access_token" in prompt
        # A file that was not retrieved must be absent from the context block.
        context = prompt[prompt.index("<<<BEGIN CONTEXT>>>") : prompt.index("<<<END CONTEXT>>>")]
        assert "unrelated_module" not in context

    def test_conversation_history_is_included_for_follow_ups(self) -> None:
        """TC_CHAT_004 — prior turns are replayed so pronouns resolve."""
        history = [
            ChatTurn(role="user", content="Where is the JWT generated?"),
            ChatTurn(role="assistant", content="In src/auth/token.py."),
        ]
        prompt = self._capture_prompt("And where is it verified?", history)["prompt"]

        assert "EARLIER CONVERSATION" in prompt
        assert "Where is the JWT generated?" in prompt
        assert "In src/auth/token.py." in prompt

    def test_history_is_trimmed_to_the_configured_window(self, app_settings) -> None:
        history = [
            ChatTurn(role="user" if index % 2 == 0 else "assistant", content=f"turn-{index}")
            for index in range(20)
        ]
        prompt = self._capture_prompt("What now?", history)["prompt"]

        assert "turn-19" in prompt
        assert "turn-0" not in prompt
        section = prompt[prompt.index("EARLIER CONVERSATION") : prompt.index("CONTEXT —")]
        assert section.count("\n") <= app_settings.max_history_turns + 2

    def test_context_is_capped_so_the_window_cannot_overflow(self) -> None:
        """TC_CHAT_003 — long inputs cannot blow past the model's context."""
        huge = [
            RetrievedChunk(
                text="y = 2\n" * 4000,
                file_path=f"src/file_{index}.py",
                language="python",
                chunk_index=0,
                start_line=1,
                end_line=4000,
                distance=0.3 + index / 100,
            )
            for index in range(20)
        ]
        context = rag_service._format_context(huge)
        assert len(context) <= 30_000

    def test_directory_outline_is_supplied_for_structure_questions(self) -> None:
        """TC_AI_002 — folder-structure answers get the tree, not just chunks."""
        prompt = self._capture_prompt("Explain the folder structure")["prompt"]
        assert "DIRECTORY OUTLINE" in prompt
        assert "src/api/" in prompt


class TestSummaryGeneration:
    """Module 10 — repository summary (TC_SUM_001) and caching."""

    def test_summary_sweeps_multiple_facets_and_caches(self) -> None:
        record = make_record()
        calls: list[str] = []

        def fake_retrieve(_record, query, _top_k, **_kwargs):
            calls.append(query)
            return make_hits()

        with (
            patch("app.services.indexing_service.IndexingService.require_ready", return_value=record),
            patch("app.services.rag_service.RagService._retrieve", side_effect=fake_retrieve),
            patch("app.services.llm_service.LLMService.generate", return_value="## Overview\nA demo service."),
            patch("app.services.index_cache.IndexCache.save_summary") as save,
        ):
            response = rag_service.summarize_repository("owner__repo")

        assert len(calls) == len(prompts.SUMMARY_SEED_QUERIES) > 5
        assert "## Overview" in response.summary
        assert response.cached is False
        assert response.sources
        save.assert_called_once()

    def test_cached_summary_skips_the_llm(self) -> None:
        record = make_record()
        record.summary = "## Overview\nCached briefing."

        with (
            patch("app.services.indexing_service.IndexingService.require_ready", return_value=record),
            patch("app.services.llm_service.LLMService.generate") as generate,
        ):
            response = rag_service.summarize_repository("owner__repo")

        generate.assert_not_called()
        assert response.cached is True
        assert response.summary == "## Overview\nCached briefing."

    def test_refresh_forces_regeneration(self) -> None:
        record = make_record()
        record.summary = "stale"

        with (
            patch("app.services.indexing_service.IndexingService.require_ready", return_value=record),
            patch("app.services.rag_service.RagService._retrieve", return_value=make_hits()),
            patch("app.services.llm_service.LLMService.generate", return_value="fresh") as generate,
            patch("app.services.index_cache.IndexCache.save_summary"),
        ):
            response = rag_service.summarize_repository("owner__repo", refresh=True)

        generate.assert_called_once()
        assert response.summary == "fresh"

    def test_summary_prompt_demands_grounded_sections(self) -> None:
        instruction = prompts.SUMMARY_SYSTEM_INSTRUCTION
        for heading in ("## Overview", "## Tech Stack", "## Architecture", "## Getting Started"):
            assert heading in instruction
        assert "Never invent" in instruction
        assert prompts.NO_ANSWER_SENTINEL in instruction


class TestLlmErrorTranslation:
    """TC_ERR_001 — SDK failures become actionable messages."""

    @pytest.mark.parametrize(
        "raw,expected_fragment",
        [
            ("400 INVALID_ARGUMENT: API key not valid", "Verify GEMINI_API_KEY"),
            ("429 RESOURCE_EXHAUSTED: quota exceeded", "rate limit"),
            ("404 NOT_FOUND: model gemini-x is not found", "unavailable for this key"),
            # The exact wording Google returns for a retired model.
            (
                "404 NOT_FOUND. {'error': {'message': 'This model models/gemini-2.5-flash is "
                "no longer available to new users.'}}",
                "unavailable for this key",
            ),
            ("503 UNAVAILABLE: model is experiencing high traffic", "temporarily overloaded"),
            ("504 DEADLINE_EXCEEDED", "timed out"),
        ],
    )
    def test_messages_are_specific(self, raw: str, expected_fragment: str) -> None:
        from app.services.llm_service import LLMService

        error = LLMService._translate(Exception(raw))
        assert expected_fragment.lower() in error.message.lower()
        assert error.code == "llm_error"

    def test_thinking_level_is_applied_when_configured(self) -> None:
        from app.services.llm_service import LLMService

        with patch.object(settings, "gemini_thinking_level", "minimal"):
            config = LLMService()._build_config(
                system_instruction="s", temperature=None, max_output_tokens=None
            )
        # The SDK normalises the value into a ThinkingLevel enum.
        level = getattr(config.thinking_config, "thinking_level", None)
        assert str(getattr(level, "value", level)).lower() == "minimal"

    def test_thinking_level_is_omitted_by_default(self) -> None:
        from app.services.llm_service import LLMService

        with patch.object(settings, "gemini_thinking_level", ""):
            config = LLMService()._build_config(
                system_instruction="s", temperature=None, max_output_tokens=None
            )
        assert getattr(config, "thinking_config", None) is None

    def test_unsupported_thinking_level_retries_without_it(self) -> None:
        """A model that rejects the setting must still answer."""
        from app.services.llm_service import LLMService

        service = LLMService(model="some-model")
        calls: list[object] = []

        def generate_content(*, model, contents, config):  # noqa: ARG001
            calls.append(getattr(config, "thinking_config", None))
            if len(calls) == 1:
                raise RuntimeError("400 INVALID_ARGUMENT: thinking_level not supported")

            class Response:
                text = "Recovered answer."
                candidates = []

            return Response()

        with (
            patch.object(settings, "gemini_thinking_level", "minimal"),
            patch("app.services.llm_service.LLMService.is_configured", new=True),
            patch.object(LLMService, "_ensure_client") as ensure,
        ):
            ensure.return_value.models.generate_content = generate_content
            answer = service.generate(prompt="p", system_instruction="s")

        assert answer == "Recovered answer."
        assert len(calls) == 2
        assert calls[0] is not None and calls[1] is None

    def test_empty_model_response_is_reported(self) -> None:
        from app.core.exceptions import LLMError
        from app.services.llm_service import llm_service

        class EmptyResponse:
            text = ""
            candidates = []

        with (
            patch("app.services.llm_service.LLMService.is_configured", new=True),
            patch("app.services.llm_service.LLMService._ensure_client") as ensure,
        ):
            ensure.return_value.models.generate_content.return_value = EmptyResponse()
            with pytest.raises(LLMError) as excinfo:
                llm_service.generate(prompt="p", system_instruction="s")

        assert "empty response" in str(excinfo.value).lower()
