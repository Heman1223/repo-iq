"""End-to-end pipeline tests against a real repository.

Covers Module 3 (cloning), Module 6 (vector database), Module 9 (code search),
Module 11 (progress reporting) and Module 13 (performance), plus the reuse and
duplicate-indexing behaviour from Module 5.

Marked ``network`` because a real GitHub clone and a local embedding pass are
required. Run with:  ``pytest -m network``
"""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest
from git import GitCommandError

from app.core.exceptions import CloneError, PrivateRepositoryError, RepositoryNotFound
from app.models.schemas import IndexStage
from app.services.embedding_service import embedding_service
from app.services.git_service import git_service
from app.services.index_cache import IndexCache, index_cache
from app.services.indexing_service import indexing_service
from app.services.vector_store import vector_store
from app.utils.repo_url import parse_github_url

# Small, stable, public repository with real source files in several languages.
TEST_REPO_URL = "https://github.com/pallets/click"

pytestmark = pytest.mark.network


@pytest.fixture(scope="module")
def indexed_repo():
    """Index the test repository once and share it across this module."""
    repo, _, needs_indexing = indexing_service.prepare(TEST_REPO_URL, force=True)
    assert needs_indexing is True

    started = time.perf_counter()
    indexing_service.run(repo, force=True)
    elapsed = time.perf_counter() - started

    status = indexing_service.get_status(repo.repo_id)
    if status.stage is not IndexStage.READY:
        pytest.fail(f"indexing failed: {status.error_code} — {status.error_message}")

    return {"repo": repo, "status": status, "elapsed": elapsed}


class TestClone:
    """TC_CLONE_001 / TC_CLONE_002 — cloning succeeds and is bounded."""

    def test_clone_small_repository(self) -> None:
        repo = parse_github_url("https://github.com/octocat/Hello-World")
        try:
            result = git_service.clone(repo, force=True)
            assert result.path.exists()
            assert (result.path / ".git").exists()
            assert result.head_commit
            assert result.default_branch
        finally:
            git_service.cleanup(repo)
        assert not git_service.local_path(repo).exists()

    def test_clone_is_shallow(self) -> None:
        """TC_CLONE_002 — depth-1 keeps large repositories fast."""
        repo = parse_github_url("https://github.com/pallets/jinja")
        try:
            git_service.clone(repo, force=True)
            from git import Repo

            # Closed explicitly: an open handle would block cleanup on Windows.
            with Repo(str(git_service.local_path(repo))) as repository:
                assert len(list(repository.iter_commits())) == 1
        finally:
            git_service.cleanup(repo)
        assert not git_service.local_path(repo).exists()


class TestCloneFailures:
    """TC_CLONE_003 / TC_CLONE_005 / TC_REPO_005 — failures are translated."""

    def test_nonexistent_repository_is_reported_as_not_found(self) -> None:
        repo = parse_github_url("https://github.com/octocat/this-repo-does-not-exist-xyz-42")
        with pytest.raises((RepositoryNotFound, PrivateRepositoryError, CloneError)):
            git_service.clone(repo, force=True)

    def test_network_failure_is_translated(self) -> None:
        """TC_CLONE_003 / TC_ERR_004 — a dropped connection yields a clean error."""
        repo = parse_github_url("https://github.com/pallets/click")
        failure = GitCommandError(
            command=["git", "clone"],
            status=128,
            stderr="fatal: unable to access: Could not resolve host: github.com",
        )
        with patch("app.services.git_service.Repo.clone_from", side_effect=failure):
            with pytest.raises(CloneError) as excinfo:
                git_service.clone(repo, force=True)
        assert "Network error" in excinfo.value.message

    def test_authentication_failure_maps_to_private_repository(self) -> None:
        """TC_REPO_005 — a private repository is named as such."""
        repo = parse_github_url("https://github.com/someorg/private-thing")
        failure = GitCommandError(
            command=["git", "clone"],
            status=128,
            stderr="fatal: Authentication failed for 'https://github.com/someorg/private-thing'",
        )
        with patch("app.services.git_service.Repo.clone_from", side_effect=failure):
            with pytest.raises(PrivateRepositoryError):
                git_service.clone(repo, force=True)

    def test_failed_clone_leaves_no_partial_directory(self) -> None:
        repo = parse_github_url("https://github.com/someorg/private-thing")
        failure = GitCommandError(command=["git", "clone"], status=128, stderr="fatal: not found")
        with patch("app.services.git_service.Repo.clone_from", side_effect=failure):
            with pytest.raises(Exception):
                git_service.clone(repo, force=True)
        assert not git_service.local_path(repo).exists()


