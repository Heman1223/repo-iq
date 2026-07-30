"""Module 2 — Repository URL validation (TC_REPO_001 … TC_REPO_008)."""

from __future__ import annotations

import pytest

from app.core.exceptions import InvalidRepositoryURL
from app.utils.repo_url import parse_github_url, sanitize_identifier


class TestValidUrls:
    """TC_REPO_001 / TC_REPO_007 / TC_REPO_008 — accepted URL forms."""

    @pytest.mark.parametrize(
        "raw",
        [
            "https://github.com/pallets/flask",              # TC_REPO_001
            "http://github.com/pallets/flask",
            "github.com/pallets/flask",
            "www.github.com/pallets/flask",
            "https://github.com/pallets/flask/",             # TC_REPO_007 trailing slash
            "https://github.com/pallets/flask.git",          # TC_REPO_008 .git suffix
            "https://github.com/pallets/flask.git/",
            "git@github.com:pallets/flask.git",
            "https://github.com/pallets/flask/tree/main/src",  # deep link
            "https://github.com/pallets/flask/blob/main/README.md",
            "  https://github.com/pallets/flask  ",          # surrounding whitespace
        ],
    )
    def test_normalises_to_the_same_reference(self, raw: str) -> None:
        repo = parse_github_url(raw)
        assert repo.owner == "pallets"
        assert repo.name == "flask"
        assert repo.full_name == "pallets/flask"
        assert repo.clone_url == "https://github.com/pallets/flask.git"
        assert repo.repo_id == "pallets__flask"

    def test_names_with_dots_and_dashes_survive(self) -> None:
        repo = parse_github_url("https://github.com/my-org/my.cool_repo-2")
        assert repo.full_name == "my-org/my.cool_repo-2"


class TestInvalidUrls:
    """TC_REPO_002 / TC_REPO_003 / TC_REPO_004 / TC_REPO_006 — rejected input."""

    @pytest.mark.parametrize(
        "raw",
        [
            "",                                   # TC_REPO_002 empty
            "   ",
            "not-a-url",                          # TC_REPO_003 invalid
            "https://github.com",                 # TC_REPO_004 malformed: no owner/repo
            "https://github.com/pallets",         # TC_REPO_004 owner only
            "https://gitlab.com/group/project",   # TC_REPO_006 non-GitHub
            "https://bitbucket.org/team/repo",    # TC_REPO_006 non-GitHub
            "ftp://github.com/pallets/flask",     # unsupported scheme
            "file:///etc/passwd",
            "https://github.com/../../etc/passwd",
            "https://evil.com/github.com/a/b",
        ],
    )
    def test_raises_invalid_repository_url(self, raw: str) -> None:
        with pytest.raises(InvalidRepositoryURL):
            parse_github_url(raw)


class TestIdentifierSanitising:
    """TC_SEC_002 — identifiers can never carry path or shell metacharacters."""

    @pytest.mark.parametrize(
        "raw",
        ["../../etc/passwd", "a/b\\c", "repo; rm -rf /", "réPo Name!", "$(whoami)"],
    )
    def test_only_safe_characters_survive(self, raw: str) -> None:
        cleaned = sanitize_identifier(raw)
        assert all(character.isalnum() or character in "._-" for character in cleaned)
        assert ".." not in cleaned.strip("-")
        assert "/" not in cleaned and "\\" not in cleaned

    def test_collection_name_matches_chroma_constraints(self) -> None:
        repo = parse_github_url("https://github.com/A-Very-Long-Organisation-Name/an.extremely-long-repository-name")
        name = repo.collection_name
        assert 3 <= len(name) <= 63
        assert name[0].isalnum() and name[-1].isalnum()
        assert all(character.isalnum() or character in "._-" for character in name)
