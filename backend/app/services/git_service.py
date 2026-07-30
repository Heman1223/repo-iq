"""Repository cloning with GitPython.

Clones are shallow (``--depth 1``, no tags, blob-filtered) because the assistant
only needs the current working tree. Terminal credential prompts are disabled so
a private repository fails fast instead of hanging the request.
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from git import GitCommandError, Repo

from app.core.config import settings
from app.core.exceptions import CloneError, EmptyRepositoryError, PrivateRepositoryError, RepositoryNotFound
from app.utils.paths import is_within, remove_tree
from app.utils.repo_url import RepoRef

logger = logging.getLogger(__name__)

# Environment that guarantees git never blocks waiting for credentials.
_NON_INTERACTIVE_ENV = {
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_ASKPASS": "echo",
    "GCM_INTERACTIVE": "never",
    "GIT_LFS_SKIP_SMUDGE": "1",
}


@dataclass(slots=True)
class CloneResult:
    path: Path
    default_branch: str
    head_commit: str
    head_message: str


class GitService:
    """Clones public repositories into an isolated workspace directory."""

    def __init__(self) -> None:
        self._root = settings.repositories_dir

    def local_path(self, repo: RepoRef) -> Path:
        """Sandbox directory for ``repo`` (validated to stay under the root)."""
        target = (self._root / repo.repo_id).resolve()
        if not is_within(self._root, target):
            raise CloneError("Refusing to write outside the repositories directory.")
        return target

    def is_cloned(self, repo: RepoRef) -> bool:
        path = self.local_path(repo)
        return (path / ".git").exists()

    def clone(self, repo: RepoRef, *, force: bool = False) -> CloneResult:
        """Clone ``repo``, replacing any previous clone.

        Raises:
            RepositoryNotFound / PrivateRepositoryError: mapped from git's stderr.
            CloneError: any other git failure or timeout.
            EmptyRepositoryError: the repository has no commits.
        """
        self._root.mkdir(parents=True, exist_ok=True)
        target = self.local_path(repo)

        if target.exists():
            if not force and self.is_cloned(repo):
                logger.info("Reusing existing clone at %s", target)
                return self._describe(target)
            logger.info("Removing previous clone at %s", target)
            remove_tree(target)

        # A stalled transfer aborts instead of hanging the request. Passed as
        # GIT_CONFIG_* env vars because GitPython rejects `--config` as unsafe,
        # and unlike `kill_after_timeout` this also works on Windows.
        env = {
            **os.environ,
            **_NON_INTERACTIVE_ENV,
            "GIT_CONFIG_COUNT": "2",
            "GIT_CONFIG_KEY_0": "http.lowSpeedLimit",
            "GIT_CONFIG_VALUE_0": "1000",
            "GIT_CONFIG_KEY_1": "http.lowSpeedTime",
            "GIT_CONFIG_VALUE_1": str(settings.clone_timeout_seconds),
        }
        logger.info("Cloning %s -> %s", repo.clone_url, target)

        # POSIX-only hard timeout; GitPython raises on Windows if this is set.
        kwargs = (
            {} if sys.platform == "win32"
            else {"kill_after_timeout": settings.clone_timeout_seconds}
        )

        try:
            Repo.clone_from(
                url=repo.clone_url,
                to_path=str(target),
                env=env,
                multi_options=[
                    f"--depth={settings.clone_depth}",
                    "--single-branch",
                    "--no-tags",
                    "--filter=blob:none",
                ],
                **kwargs,
            )
        except GitCommandError as exc:
            remove_tree(target)
            raise self._translate(exc, repo) from exc
        except Exception as exc:  # pragma: no cover - unexpected git/OS failure
            remove_tree(target)
            raise CloneError(f"Cloning failed: {exc}") from exc

        return self._describe(target)

    def cleanup(self, repo: RepoRef) -> None:
        """Delete a clone once its vectors are stored (source of truth = Chroma)."""
        remove_tree(self.local_path(repo))

    # -- internals -----------------------------------------------------------

    @staticmethod
    def _describe(path: Path) -> CloneResult:
        """Read HEAD details from a freshly cloned working tree.

        The ``Repo`` handle is always closed: GitPython memory-maps pack files,
        and on Windows an open handle prevents the directory from being deleted
        later, silently leaking the clone.
        """
        repository: Repo | None = None
        try:
            repository = Repo(str(path))
            head = repository.head.commit
            branch = repository.active_branch.name
            summary = (head.message or "").strip().splitlines()
            return CloneResult(
                path=path,
                default_branch=branch,
                head_commit=head.hexsha[:10],
                head_message=summary[0][:200] if summary else "",
            )
        except Exception as exc:
            raise EmptyRepositoryError(
                "The repository appears to be empty (no commits to read)."
            ) from exc
        finally:
            if repository is not None:
                repository.close()

    @staticmethod
    def _translate(exc: GitCommandError, repo: RepoRef) -> Exception:
        """Turn git's stderr into a precise, user-facing error."""
        stderr = f"{exc.stderr or ''} {exc.stdout or ''}".lower()

        if "authentication failed" in stderr or "could not read username" in stderr:
            return PrivateRepositoryError(
                f"'{repo.full_name}' requires authentication. Only public repositories "
                "are supported right now."
            )
        if "not found" in stderr or "repository does not exist" in stderr:
            return RepositoryNotFound(f"'{repo.full_name}' could not be cloned: not found.")
        if "you appear to have cloned an empty repository" in stderr:
            return EmptyRepositoryError()
        if "timed out" in stderr or "timeout" in stderr:
            return CloneError("Cloning timed out. The repository may be too large.")
        if "could not resolve host" in stderr or "network" in stderr:
            return CloneError("Network error while cloning. Check your internet connection.")

        logger.error("git clone failed for %s: %s", repo.full_name, stderr.strip()[:400])
        return CloneError(f"Cloning '{repo.full_name}' failed. Please verify the URL.")


git_service = GitService()