class TestIndexingPipeline:
    """Modules 3-6 + 11 — the whole pipeline, observed through its own reporting."""

    def test_reaches_ready_with_populated_statistics(self, indexed_repo) -> None:
        stats = indexed_repo["status"].stats
        assert stats is not None
        assert stats.total_files_indexed > 20
        assert stats.total_chunks > stats.total_files_indexed
        assert stats.total_files_skipped >= 0
        assert stats.embedding_dimensions == 384
        assert stats.indexing_seconds > 0
        assert stats.indexed_at is not None

    def test_vector_count_matches_chunk_count(self, indexed_repo) -> None:
        """TC_DB_001 — every chunk produced a stored vector."""
        stats = indexed_repo["status"].stats
        assert stats.vector_count == stats.total_chunks

    def test_language_detection_and_structure(self, indexed_repo) -> None:
        """TC_SUM_002 — languages are detected; TC_SUM_003 — structure captured."""
        stats = indexed_repo["status"].stats
        assert "python" in stats.languages
        assert stats.languages["python"] > 0
        assert any(entry.endswith("/") for entry in stats.top_level_entries)

    def test_ignored_directories_never_reach_the_index(self, indexed_repo) -> None:
        """TC_FILE_004 / TC_FILE_005 verified on a real repository."""
        record = index_cache.get(indexed_repo["repo"].repo_id)
        outline = record.tree_outline
        assert "node_modules" not in outline
        assert ".git/" not in outline

    def test_clone_is_deleted_after_indexing(self, indexed_repo) -> None:
        """Working copies are disposable once vectors are written."""
        assert not git_service.local_path(indexed_repo["repo"]).exists()

    def test_progress_stages_are_terminal_and_complete(self, indexed_repo) -> None:
        """TC_LOAD_001 / TC_LOAD_002 — the job ends at 100% and is marked ready."""
        status = indexed_repo["status"]
        assert status.stage is IndexStage.READY
        assert status.progress == 1.0
        assert status.is_ready is True
        assert status.error_code is None

    @pytest.mark.parametrize("_", range(1))
    def test_indexing_completes_within_a_reasonable_time(self, indexed_repo, _) -> None:
        """TC_PERF_001 — a few-hundred-file repository indexes in minutes, not hours."""
        stats = indexed_repo["status"].stats
        chunks_per_second = stats.total_chunks / max(stats.indexing_seconds, 0.001)
        assert chunks_per_second > 1.0, f"only {chunks_per_second:.2f} chunks/s"
        assert indexed_repo["elapsed"] < 600


class TestReuseAndDeduplication:
    """TC_CLONE_004 / TC_EMB_004 / TC_DB_003 — index once, reuse thereafter."""

    def test_second_submission_reuses_the_existing_index(self, indexed_repo) -> None:
        repo, status, needs_indexing = indexing_service.prepare(TEST_REPO_URL)
        assert needs_indexing is False
        assert status.is_ready is True
        assert status.reused_existing_index is True
        assert repo.repo_id == indexed_repo["repo"].repo_id

    def test_reindexing_does_not_duplicate_vectors(self, indexed_repo) -> None:
        """TC_EMB_004 — chunk ids are deterministic, so a rebuild cannot double up."""
        repo = indexed_repo["repo"]
        before = vector_store.count(repo.collection_name)

        indexing_service.run(repo, force=True)
        after = vector_store.count(repo.collection_name)

        assert after == before

    def test_index_survives_a_fresh_cache_instance(self, indexed_repo, app_settings) -> None:
        """TC_DB_003 — restart persistence: a new cache reads the same record."""
        reloaded = IndexCache(app_settings.index_cache_file)
        record = reloaded.get(indexed_repo["repo"].repo_id)

        assert record is not None
        assert record.full_name == "pallets/click"
        assert record.stats.total_chunks > 0
        # And the vectors are still queryable from disk.
        assert vector_store.count(record.collection_name) == record.stats.total_chunks


