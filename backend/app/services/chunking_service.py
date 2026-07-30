"""Document chunking built on LangChain's recursive text splitters.

Code files are split with language-aware separators (class/function boundaries
first, then blank lines, then characters) so a chunk rarely cuts a function in
half. Every chunk keeps an overlap with its neighbour to preserve context, and
carries the metadata needed to cite it later.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from functools import lru_cache

from langchain_text_splitters import Language, RecursiveCharacterTextSplitter

from app.core.config import settings
from app.services.file_service import SourceFile

logger = logging.getLogger(__name__)

# Our language labels -> LangChain `Language` members (names differ slightly).
_LANGCHAIN_LANGUAGE: dict[str, str] = {
    "python": "PYTHON",
    "javascript": "JS",
    "typescript": "TS",
    "java": "JAVA",
    "kotlin": "KOTLIN",
    "scala": "SCALA",
    "go": "GO",
    "rust": "RUST",
    "ruby": "RUBY",
    "php": "PHP",
    "c": "C",
    "cpp": "CPP",
    "csharp": "CSHARP",
    "swift": "SWIFT",
    "markdown": "MARKDOWN",
    "rst": "RST",
    "html": "HTML",
    "proto": "PROTO",
    "powershell": "POWERSHELL",
}


@dataclass(slots=True)
class Chunk:
    """A single embeddable unit of repository text."""

    chunk_id: str
    text: str
    file_path: str
    language: str
    chunk_index: int
    start_line: int
    end_line: int

    def to_metadata(self, repo_id: str, repo_full_name: str) -> dict[str, str | int]:
        """Chroma metadata payload (scalars only — that is all Chroma accepts)."""
        return {
            "repo_id": repo_id,
            "repo_full_name": repo_full_name,
            "file_path": self.file_path,
            "file_name": self.file_path.rsplit("/", 1)[-1],
            "language": self.language,
            "chunk_index": self.chunk_index,
            "start_line": self.start_line,
            "end_line": self.end_line,
        }


@dataclass(slots=True)
class ChunkingResult:
    chunks: list[Chunk] = field(default_factory=list)
    files_chunked: int = 0


class ChunkingService:
    """Turns :class:`SourceFile` objects into overlapping, cited chunks."""

    def __init__(
        self,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ) -> None:
        self._chunk_size = chunk_size or settings.chunk_size
        self._chunk_overlap = chunk_overlap or settings.chunk_overlap
        if self._chunk_overlap >= self._chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")

    def chunk_files(self, files: list[SourceFile]) -> ChunkingResult:
        """Chunk every file, preserving order for deterministic chunk ids."""
        result = ChunkingResult()
        for source in files:
            file_chunks = self.chunk_file(source)
            if file_chunks:
                result.chunks.extend(file_chunks)
                result.files_chunked += 1

        logger.info("Created %d chunks from %d files", len(result.chunks), result.files_chunked)
        return result

    def chunk_file(self, source: SourceFile) -> list[Chunk]:
        """Split one file and annotate each piece with its line range."""
        splitter = self._splitter_for(source.language)
        try:
            pieces = splitter.split_text(source.content)
        except Exception as exc:  # pragma: no cover - splitter edge cases
            logger.debug("Falling back to plain splitting for %s: %s", source.path, exc)
            pieces = self._splitter_for("text").split_text(source.content)

        chunks: list[Chunk] = []
        cursor = 0
        for index, piece in enumerate(pieces):
            text = piece.strip("\n")
            if not text.strip():
                continue

            # Locate the piece to derive real line numbers for citations.
            position = source.content.find(piece, cursor)
            if position == -1:
                position = cursor
            cursor = position + max(len(piece) - self._chunk_overlap, 1)

            start_line = source.content.count("\n", 0, position) + 1
            end_line = start_line + piece.count("\n")

            chunks.append(
                Chunk(
                    chunk_id=f"{source.path}::{index}",
                    text=text,
                    file_path=source.path,
                    language=source.language,
                    chunk_index=index,
                    start_line=start_line,
                    end_line=end_line,
                )
            )
        return chunks

    @lru_cache(maxsize=64)
    def _splitter_for(self, language: str) -> RecursiveCharacterTextSplitter:
        """Cached splitter per language (constructing separators is not free)."""
        member = _LANGCHAIN_LANGUAGE.get(language)
        if member is not None and hasattr(Language, member):
            try:
                return RecursiveCharacterTextSplitter.from_language(
                    language=getattr(Language, member),
                    chunk_size=self._chunk_size,
                    chunk_overlap=self._chunk_overlap,
                )
            except Exception:  # pragma: no cover - unsupported in installed version
                logger.debug("No LangChain separators for %s; using generic splitter", language)

        return RecursiveCharacterTextSplitter(
            chunk_size=self._chunk_size,
            chunk_overlap=self._chunk_overlap,
            separators=["\n\n\n", "\n\n", "\n", " ", ""],
            keep_separator=True,
        )


chunking_service = ChunkingService()
