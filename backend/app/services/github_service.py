"""GitHub REST API client for public repository metadata.

Only read-only metadata endpoints are used. A token is optional and merely
raises the rate limit; the app works fully unauthenticated.
"""

from __future__ import annotations

import logging

import httpx

from app.core.config import settings
from app.core.exceptions import GitHubAPIError, PrivateRepositoryError, RepositoryNotFound
from app.models.schemas import RepositoryMetadata
from app.utils.repo_url import RepoRef

logger = logging.getLogger(__name__)


class GitHubService:
    """Fetches the facts shown on the repository dashboard."""

    def __init__(self) -> None:
        self._base_url = settings.github_api_base.rstrip("/")
        self._timeout = settings.http_timeout_seconds

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": f"{settings.app_name}/{settings.app_version}",
        }
        if settings.github_token.strip():
            headers["Authorization"] = f"Bearer {settings.github_token.strip()}"
        return headers

    def fetch_metadata(self, repo: RepoRef) -> RepositoryMetadata:
        """Load public metadata for ``repo``.

        Raises:
            RepositoryNotFound: 404 from GitHub (missing *or* private).
            PrivateRepositoryError: the repository exists but is not public.
            GitHubAPIError: network failure or rate limiting.
        """
        url = f"{self._base_url}/repos/{repo.owner}/{repo.name}"
        try:
            with httpx.Client(timeout=self._timeout, follow_redirects=True) as client:
                response = client.get(url, headers=self._headers())
        except httpx.HTTPError as exc:
            raise GitHubAPIError(f"Could not reach the GitHub API: {exc}") from exc

        if response.status_code == 404:
            raise RepositoryNotFound(
                f"'{repo.full_name}' was not found. It may be private, renamed or deleted."
            )
        if response.status_code in (401, 403):
            remaining = response.headers.get("x-ratelimit-remaining")
            if remaining == "0":
                raise GitHubAPIError(
                    "GitHub API rate limit reached. Add a GITHUB_TOKEN to the backend .env "
                    "or try again in a few minutes."
                )
            raise PrivateRepositoryError(f"Access to '{repo.full_name}' was denied by GitHub.")
        if response.status_code >= 400:
            raise GitHubAPIError(
                f"GitHub API returned {response.status_code} for '{repo.full_name}'."
            )

        payload = response.json()
        if payload.get("private"):
            raise PrivateRepositoryError()

        return self._to_metadata(payload, repo)

    @staticmethod
    def _to_metadata(payload: dict, repo: RepoRef) -> RepositoryMetadata:
        """Map the GitHub payload onto our own narrower contract."""
        owner = (payload.get("owner") or {}).get("login") or repo.owner
        license_info = payload.get("license") or {}
        return RepositoryMetadata(
            full_name=payload.get("full_name") or repo.full_name,
            name=payload.get("name") or repo.name,
            owner=owner,
            html_url=payload.get("html_url") or repo.html_url,
            description=payload.get("description"),
            language=payload.get("language"),
            stars=int(payload.get("stargazers_count") or 0),
            forks=int(payload.get("forks_count") or 0),
            watchers=int(payload.get("subscribers_count") or payload.get("watchers_count") or 0),
            open_issues=int(payload.get("open_issues_count") or 0),
            size_kb=int(payload.get("size") or 0),
            default_branch=payload.get("default_branch") or "main",
            topics=list(payload.get("topics") or []),
            license_name=license_info.get("spdx_id") or license_info.get("name"),
            is_fork=bool(payload.get("fork")),
            created_at=payload.get("created_at"),
            updated_at=payload.get("updated_at"),
            pushed_at=payload.get("pushed_at"),
        )

    def fallback_metadata(self, repo: RepoRef) -> RepositoryMetadata:
        """Minimal metadata used when the GitHub API is unavailable."""
        return RepositoryMetadata(
            full_name=repo.full_name,
            name=repo.name,
            owner=repo.owner,
            html_url=repo.html_url,
        )


github_service = GitHubService()
