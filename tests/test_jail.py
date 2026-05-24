"""Unit tests for jail path restriction.

Tests the --jail feature that restricts repository access to a specific
directory tree, preventing access to paths outside the jail.
"""

import subprocess
from pathlib import Path

import pytest

from hg_mcp.helpers import (
    validate_path,
    validate_path_in_jail,
    validate_repo_path,
)
from hg_mcp.server import mcp


class TestJailPathValidation:
    """Tests for validate_path_in_jail function."""

    def setup_method(self) -> None:
        """Reset jail path before each test."""
        mcp._jail_path = None

    def teardown_method(self) -> None:
        """Clean up jail path after each test."""
        mcp._jail_path = None

    def test_no_jail_allows_any_path(self, tmp_path: Path) -> None:
        """When jail is not set, any path should be allowed."""
        mcp._jail_path = None
        result = validate_path_in_jail(tmp_path)
        assert result == tmp_path

    def test_jail_allows_path_inside(self, tmp_path: Path) -> None:
        """Paths inside jail should be allowed."""
        jail = tmp_path / "jail"
        jail.mkdir()
        mcp.jail_path = str(jail)

        allowed_path = jail / "repo" / "subdir"
        allowed_path.mkdir(parents=True)

        result = validate_path_in_jail(allowed_path)
        assert result == allowed_path

    def test_jail_blocks_path_outside(self, tmp_path: Path) -> None:
        """Paths outside jail should be blocked."""
        jail = tmp_path / "jail"
        jail.mkdir()
        mcp.jail_path = str(jail)

        outside_path = tmp_path / "outside"
        outside_path.mkdir()

        with pytest.raises(ValueError) as exc_info:
            validate_path_in_jail(outside_path)

        assert "outside the allowed jail" in str(exc_info.value)
        assert "outside" in str(exc_info.value)

    def test_jail_blocks_parent_traversal(self, tmp_path: Path) -> None:
        """Path traversal with .. should be blocked."""
        jail = tmp_path / "jail"
        jail.mkdir()
        mcp.jail_path = str(jail)

        escape_path = jail / ".." / ".." / "etc"
        escaped = escape_path.resolve()

        with pytest.raises(ValueError) as exc_info:
            validate_path_in_jail(escaped)

        assert "outside the allowed jail" in str(exc_info.value)

    def test_jail_allows_exact_path(self, tmp_path: Path) -> None:
        """The jail path itself should be allowed."""
        jail = tmp_path / "jail"
        jail.mkdir()
        mcp.jail_path = str(jail)

        result = validate_path_in_jail(jail)
        assert result == jail

    def test_jail_resolves_symlinks(self, tmp_path: Path) -> None:
        """Symlinks pointing outside jail should be blocked."""
        jail = tmp_path / "jail"
        jail.mkdir()
        mcp.jail_path = str(jail)

        outside = tmp_path / "outside"
        outside.mkdir()

        symlink = jail / "escape"
        symlink.symlink_to(outside)

        resolved = symlink.resolve()
        with pytest.raises(ValueError) as exc_info:
            validate_path_in_jail(resolved)

        assert "outside the allowed jail" in str(exc_info.value)

    def test_jail_path_immutability(self, tmp_path: Path) -> None:
        """jail_path should be immutable once set to a non-None value."""
        jail1 = tmp_path / "jail1"
        jail1.mkdir()
        mcp.jail_path = str(jail1)

        # Setting to same path should be fine
        mcp.jail_path = str(jail1)

        # Setting to different path should raise RuntimeError
        jail2 = tmp_path / "jail2"
        jail2.mkdir()
        with pytest.raises(RuntimeError) as exc_info:
            mcp.jail_path = str(jail2)

        assert "immutable" in str(exc_info.value)

    def test_jail_path_none(self) -> None:
        """Setting jail_path to None should do nothing."""
        mcp._jail_path = None
        mcp.jail_path = None
        assert mcp._jail_path is None


