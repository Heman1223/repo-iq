"""Parsing and validation of GitHub repository URLs.

Security note: only hosts on the configured allow-list are accepted, and the
derived identifiers are strictly sanitised before they are ever used as a
filesystem path or a vector-collection name.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from urllib.parse import urlparse

from app.core.config import settings
from app.core.exceptions import InvalidRepositoryURL

# GitHub allows alphanumerics, hyphen, underscore and period in both segments.
_SEGMENT = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,98}[A-Za-z0-9_])?$")
_SCP_SYNTAX = re.compile(r"^git@(?P<host>[^:]+):(?P<path>.+)$")
_UNSAFE_CHARS = re.compile(r"[^a-z0-9._-]+")
_DOT_RUN = re.compile(r"\.{2,}")
_DASH_RUN = re.compile(r"-{2,}")


@dataclass(frozen=True, slots=True)
class RepoRef:
    """A validated, normalised reference to a public GitHub repository."""

    owner: str
    name: str
    host: str

    @property
    def full_name(self) -> str:
        """``owner/repo`` as GitHub displays it."""
        return f"{self.owner}/{self.name}"

    @property
    def clone_url(self) -> str:
        return f"https://{self.host}/{self.owner}/{self.name}.git"

    @property
    def html_url(self) -> str:
        return f"https://{self.host}/{self.owner}/{self.name}"

    @property
    def repo_id(self) -> str:
        """Stable, filesystem-safe identifier used as the primary key."""
        return sanitize_identifier(f"{self.owner}__{self.name}")

    @property
    def collection_name(self) -> str:
        """Chroma collection name (3-63 chars, alphanumeric edges)."""
        digest = hashlib.sha1(self.full_name.lower().encode()).hexdigest()[:8]
        stem = sanitize_identifier(f"{self.owner}-{self.name}")[:45].strip("-._")
        return f"repo-{stem or 'unnamed'}-{digest}"


def sanitize_identifier(raw: str) -> str:
    """Reduce ``raw`` to a safe ``[a-z0-9._-]`` identifier.

    Single periods survive because real repository names contain them
    (``socket.io``), but runs of periods are collapsed and leading/trailing
    separators removed so the result can never resemble a relative path
    component. Chroma also rejects consecutive periods in collection names.
    """
    cleaned = _UNSAFE_CHARS.sub("-", raw.strip().lower())
    cleaned = _DOT_RUN.sub(".", cleaned)
    cleaned = _DASH_RUN.sub("-", cleaned).strip("-._")
    return cleaned or "unnamed"


def parse_github_url(raw_url: str) -> RepoRef:
    """Turn any accepted GitHub URL form into a :class:`RepoRef`.

    Accepts ``https://github.com/owner/repo``, the same with a ``.git`` suffix,
    deep links such as ``/tree/main/src``, bare ``github.com/owner/repo`` and
    the SCP-style ``git@github.com:owner/repo.git``.

    Raises:
        InvalidRepositoryURL: if the host is not allowed or the path is not a
            recognisable ``owner/repo`` pair.
    """
    candidate = (raw_url or "").strip()
    if not candidate:
        raise InvalidRepositoryURL("Please provide a GitHub repository URL.")

    scp = _SCP_SYNTAX.match(candidate)
    if scp:
        host, path = scp.group("host"), scp.group("path")
    else:
        if "://" not in candidate:
            candidate = f"https://{candidate}"
        parsed = urlparse(candidate)
        if parsed.scheme not in {"http", "https"}:
            raise InvalidRepositoryURL("Only http(s) GitHub URLs are supported.")
        host, path = parsed.netloc, parsed.path

    host = host.lower().split("@")[-1].split(":")[0]
    if host not in settings.allowed_git_host_list:
        allowed = settings.allowed_git_host_list[0]
        raise InvalidRepositoryURL(
            f"Only repositories hosted on {allowed} can be indexed. "
            f"Expected a URL like https://{allowed}/<owner>/<repository>."
        )

    parts = [segment for segment in path.strip("/").split("/") if segment]
    if len(parts) < 2:
        raise InvalidRepositoryURL(
            "Expected a URL in the form https://github.com/<owner>/<repository>."
        )

    owner, name = parts[0], parts[1]
    if name.endswith(".git"):
        name = name[: -len(".git")]

    if not _SEGMENT.match(owner) or not _SEGMENT.match(name):
        raise InvalidRepositoryURL("The owner or repository name contains invalid characters.")

    return RepoRef(owner=owner, name=name, host="github.com")