class TestRetrieval:
    """Module 9 — code search (TC_CODE_001 … TC_CODE_004) and TC_DB_002."""

    def _search(self, repo, question: str, top_k: int = 5):
        record = index_cache.get(repo.repo_id)
        return vector_store.similarity_search(
            collection_name=record.collection_name,
            query_embedding=embedding_service.embed_query(question),
            top_k=top_k,
        )

    def test_returns_relevant_chunks_with_citable_metadata(self, indexed_repo) -> None:
        """TC_DB_002 — retrieval yields usable, attributable results."""
        hits = self._search(indexed_repo["repo"], "how are command line options parsed?")

        assert hits, "no chunks retrieved"
        for hit in hits:
            assert hit.file_path
            assert hit.text.strip()
            assert 0.0 <= hit.relevance <= 1.0
            assert hit.start_line >= 1
            assert hit.end_line >= hit.start_line

    def test_results_are_ordered_by_similarity(self, indexed_repo) -> None:
        hits = self._search(indexed_repo["repo"], "decorator that defines a command group")
        distances = [hit.distance for hit in hits]
        assert distances == sorted(distances)

    @pytest.mark.parametrize(
        "question,expected_fragment",
        [
            ("how are command line arguments parsed?", "click/"),
            ("where are terminal colours handled?", "click/"),
            ("how is user input prompted for?", "click/"),
        ],
    )
    def test_topical_questions_surface_source_files(
        self, indexed_repo, question: str, expected_fragment: str
    ) -> None:
        """TC_CODE_001 / TC_CODE_003 — searches land in the right part of the tree."""
        hits = self._search(indexed_repo["repo"], question, top_k=8)
        assert any(expected_fragment in hit.file_path for hit in hits), (
            f"{question!r} returned {[hit.file_path for hit in hits]}"
        )

    def test_retrieval_is_scoped_to_the_requested_repository(self, indexed_repo) -> None:
        """A query against an unknown collection returns nothing, never another repo's data."""
        hits = vector_store.similarity_search(
            collection_name="repo-does-not-exist-00000000",
            query_embedding=embedding_service.embed_query("anything"),
            top_k=5,
        )
        assert hits == []

    def test_distance_threshold_discards_obvious_noise(self, indexed_repo) -> None:
        """TC_CODE_004 — a hard threshold still filters unrelated matches."""
        record = index_cache.get(indexed_repo["repo"].repo_id)
        hits = vector_store.similarity_search(
            collection_name=record.collection_name,
            query_embedding=embedding_service.embed_query("sourdough bread proofing schedule"),
            top_k=5,
            max_distance=0.5,
        )
        assert hits == []

    def test_repeated_queries_are_consistently_fast(self, indexed_repo) -> None:
        """TC_PERF_002 — retrieval latency does not degrade across calls."""
        durations = []
        for _ in range(5):
            started = time.perf_counter()
            self._search(indexed_repo["repo"], "how is the CLI context created?")
            durations.append(time.perf_counter() - started)

        assert max(durations) < 2.0
        # No systematic slowdown: the last call is not dramatically worse than the first.
        assert durations[-1] < durations[0] * 4 + 0.25


class TestApiIntegration:
    """The same flow, exercised through HTTP (TC_API_001 / TC_API_005 / TC_API_006)."""

    def test_clone_endpoint_reports_an_already_indexed_repository(self, client, indexed_repo) -> None:
        response = client.post("/clone", json={"repo_url": TEST_REPO_URL})
        assert response.status_code == 202

        payload = response.json()
        assert payload["already_indexed"] is True
        assert payload["status"]["is_ready"] is True
        assert payload["repo_id"] == indexed_repo["repo"].repo_id

    def test_status_endpoint_returns_dashboard_data(self, client, indexed_repo) -> None:
        """TC_API_005 / TC_SUM_003 — everything the dashboard renders is present."""
        response = client.get("/status", params={"repo_id": indexed_repo["repo"].repo_id})
        assert response.status_code == 200

        payload = response.json()
        assert payload["stage"] == "ready"
        assert payload["metadata"]["full_name"] == "pallets/click"
        assert payload["metadata"]["default_branch"]
        assert payload["stats"]["total_chunks"] > 0
        assert payload["stats"]["embedding_model"].endswith("all-MiniLM-L6-v2")

    def test_repository_listing_includes_the_indexed_repository(self, client, indexed_repo) -> None:
        entries = client.get("/repositories").json()["repositories"]
        assert any(entry["repo_id"] == indexed_repo["repo"].repo_id for entry in entries)


class TestDeletion:
    """TC_DB_004 — deleting a repository clears vectors and cache together."""

    def test_delete_removes_vectors_and_registry_entry(self, client) -> None:
        # Index a tiny repository specifically so it can be destroyed.
        repo, _, _ = indexing_service.prepare("https://github.com/octocat/Hello-World", force=True)
        indexing_service.run(repo, force=True)

        status = indexing_service.get_status(repo.repo_id)
        if status.stage is not IndexStage.READY:
            pytest.skip(f"could not index fixture repository: {status.error_message}")

        assert vector_store.count(repo.collection_name) > 0

        response = client.delete(f"/repositories/{repo.repo_id}")
        assert response.status_code == 204

        assert vector_store.count(repo.collection_name) == 0
        assert index_cache.get(repo.repo_id) is None
        assert client.get("/status", params={"repo_id": repo.repo_id}).status_code == 404
