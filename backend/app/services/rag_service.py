"""Retrieval-Augmented Generation orchestration.

Question answering flow::

    question -> embed -> similarity search (scoped to the repository)
             -> assemble a cited CONTEXT block -> Gemini -> answer + sources

The whole repository is never sent to the LLM: only the retrieved chunks are.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime

from app.core.config import settings
from app.models.schemas import (
    AskRequest,
    AskResponse,
    ChatTurn,
    SourceReference,
    SummaryResponse,
)
from app.services import prompts
from app.services.embedding_service import embedding_service
from app.services.index_cache import IndexRecord, index_cache
from app.services.indexing_service import indexing_service
from app.services.llm_service import llm_service
from app.services.vector_store import RetrievedChunk, vector_store

logger = logging.getLogger(__name__)

# Characters of a chunk kept in the citation snippet shown in the UI.
_SNIPPET_LIMIT = 420
# Upper bound on characters handed to the LLM as context (keeps us well inside
# the model window and keeps latency predictable).
_MAX_CONTEXT_CHARS = 28_000


class RagService:
    """Answers questions and writes briefings from indexed repository vectors."""

    # -- question answering --------------------------------------------------

    def answer_question(self, request: AskRequest) -> AskResponse:
        """Retrieve relevant chunks and produce a grounded, cited answer."""
        started = time.perf_counter()
        record = indexing_service.require_ready(request.repo_id)
        top_k = request.top_k or settings.retrieval_top_k

        hits = self._retrieve(record, request.question, top_k)

        if not hits:
            # Short-circuit: with no context, the honest answer is the sentinel.
            logger.info("No relevant chunks for %r in %s", request.question, record.full_name)
            return AskResponse(
                repo_id=record.repo_id,
                question=request.question,
                answer=prompts.NO_ANSWER_SENTINEL,
                sources=[],
                grounded=False,
                model=llm_service.model,
                retrieved_chunks=0,
                elapsed_ms=self._elapsed_ms(started),
            )

        prompt = prompts.build_qa_prompt(
            repo_full_name=record.full_name,
            question=request.question,
            context=self._format_context(hits),
            history=llm_service.chat_history_as_text(request.history),
            tree_outline=self._truncate(record.tree_outline, 2_500),
        )
        answer = llm_service.generate(
            prompt=prompt,
            system_instruction=prompts.QA_SYSTEM_INSTRUCTION,
        )

        grounded = prompts.NO_ANSWER_SENTINEL.lower() not in answer.lower()
        return AskResponse(
            repo_id=record.repo_id,
            question=request.question,
            answer=answer,
            # Citations are pointless when the model reports no answer.
            sources=self._to_references(hits) if grounded else [],
            grounded=grounded,
            model=llm_service.model,
            retrieved_chunks=len(hits),
            elapsed_ms=self._elapsed_ms(started),
        )

    # -- repository briefing -------------------------------------------------

    def summarize_repository(self, repo_id: str, *, refresh: bool = False) -> SummaryResponse:
        """Generate (or return the cached) onboarding briefing for a repository."""
        record = indexing_service.require_ready(repo_id)

        if record.summary and not refresh:
            return SummaryResponse(
                repo_id=record.repo_id,
                full_name=record.full_name,
                summary=record.summary,
                sources=[],
                model=llm_service.model,
                cached=True,
                generated_at=record.summary_generated_at or record.indexed_at,
            )

        # Sweep several facets of the repository so the briefing is not README-only.
        collected: dict[str, RetrievedChunk] = {}
        for query in prompts.SUMMARY_SEED_QUERIES:
            for hit in self._retrieve(record, query, settings.summary_top_k, relax=True):
                key = f"{hit.file_path}::{hit.chunk_index}"
                if key not in collected or hit.distance < collected[key].distance:
                    collected[key] = hit

        hits = sorted(collected.values(), key=lambda hit: hit.distance)
        if not hits:
            summary = prompts.NO_ANSWER_SENTINEL
        else:
            prompt = prompts.build_summary_prompt(
                repo_full_name=record.full_name,
                description=record.metadata.description or "",
                context=self._format_context(hits),
                tree_outline=self._truncate(record.tree_outline, 4_000),
            )
            summary = llm_service.generate(
                prompt=prompt,
                system_instruction=prompts.SUMMARY_SYSTEM_INSTRUCTION,
                max_output_tokens=max(settings.gemini_max_output_tokens, 2_048),
            )
            index_cache.save_summary(repo_id, summary)

        return SummaryResponse(
            repo_id=record.repo_id,
            full_name=record.full_name,
            summary=summary,
            sources=self._to_references(hits[:8]),
            model=llm_service.model,
            cached=False,
            generated_at=datetime.now(),
        )

    # -- internals -----------------------------------------------------------

    def _retrieve(
        self,
        record: IndexRecord,
        query: str,
        top_k: int,
        *,
        relax: bool = False,
    ) -> list[RetrievedChunk]:
        """Embed ``query`` and search the repository's collection."""
        query_embedding = embedding_service.embed_query(query)
        return vector_store.similarity_search(
            collection_name=record.collection_name,
            query_embedding=query_embedding,
            top_k=top_k,
            # Summaries cast a wider net; precision matters less than coverage.
            max_distance=2.0 if relax else None,
        )

    def _format_context(self, hits: list[RetrievedChunk]) -> str:
        """Render hits as labelled, file-attributed passages within a char budget."""
        passages: list[str] = []
        budget = _MAX_CONTEXT_CHARS

        for index, hit in enumerate(hits, start=1):
            header = (
                f"[{index}] FILE: {hit.file_path} "
                f"(lines {hit.start_line}-{hit.end_line}, language: {hit.language})"
            )
            body = hit.text
            block = f"{header}\n```{hit.language}\n{body}\n```"

            if len(block) > budget:
                remaining = budget - len(header) - 16
                if remaining < 200:
                    break
                block = f"{header}\n```{hit.language}\n{body[:remaining]}\n... (truncated)\n```"

            passages.append(block)
            budget -= len(block)
            if budget <= 0:
                break

        return prompts.build_context_block(passages)

    @staticmethod
    def _to_references(hits: list[RetrievedChunk]) -> list[SourceReference]:
        """Convert hits to citations, keeping the best hit per file first."""
        references: list[SourceReference] = []
        seen: set[str] = set()

        for hit in hits:
            key = f"{hit.file_path}::{hit.chunk_index}"
            if key in seen:
                continue
            seen.add(key)
            snippet = hit.text.strip()
            references.append(
                SourceReference(
                    file_path=hit.file_path,
                    language=hit.language,
                    chunk_index=hit.chunk_index,
                    start_line=hit.start_line or None,
                    end_line=hit.end_line or None,
                    relevance=round(hit.relevance, 4),
                    snippet=(
                        snippet[:_SNIPPET_LIMIT] + "..."
                        if len(snippet) > _SNIPPET_LIMIT
                        else snippet
                    ),
                )
            )
        return references

    @staticmethod
    def _truncate(text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        return f"{text[:limit]}\n... (outline truncated)"

    @staticmethod
    def _elapsed_ms(started: float) -> int:
        return int((time.perf_counter() - started) * 1000)


rag_service = RagService()

__all__ = ["RagService", "rag_service", "ChatTurn"]
