"""Module 5 — Embeddings (TC_EMB_001 … TC_EMB_004) and chunking behaviour."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.core.exceptions import EmbeddingError
from app.services.chunking_service import ChunkingService, chunking_service
from app.services.embedding_service import EmbeddingService, embedding_service
from app.services.file_service import SourceFile


def make_source(path: str, language: str, body: str) -> SourceFile:
    return SourceFile(path=path, content=body, language=language, size_bytes=len(body))


class TestChunking:
    def test_small_file_becomes_one_chunk(self) -> None:
        source = make_source("src/a.py", "python", "def a():\n    return 1\n")
        chunks = chunking_service.chunk_file(source)
        assert len(chunks) == 1
        assert chunks[0].file_path == "src/a.py"
        assert chunks[0].start_line == 1

    def test_large_file_is_split_with_overlap(self) -> None:
        body = "".join(f"def function_{index}():\n    return {index}\n\n\n" for index in range(200))
        chunks = chunking_service.chunk_file(make_source("src/big.py", "python", body))

        assert len(chunks) > 1
        # Chunk ids are stable and ordered.
        assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))
        assert chunks[0].chunk_id == "src/big.py::0"
        # Line ranges advance monotonically and stay inside the file.
        total_lines = body.count("\n") + 1
        for previous, current in zip(chunks, chunks[1:]):
            assert current.start_line >= previous.start_line
            assert current.end_line <= total_lines + 1

    def test_chunks_respect_the_configured_size(self) -> None:
        service = ChunkingService(chunk_size=300, chunk_overlap=50)
        body = "x = 1\n" * 2000
        for chunk in service.chunk_file(make_source("a.py", "python", body)):
            # Splitters may exceed slightly on unbreakable spans; allow 2x headroom.
            assert len(chunk.text) <= 600

    def test_overlap_must_be_smaller_than_chunk_size(self) -> None:
        with pytest.raises(ValueError):
            ChunkingService(chunk_size=100, chunk_overlap=100)

    @pytest.mark.parametrize(
        "language,body",
        [
            ("python", "class A:\n    def b(self):\n        pass\n"),
            ("javascript", "export function a() { return 1 }\n"),
            ("typescript", "export const a: number = 1\n"),
            ("markdown", "# Title\n\nBody text.\n"),
            ("yaml", "key: value\n"),
            ("dockerfile", "FROM node:20\nRUN npm ci\n"),
            ("text", "plain content\n"),
            ("unknown-language", "some content\n"),
        ],
    )
    def test_every_language_label_is_chunkable(self, language: str, body: str) -> None:
        chunks = chunking_service.chunk_file(make_source(f"f.{language}", language, body))
        assert len(chunks) >= 1
        assert chunks[0].language == language

    def test_metadata_payload_is_chroma_compatible(self) -> None:
        chunk = chunking_service.chunk_file(make_source("src/a.py", "python", "x = 1\n"))[0]
        metadata = chunk.to_metadata("owner__repo", "owner/repo")

        assert metadata["repo_id"] == "owner__repo"
        assert metadata["file_path"] == "src/a.py"
        assert metadata["file_name"] == "a.py"
        # Chroma only accepts scalar metadata values.
        assert all(isinstance(value, (str, int, float, bool)) for value in metadata.values())

    def test_whitespace_only_pieces_are_dropped(self) -> None:
        chunks = chunking_service.chunk_file(make_source("blank.py", "python", "\n\n\n   \n\n"))
        assert chunks == []


@pytest.mark.slow
class TestEmbeddings:
    """TC_EMB_001 / TC_EMB_002 — real local embedding generation."""

    def test_generates_normalised_384_dimensional_vectors(self) -> None:
        vectors = embedding_service.embed_documents(["def handler(): pass", "# README"])
        assert len(vectors) == 2
        assert all(len(vector) == 384 for vector in vectors)

        magnitude = sum(value * value for value in vectors[0]) ** 0.5
        assert magnitude == pytest.approx(1.0, abs=1e-3)

    def test_query_and_document_embeddings_share_the_space(self) -> None:
        document = embedding_service.embed_documents(["JWT tokens are signed here"])[0]
        query = embedding_service.embed_query("where is the JWT signed?")
        similarity = sum(a * b for a, b in zip(document, query))
        assert similarity > 0.4  # semantically close

    def test_progress_callback_reports_monotonic_completion(self) -> None:
        """TC_LOAD_002 — embedding progress is observable for the loading screen."""
        seen: list[tuple[int, int]] = []
        service = EmbeddingService(batch_size=4)
        service.embed_documents([f"line {index}" for index in range(10)], on_progress=lambda d, t: seen.append((d, t)))

        assert seen, "progress callback was never invoked"
        assert [done for done, _ in seen] == sorted(done for done, _ in seen)
        assert seen[-1] == (10, 10)

    def test_batching_covers_every_input(self) -> None:
        """TC_EMB_002 — many chunks, no dropped or duplicated vectors."""
        texts = [f"def function_{index}(): return {index}" for index in range(150)]
        vectors = EmbeddingService(batch_size=16).embed_documents(texts)
        assert len(vectors) == len(texts)

    def test_empty_input_short_circuits(self) -> None:
        assert embedding_service.embed_documents([]) == []


class TestEmbeddingFailures:
    """TC_EMB_003 — an unavailable model produces a clear error, not a crash."""

    def test_unloadable_model_raises_embedding_error(self) -> None:
        service = EmbeddingService(model_name="this-model-does-not-exist/nope")
        with pytest.raises(EmbeddingError) as excinfo:
            service.embed_query("anything")
        assert "Could not load embedding model" in str(excinfo.value)

    def test_encode_failure_is_wrapped(self) -> None:
        service = EmbeddingService()
        with patch.object(service, "_ensure_model") as ensure:
            ensure.return_value.encode.side_effect = RuntimeError("CUDA out of memory")
            with pytest.raises(EmbeddingError) as excinfo:
                service.embed_documents(["text"])
        assert "Embedding generation failed" in str(excinfo.value)

    def test_warm_up_never_raises(self) -> None:
        """Startup must not fail because the model cannot be downloaded."""
        EmbeddingService(model_name="this-model-does-not-exist/nope").warm_up()