class TestValidatePathWithJail:
    """Tests for validate_path with jail restriction."""

    def setup_method(self) -> None:
        """Reset jail path before each test."""
        mcp._jail_path = None

    def teardown_method(self) -> None:
        """Clean up jail path after each test."""
        mcp._jail_path = None

    def test_validate_path_inside_jail(self, tmp_path: Path) -> None:
        """validate_path should work for paths inside jail."""
        jail = tmp_path / "jail"
        jail.mkdir()
        mcp.jail_path = str(jail)

        target = jail / "project"
        target.mkdir()

        result = validate_path(str(target))
        assert result == target

    def test_validate_path_outside_jail(self, tmp_path: Path) -> None:
        """validate_path should block paths outside jail."""
        jail = tmp_path / "jail"
        jail.mkdir()
        mcp.jail_path = str(jail)

        outside = tmp_path / "outside"
        outside.mkdir()

        with pytest.raises(ValueError) as exc_info:
            validate_path(str(outside))

        assert "outside the allowed jail" in str(exc_info.value)

    def test_validate_path_create_inside_jail(self, tmp_path: Path) -> None:
        """validate_path should create directories inside jail."""
        jail = tmp_path / "jail"
        jail.mkdir()
        mcp.jail_path = str(jail)

        new_dir = jail / "new_project"

        result = validate_path(str(new_dir), create_if_missing=True)
        assert result.exists()
        assert result.is_dir()

    def test_validate_path_blocks_create_outside_jail(self, tmp_path: Path) -> None:
        """validate_path should not create directories outside jail."""
        jail = tmp_path / "jail"
        jail.mkdir()
        mcp.jail_path = str(jail)

        new_dir = tmp_path / "outside_new"

        with pytest.raises(ValueError) as exc_info:
            validate_path(str(new_dir), create_if_missing=True)

        assert "outside the allowed jail" in str(exc_info.value)
        assert not new_dir.exists()


class TestValidateRepoPathWithJail:
    """Tests for validate_repo_path with jail restriction."""

    def setup_method(self) -> None:
        """Reset jail path before each test."""
        mcp._jail_path = None

    def teardown_method(self) -> None:
        """Clean up jail path after each test."""
        mcp._jail_path = None

    def _create_hg_repo(self, path: Path) -> Path:
        """Create a Mercurial repository at the given path."""
        path.mkdir(parents=True, exist_ok=True)
        (path / ".hg").mkdir()
        return path

    def test_validate_repo_path_inside_jail(self, tmp_path: Path) -> None:
        """validate_repo_path should work for repos inside jail."""
        jail = tmp_path / "jail"
        jail.mkdir()
        mcp.jail_path = str(jail)

        repo = self._create_hg_repo(jail / "my_repo")

        result = validate_repo_path(str(repo))
        assert result == repo

    def test_validate_repo_path_outside_jail(self, tmp_path: Path) -> None:
        """validate_repo_path should block repos outside jail."""
        jail = tmp_path / "jail"
        jail.mkdir()
        mcp.jail_path = str(jail)

        outside_repo = self._create_hg_repo(tmp_path / "outside_repo")

        with pytest.raises(ValueError) as exc_info:
            validate_repo_path(str(outside_repo))

        assert "outside the allowed jail" in str(exc_info.value)

    def test_validate_repo_path_parent_outside_jail(self, tmp_path: Path) -> None:
        """Should block if repo root is outside jail even if subpath is inside."""
        jail = tmp_path / "deep" / "jail"
        jail.mkdir(parents=True)
        mcp.jail_path = str(jail)

        self._create_hg_repo(tmp_path)

        with pytest.raises(ValueError) as exc_info:
            validate_repo_path(str(jail))

        assert "outside the allowed jail" in str(exc_info.value)

    def test_validate_repo_path_traversal_escape(self, tmp_path: Path) -> None:
        """Path traversal should not escape jail."""
        jail = tmp_path / "jail"
        jail.mkdir()
        mcp.jail_path = str(jail)

        escape_repo = self._create_hg_repo(tmp_path / "escape")

        with pytest.raises(ValueError) as exc_info:
            validate_repo_path(str(escape_repo))

        assert "outside the allowed jail" in str(exc_info.value)


class TestJailWithRealHgRepo:
    """Integration tests with actual Mercurial repositories."""

    def setup_method(self) -> None:
        """Reset jail path before each test."""
        mcp._jail_path = None

    def teardown_method(self) -> None:
        """Clean up jail path after each test."""
        mcp._jail_path = None

    def test_hg_status_inside_jail(self, tmp_path: Path) -> None:
        """hg_status tool should work with repo inside jail."""
        jail = tmp_path / "jail"
        jail.mkdir()
        mcp.jail_path = str(jail)

        # Create and init repo inside jail
        repo = jail / "test_repo"
        repo.mkdir()
        subprocess.run(["hg", "init"], cwd=repo, check=True, capture_output=True)

        # This should not raise
        path = validate_repo_path(str(repo))
        assert path == repo

    def test_hg_status_blocked_outside_jail(self, tmp_path: Path) -> None:
        """hg_status tool should block access to repo outside jail."""
        jail = tmp_path / "jail"
        jail.mkdir()
        mcp.jail_path = str(jail)

        # Create repo outside jail
        outside_repo = tmp_path / "outside_repo"
        outside_repo.mkdir()
        subprocess.run(
            ["hg", "init"], cwd=outside_repo, check=True, capture_output=True
        )

        with pytest.raises(ValueError) as exc_info:
            validate_repo_path(str(outside_repo))

        assert "outside the allowed jail" in str(exc_info.value)
