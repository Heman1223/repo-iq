"""Shared pytest fixtures.

Storage paths are redirected to a temporary directory *before* the application
package is imported, so tests never touch the developer's real ChromaDB or
clone directory.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pytest

# --- Isolate all on-disk state before `app.core.config` is imported ----------
_TEST_ROOT = Path(tempfile.mkdtemp(prefix="repoai-tests-"))
os.environ["REPOSITORIES_DIR"] = str(_TEST_ROOT / "repositories")
os.environ["CHROMA_DIR"] = str(_TEST_ROOT / "chroma_db")
os.environ["LOG_LEVEL"] = "WARNING"
# Keep indexing quick: these tests care about behaviour, not throughput.
os.environ["EMBEDDING_BATCH_SIZE"] = "64"

from app.core.config import settings  # noqa: E402
from app.main import app  # noqa: E402


def pytest_sessionfinish(session, exitstatus) -> None:  # noqa: ARG001
    """Remove the temporary storage tree once the whole session ends."""
    shutil.rmtree(_TEST_ROOT, ignore_errors=True)


@pytest.fixture(scope="session")
def test_root() -> Path:
    return _TEST_ROOT


@pytest.fixture(scope="session")
def client():
    """Starlette test client with the real application lifespan."""
    from starlette.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def client_no_raise():
    """Client that returns 500 responses instead of re-raising them.

    Needed to assert on the shape of unhandled-error responses: by default the
    test client re-raises server exceptions rather than letting the handler run.
    """
    from starlette.testclient import TestClient

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def app_settings():
    return settings


@pytest.fixture
def sample_repo_tree(tmp_path: Path) -> Path:
    """A miniature repository exercising every include/exclude rule."""
    root = tmp_path / "repo"

    files: dict[str, bytes] = {
        # --- should be indexed ---
        "README.md": b"# Demo\n\nA sample project.\n",
        "requirements.txt": b"fastapi\nuvicorn\n",
        "Dockerfile": b"FROM python:3.12-slim\nCOPY . /app\n",
        ".env.example": b"SECRET_KEY=changeme\n",
        "package.json": b'{"name": "demo", "dependencies": {"react": "19"}}',
        "src/main.py": b"def main():\n    return 'hello'\n",
        "src/auth/token.py": b"import jwt\n\n\ndef make_token(user):\n    return jwt.encode(user)\n",
        "src/app.js": b"export function boot() { return true }\n",
        "src/ui/Button.tsx": b"export const Button = () => <button />\n",
        "docs/guide.rst": b"Guide\n=====\n",
        "config/settings.yaml": b"debug: false\n",
        # --- must be ignored ---
        "node_modules/left-pad/index.js": b"module.exports = 1\n",
        ".git/config": b"[core]\n",
        "dist/bundle.js": b"console.log(1)\n",
        "build/output.txt": b"built\n",
        "coverage/lcov.info": b"TN:\n",
        "__pycache__/main.cpython-312.pyc": b"\x00\x01binary",
        "package-lock.json": b'{"lockfileVersion": 3}',
        "yarn.lock": b"# yarn lockfile v1\n",
        "pnpm-lock.yaml": b"lockfileVersion: 6\n",
        "assets/logo.png": b"\x89PNG\r\n\x1a\n\x00\x00binary-image",
        "assets/clip.mp4": b"\x00\x00\x00\x18ftypmp42",
        "lib/native.so": b"\x7fELF\x02\x01\x01\x00binary",
        "static/app.min.js": b"var a=1;\n",
        "data/blob.bin": b"\x00\x01\x02\x03\x04",
        "empty.py": b"",
    }

    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    return root
