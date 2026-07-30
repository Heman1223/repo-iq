"""Repository file discovery and safe reading.

Responsibilities
----------------
* Walk a cloned repository while pruning noise directories early.
* Keep only text/source files the assistant can reason about.
* Read files defensively: size caps, symlink refusal, binary sniffing and a
  path-traversal check on every candidate.

Repository code is **never executed** — files are only ever opened for reading.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from app.core.config import settings
from app.utils.paths import is_within, relative_posix

logger = logging.getLogger(__name__)

# --- Ignore rules ------------------------------------------------------------

IGNORED_DIRECTORIES: frozenset[str] = frozenset({
    ".git", ".github", ".gitlab", ".svn", ".hg",
    "node_modules", "bower_components", "jspm_packages", ".pnpm-store",
    "venv", ".venv", "env", ".env.d", "virtualenv",
    "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox",
    "dist", "build", "out", "target", "bin", "obj", ".output",
    ".next", ".nuxt", ".svelte-kit", ".astro", ".parcel-cache", ".turbo", ".cache",
    "coverage", "htmlcov", ".nyc_output",
    "vendor", "third_party", "site-packages", "Pods", "gradle", ".gradle",
    ".idea", ".vscode", ".vs", ".terraform", ".serverless",
    "chroma_db", "repositories", ".DS_Store",
})

IGNORED_FILENAMES: frozenset[str] = frozenset({
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "npm-shrinkwrap.json",
    "poetry.lock", "pdm.lock", "pipfile.lock", "cargo.lock", "composer.lock",
    "gemfile.lock", "go.sum", "bun.lockb", "flake.lock", ".ds_store", "thumbs.db",
})

# Binary, media, archive and compiled artefacts.
IGNORED_EXTENSIONS: frozenset[str] = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".ico", ".svg", ".tiff", ".avif",
    ".mp3", ".wav", ".ogg", ".flac", ".mp4", ".mov", ".avi", ".mkv", ".webm",
    ".woff", ".woff2", ".ttf", ".otf", ".eot",
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar", ".jar", ".war",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".pyc", ".pyo", ".pyd", ".so", ".dylib", ".dll", ".exe", ".bin", ".o", ".a",
    ".class", ".wasm", ".node", ".db", ".sqlite", ".sqlite3", ".parquet",
    ".pt", ".pth", ".onnx", ".safetensors", ".h5", ".pkl", ".npy", ".npz",
    ".map", ".min.js", ".min.css", ".lock", ".log", ".pem", ".key", ".crt", ".p12",
})

# --- Allow rules -------------------------------------------------------------

# extension -> canonical language label (also drives code-aware chunking)
EXTENSION_LANGUAGE: dict[str, str] = {
    ".py": "python", ".pyi": "python",
    ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".tsx": "typescript", ".mts": "typescript", ".cts": "typescript",
    ".java": "java", ".kt": "kotlin", ".kts": "kotlin", ".scala": "scala",
    ".go": "go", ".rs": "rust", ".rb": "ruby", ".php": "php",
    ".c": "c", ".h": "c", ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp", ".hpp": "cpp",
    ".cs": "csharp", ".swift": "swift", ".m": "objectivec", ".dart": "dart",
    ".sh": "shell", ".bash": "shell", ".zsh": "shell", ".ps1": "powershell",
    ".sql": "sql", ".graphql": "graphql", ".gql": "graphql", ".proto": "proto",
    ".html": "html", ".htm": "html", ".vue": "vue", ".svelte": "svelte",
    ".css": "css", ".scss": "scss", ".sass": "sass", ".less": "less",
    ".json": "json", ".jsonc": "json", ".yaml": "yaml", ".yml": "yaml",
    ".toml": "toml", ".ini": "ini", ".cfg": "ini", ".conf": "ini", ".properties": "ini",
    ".md": "markdown", ".mdx": "markdown", ".rst": "rst", ".txt": "text",
    ".tf": "terraform", ".tfvars": "terraform", ".gradle": "gradle", ".cmake": "cmake",
    ".ipynb": "json", ".env.example": "dotenv", ".editorconfig": "ini",
}

# Extension-less files that matter for architecture questions.
ALLOWED_FILENAMES: dict[str, str] = {
    "dockerfile": "dockerfile",
    "containerfile": "dockerfile",
    "docker-compose.yml": "yaml",
    "docker-compose.yaml": "yaml",
    "makefile": "makefile",
    "procfile": "text",
    "readme": "markdown",
    "license": "text",
    "notice": "text",
    "changelog": "markdown",
    "contributing": "markdown",
    "requirements.txt": "text",
    "requirements-dev.txt": "text",
    "pipfile": "toml",
    "gemfile": "ruby",
    ".env.example": "dotenv",
    ".env.sample": "dotenv",
    ".env.template": "dotenv",
    ".gitignore": "text",
    ".dockerignore": "text",
    ".nvmrc": "text",
}

_BINARY_SNIFF_BYTES = 4_096


@dataclass(slots=True)
class SourceFile:
    """One readable repository file, ready for chunking."""

    path: str  # repository-relative, POSIX separators
    content: str
    language: str
    size_bytes: int

    @property
    def line_count(self) -> int:
        return self.content.count("\n") + 1


@dataclass(slots=True)
class ScanResult:
    """Outcome of a full repository scan."""

    files: list[SourceFile] = field(default_factory=list)
    scanned: int = 0
    skipped: int = 0
    total_characters: int = 0
    truncated: bool = False

    @property
    def languages(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for source in self.files:
            counts[source.language] = counts.get(source.language, 0) + 1
        return dict(sorted(counts.items(), key=lambda item: item[1], reverse=True))


class FileService:
    """Discovers and reads the indexable subset of a cloned repository."""

    def __init__(self) -> None:
        self._max_file_size = settings.max_file_size_bytes
        self._max_files = settings.max_files_per_repo
        self._max_total_bytes = settings.max_total_bytes

    # -- public API ----------------------------------------------------------

    def scan_repository(self, repo_path: Path) -> ScanResult:
        """Walk ``repo_path`` and return every readable source file."""
        root = repo_path.resolve()
        result = ScanResult()

        for dir_path, dir_names, file_names in os.walk(root, followlinks=False):
            # Prune noise directories in-place so os.walk never descends.
            dir_names[:] = sorted(
                name for name in dir_names
                if name not in IGNORED_DIRECTORIES and not self._is_hidden_build_dir(name)
            )

            for file_name in sorted(file_names):
                result.scanned += 1
                candidate = Path(dir_path) / file_name

                if result.truncated:
                    result.skipped += 1
                    continue

                source = self._read_candidate(root, candidate)
                if source is None:
                    result.skipped += 1
                    continue

                result.files.append(source)
                result.total_characters += len(source.content)

                if (
                    len(result.files) >= self._max_files
                    or result.total_characters >= self._max_total_bytes
                ):
                    result.truncated = True
                    logger.warning(
                        "Scan cap reached for %s (%d files, %d chars)",
                        root.name, len(result.files), result.total_characters,
                    )

        logger.info(
            "Scanned %s: %d files kept, %d skipped", root.name, len(result.files), result.skipped
        )
        return result

    def top_level_entries(self, repo_path: Path, limit: int = 40) -> list[str]:
        """Visible top-level files and directories, for folder-structure answers."""
        entries: list[str] = []
        for child in sorted(repo_path.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
            if child.name in IGNORED_DIRECTORIES or child.name.startswith(".git"):
                continue
            entries.append(f"{child.name}/" if child.is_dir() else child.name)
        return entries[:limit]

    def build_tree_outline(self, repo_path: Path, files: list[SourceFile], limit: int = 220) -> str:
        """Compact indented directory outline used as extra LLM context."""
        directories: dict[str, list[str]] = {}
        for source in files:
            parent = str(Path(source.path).parent).replace("\\", "/")
            directories.setdefault("." if parent == "." else parent, []).append(
                Path(source.path).name
            )

        lines: list[str] = []
        for directory in sorted(directories):
            names = sorted(directories[directory])
            shown = ", ".join(names[:8]) + (f", +{len(names) - 8} more" if len(names) > 8 else "")
            lines.append(f"{directory}/ -> {shown}")
            if len(lines) >= limit:
                lines.append("... (outline truncated)")
                break
        return "\n".join(lines)

    # -- internals -----------------------------------------------------------

    @staticmethod
    def _is_hidden_build_dir(name: str) -> bool:
        """Skip dot-directories except a small set of meaningful ones."""
        return name.startswith(".") and name not in {".github", ".well-known"}

    def _read_candidate(self, root: Path, candidate: Path) -> SourceFile | None:
        """Validate then read one file, or return ``None`` to skip it."""
        # Refuse symlinks outright: they are the classic sandbox escape.
        if candidate.is_symlink() or not is_within(root, candidate):
            return None

        language = self._classify(candidate)
        if language is None:
            return None

        try:
            stat = candidate.stat()
        except OSError:
            return None
        if not candidate.is_file() or stat.st_size == 0 or stat.st_size > self._max_file_size:
            return None

        try:
            raw = candidate.read_bytes()
        except OSError as exc:
            logger.debug("Unreadable file %s: %s", candidate, exc)
            return None

        if b"\x00" in raw[:_BINARY_SNIFF_BYTES]:
            return None

        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("utf-8", errors="replace")
            # Mostly-unmappable content is almost certainly not source code.
            if text.count("�") > len(text) * 0.02:
                return None

        if not text.strip():
            return None

        return SourceFile(
            path=relative_posix(root, candidate),
            content=text,
            language=language,
            size_bytes=stat.st_size,
        )

    @staticmethod
    def _classify(candidate: Path) -> str | None:
        """Return the language label for a file, or ``None`` if unsupported."""
        name = candidate.name.lower()

        if name in IGNORED_FILENAMES:
            return None

        # Composite suffixes such as `.min.js` must be checked before `.js`.
        if any(name.endswith(suffix) for suffix in (".min.js", ".min.css", ".bundle.js", ".d.ts")):
            return None

        if name in ALLOWED_FILENAMES:
            return ALLOWED_FILENAMES[name]

        # `README`, `README.md`, `Dockerfile.prod`, `.env.example` ...
        stem = name.split(".")[0]
        if stem in ALLOWED_FILENAMES and candidate.suffix.lower() not in IGNORED_EXTENSIONS:
            return EXTENSION_LANGUAGE.get(candidate.suffix.lower(), ALLOWED_FILENAMES[stem])

        suffix = candidate.suffix.lower()
        if not suffix or suffix in IGNORED_EXTENSIONS:
            return None
        return EXTENSION_LANGUAGE.get(suffix)


# Module-level singleton: the service is stateless and cheap to share.
file_service = FileService()
