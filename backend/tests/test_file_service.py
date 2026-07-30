"""Module 4 — File processing (TC_FILE_001 … TC_FILE_007) and TC_ERR_005."""

from __future__ import annotations

from pathlib import Path

from app.services.file_service import file_service


class TestSupportedFiles:
    """TC_FILE_001 / TC_FILE_002 / TC_FILE_003 — source files are parsed."""

    def test_reads_python_javascript_typescript_and_markdown(self, sample_repo_tree: Path) -> None:
        result = file_service.scan_repository(sample_repo_tree)
        by_path = {source.path: source for source in result.files}

        assert by_path["src/main.py"].language == "python"          # TC_FILE_001
        assert by_path["src/app.js"].language == "javascript"       # TC_FILE_002
        assert by_path["src/ui/Button.tsx"].language == "typescript"
        assert by_path["README.md"].language == "markdown"          # TC_FILE_003
        assert "A sample project." in by_path["README.md"].content

    def test_reads_manifests_and_infrastructure_files(self, sample_repo_tree: Path) -> None:
        paths = {source.path for source in file_service.scan_repository(sample_repo_tree).files}
        assert {"requirements.txt", "package.json", "Dockerfile", ".env.example",
                "config/settings.yaml", "docs/guide.rst"} <= paths

    def test_line_counts_and_sizes_are_populated(self, sample_repo_tree: Path) -> None:
        for source in file_service.scan_repository(sample_repo_tree).files:
            assert source.size_bytes > 0
            assert source.line_count >= 1
            assert source.content.strip()


class TestIgnoredContent:
    """TC_FILE_004 / TC_FILE_005 / TC_FILE_006 / TC_ERR_005 — noise is excluded."""

    def test_excludes_dependency_build_and_vcs_directories(self, sample_repo_tree: Path) -> None:
        paths = {source.path for source in file_service.scan_repository(sample_repo_tree).files}

        assert not any(path.startswith("node_modules/") for path in paths)   # TC_FILE_004
        assert not any(path.startswith(".git/") for path in paths)           # TC_FILE_005
        assert not any(path.startswith(("dist/", "build/", "coverage/", "__pycache__/"))
                       for path in paths)

    def test_excludes_lockfiles(self, sample_repo_tree: Path) -> None:
        paths = {source.path for source in file_service.scan_repository(sample_repo_tree).files}
        assert {"package-lock.json", "yarn.lock", "pnpm-lock.yaml"}.isdisjoint(paths)

    def test_excludes_binaries_media_and_minified_bundles(self, sample_repo_tree: Path) -> None:
        """TC_FILE_006 + TC_ERR_005 — skipped safely, never a crash."""
        paths = {source.path for source in file_service.scan_repository(sample_repo_tree).files}
        assert {"assets/logo.png", "assets/clip.mp4", "lib/native.so",
                "static/app.min.js", "data/blob.bin"}.isdisjoint(paths)

    def test_excludes_empty_files(self, sample_repo_tree: Path) -> None:
        paths = {source.path for source in file_service.scan_repository(sample_repo_tree).files}
        assert "empty.py" not in paths

    def test_skip_counter_reflects_rejections(self, sample_repo_tree: Path) -> None:
        result = file_service.scan_repository(sample_repo_tree)
        assert result.skipped > 0
        assert result.scanned == len(result.files) + result.skipped


class TestEmptyRepository:
    """TC_FILE_007 — a repository with nothing readable reports zero files."""

    def test_no_readable_files(self, tmp_path: Path) -> None:
        root = tmp_path / "binaries-only"
        (root / "assets").mkdir(parents=True)
        (root / "assets" / "a.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00")
        (root / "assets" / "b.zip").write_bytes(b"PK\x03\x04\x00")

        result = file_service.scan_repository(root)
        assert result.files == []
        assert result.skipped >= 2

    def test_completely_empty_directory(self, tmp_path: Path) -> None:
        root = tmp_path / "void"
        root.mkdir()
        result = file_service.scan_repository(root)
        assert result.files == []
        assert result.scanned == 0


class TestLimits:
    """Configured caps are enforced (protects against pathological repositories)."""

    def test_oversized_file_is_skipped(self, tmp_path: Path, app_settings) -> None:
        root = tmp_path / "big"
        root.mkdir()
        (root / "huge.py").write_text("x = 1\n" * app_settings.max_file_size_bytes, encoding="utf-8")
        (root / "small.py").write_text("y = 2\n", encoding="utf-8")

        paths = {source.path for source in file_service.scan_repository(root).files}
        assert paths == {"small.py"}


class TestOutlines:
    """Structure helpers feeding the dashboard and the LLM context."""

    def test_top_level_entries_mark_directories(self, sample_repo_tree: Path) -> None:
        entries = file_service.top_level_entries(sample_repo_tree)
        assert "src/" in entries
        assert "README.md" in entries
        assert ".git" not in entries and ".git/" not in entries
        assert "node_modules/" not in entries

    def test_tree_outline_lists_directories_with_files(self, sample_repo_tree: Path) -> None:
        result = file_service.scan_repository(sample_repo_tree)
        outline = file_service.build_tree_outline(sample_repo_tree, result.files)
        assert "src/auth/" in outline
        assert "token.py" in outline
        assert "node_modules" not in outline
