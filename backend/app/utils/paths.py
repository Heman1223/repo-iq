"""Filesystem helpers with path-traversal protection."""

from __future__ import annotations

import logging
import shutil
import stat
import time
from pathlib import Path

logger = logging.getLogger(__name__)


def is_within(base: Path, target: Path) -> bool:
    """Return ``True`` only if ``target`` resolves inside ``base``.

    Used before every read so that a malicious symlink or ``..`` segment inside
    a cloned repository cannot escape the sandbox directory.
    """
    try:
        base_resolved = base.resolve(strict=False)
        target_resolved = target.resolve(strict=False)
    except OSError:  # pragma: no cover - unreadable path
        return False
    return target_resolved == base_resolved or base_resolved in target_resolved.parents


def relative_posix(base: Path, target: Path) -> str:
    """Repository-relative path using forward slashes (stable across OSes)."""
    return target.resolve().relative_to(base.resolve()).as_posix()


def remove_tree(path: Path, attempts: int = 3) -> bool:
    """Delete a directory tree, returning ``True`` once it is gone.

    Handles the two things that make this unreliable on Windows: read-only
    ``.git`` object files (cleared via ``chmod`` before retrying) and handles
    that a just-finished process has not released yet (short backoff + retry).
    """
    if not path.exists():
        return True

    def _on_error(func, target, _exc_info):
        """Clear the read-only bit and retry the failing operation once."""
        try:
            Path(target).chmod(stat.S_IWRITE | stat.S_IREAD)
            func(target)
        except OSError:
            # Swallowed deliberately: the retry loop below is the real fallback.
            pass

    for attempt in range(attempts):
        try:
            # `onexc` replaced the deprecated `onerror` in Python 3.12.
            try:
                shutil.rmtree(path, onexc=_on_error)
            except TypeError:  # pragma: no cover - Python < 3.12
                shutil.rmtree(path, onerror=_on_error)
        except OSError as exc:
            if attempt == attempts - 1:
                logger.warning("Could not remove %s after %d attempts: %s", path, attempts, exc)
                return False
            time.sleep(0.25 * (attempt + 1))
            continue

        if not path.exists():
            return True
        time.sleep(0.25 * (attempt + 1))

    still_present = path.exists()
    if still_present:
        logger.warning("Directory %s could not be fully removed", path)
    return not still_present


def human_size(num_bytes: int) -> str:
    """Format a byte count as a compact human readable string."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"
