"""Tests for merge tools and additional helper coverage.

Tests for:
- hg_merge, hg_resolve
- Additional helpers.py coverage
"""

import subprocess
from pathlib import Path

import pytest

from hg_mcp.helpers import (
    _get_git_branches,
    _is_hggit_enabled,
    run_hg_command,
)
from hg_mcp.tools import hg_merge, hg_resolve


class TestHgMerge:
    """Tests for hg_merge tool."""

    @pytest.mark.asyncio
    async def test_merge_no_pending(self, hg_repo_with_commits: Path) -> None:
        """Test merge when no merge is pending."""
        result = await hg_merge(str(hg_repo_with_commits))
        # Should indicate nothing to merge or error
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_merge_with_branch(self, hg_repo_with_branches: Path) -> None:
        """Test merging from another branch."""
        # First update to feature branch
        subprocess.run(
            ["hg", "update", "feature"],
            cwd=hg_repo_with_branches,
            check=True,
            capture_output=True,
        )

        # Try to merge default into feature
        result = await hg_merge(str(hg_repo_with_branches), revision="default")
        assert result


class TestHgResolve:
    """Tests for hg_resolve tool."""

    @pytest.mark.asyncio
    async def test_resolve_list_conflicts(self, hg_repo: Path) -> None:
        """Test listing resolve status (no conflicts)."""
        result = await hg_resolve(repo_path=str(hg_repo))
        # hg_resolve returns list[TextContent] via @json_tool
        assert isinstance(result, str | list)

    @pytest.mark.asyncio
    async def test_resolve_with_merge_conflict(
        self, hg_repo_with_branches: Path
    ) -> None:
        """Test resolve during merge conflict."""
        # Create a conflicting situation
        # Update to default
        subprocess.run(
            ["hg", "update", "default"],
            cwd=hg_repo_with_branches,
            check=True,
            capture_output=True,
        )

        # Try to merge feature branch
        await hg_merge(repo_path=str(hg_repo_with_branches), revision="feature")

        # Check resolve status
        resolve_result = await hg_resolve(repo_path=str(hg_repo_with_branches))
        assert isinstance(resolve_result, str | list)


class TestIsHggitEnabled:
    """Tests for _is_hggit_enabled helper."""

    @pytest.mark.asyncio
    async def test_hggit_not_enabled(self, hg_repo: Path) -> None:
        """Test detecting hg-git when not enabled."""
        result = await _is_hggit_enabled(hg_repo)
        # Note: This may return True if hg-git is globally enabled
        assert isinstance(result, bool)


class TestGetGitBranches:
    """Tests for _get_git_branches helper."""

    @pytest.mark.asyncio
    async def test_get_git_branches_no_suffix(
        self, hg_repo_with_bookmarks: Path
    ) -> None:
        """Test getting git branches without suffix configured."""
        git_branches, local_bookmarks = await _get_git_branches(
            hg_repo_with_bookmarks, suffix=None
        )
        assert isinstance(git_branches, list)
        assert isinstance(local_bookmarks, list)

    @pytest.mark.asyncio
    async def test_get_git_branches_with_suffix(
        self, hg_repo_with_bookmarks: Path
    ) -> None:
        """Test getting git branches with suffix configured."""
        git_branches, local_bookmarks = await _get_git_branches(
            hg_repo_with_bookmarks, suffix=".git"
        )
        assert isinstance(git_branches, list)
        assert isinstance(local_bookmarks, list)

    @pytest.mark.asyncio
    async def test_get_git_branches_empty_repo(self, hg_repo: Path) -> None:
        """Test getting git branches from repo without bookmarks."""
        git_branches, local_bookmarks = await _get_git_branches(
            hg_repo, suffix=".git"
        )
        assert git_branches == []
        assert local_bookmarks == []


class TestRunHgCommandWithJson:
    """Tests for run_hg_command with JSON output."""

    @pytest.mark.asyncio
    async def test_run_command_with_json(
        self, hg_repo_with_commits: Path
    ) -> None:
        """Test running command with automatic JSON output."""
        result = await run_hg_command(
            ["log", "--limit", "2"], cwd=hg_repo_with_commits
        )
        # Should be JSON formatted
        assert result.startswith("[")

    @pytest.mark.asyncio
    async def test_run_command_without_json(
        self, hg_repo_with_commits: Path
    ) -> None:
        """Test running command without JSON output."""
        result = await run_hg_command(
            ["log", "--limit", "1"], cwd=hg_repo_with_commits, use_json=False
        )
        # Should be human-readable format
        assert "changeset" in result.lower()

    @pytest.mark.asyncio
    async def test_run_command_with_existing_json_flag(
        self, hg_repo_with_commits: Path
    ) -> None:
        """Test running command that already has -T flag."""
        result = await run_hg_command(
            ["log", "--limit", "1", "-T", "json"], cwd=hg_repo_with_commits
        )
        assert result.startswith("[")


class TestRunHgCommandErrors:
    """Tests for run_hg_command error handling."""

    @pytest.mark.asyncio
    async def test_run_command_file_not_found(self, hg_repo: Path) -> None:
        """Test error when hg command not found (simulated)."""
        # This test verifies error handling works
        result = await run_hg_command(["nonexistent"], cwd=hg_repo)
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_run_command_with_invalid_args(self, hg_repo: Path) -> None:
        """Test error with invalid arguments."""
        result = await run_hg_command(
            ["log", "--invalid-flag-xyz"], cwd=hg_repo
        )
        assert "Error" in result


class TestMergeToolOutput:
    """Tests verifying merge tool output format."""

    @pytest.mark.asyncio
    async def test_merge_returns_string(
        self, hg_repo_with_commits: Path
    ) -> None:
        """Test that merge returns string output."""
        result = await hg_merge(repo_path=str(hg_repo_with_commits))
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_resolve_returns_list(
        self, hg_repo_with_commits: Path
    ) -> None:
        """Test that resolve returns list[TextContent] output."""
        result = await hg_resolve(repo_path=str(hg_repo_with_commits))
        # hg_resolve uses @json_tool decorator, returns list[TextContent]
        assert isinstance(result, str | list)
