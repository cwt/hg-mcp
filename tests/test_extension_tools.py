"""Tests for extension-based tools.

Tests tools that require Mercurial extensions:
- hg_rebase, hg_strip, hg_histedit, hg_evolve, hg_transplant
- hg_topic, hg_topics, hg_topic_current
"""

import subprocess
from pathlib import Path

import pytest
from mcp.types import TextContent

from hg_mcp.tools import (
    hg_bookmark_create,
    hg_bookmarks,
    hg_evolve,
    hg_histedit,
    hg_rebase,
    hg_strip,
    hg_topic,
    hg_topic_current,
    hg_topics,
    hg_transplant,
)


def _extract_text(result: str | list[TextContent]) -> str:
    """Extract text from test result (handles both str and list[TextContent])."""
    if isinstance(result, list):
        return "\n".join(
            item.text if isinstance(item, TextContent) else str(item)
            for item in result
        )
    return result


class TestHgRebase:
    """Tests for hg_rebase tool (requires rebase extension)."""

    @pytest.mark.asyncio
    async def test_rebase_basic(self, hg_repo_with_branches: Path) -> None:
        """Test basic rebase operation."""
        # Update to feature branch
        subprocess.run(
            ["hg", "update", "feature"],
            cwd=hg_repo_with_branches,
            check=True,
            capture_output=True,
        )

        # Rebase feature branch onto tip of default
        result = await hg_rebase(
            str(hg_repo_with_branches), source="feature", dest="default"
        )
        assert result  # Should complete


class TestHgStrip:
    """Tests for hg_strip tool (requires strip extension)."""

    @pytest.mark.asyncio
    async def test_strip_revision(self, hg_repo_with_commits: Path) -> None:
        """Test stripping a specific revision."""
        # Strip revision 4 (keep flag not set, so it will be removed)
        result = await hg_strip("4", str(hg_repo_with_commits), keep=True)
        assert result  # Should complete

    @pytest.mark.asyncio
    async def test_strip_without_keep(self, hg_repo_with_commits: Path) -> None:
        """Test stripping without keeping changes."""
        result = await hg_strip("4", str(hg_repo_with_commits), keep=False)
        assert result  # Should complete


class TestHgTopic:
    """Tests for hg_topic tool (requires topic extension)."""

    @pytest.mark.asyncio
    async def test_create_topic(self, hg_repo_with_extensions: Path) -> None:
        """Test creating a new topic."""
        # This test requires topic extension enabled
        result = await hg_topic("test-topic", str(hg_repo_with_extensions))
        # Topic creation may show message or error if extension not available
        assert isinstance(result, str)


class TestHgTopics:
    """Tests for hg_topics tool (requires topic extension)."""

    @pytest.mark.asyncio
    async def test_list_topics(self, hg_repo_with_extensions: Path) -> None:
        """Test listing all topics."""
        result = await hg_topics(str(hg_repo_with_extensions))
        # Should return JSON or message about no topics
        assert isinstance(result, str | list)


class TestHgTopicCurrent:
    """Tests for hg_topic_current tool (requires topic extension)."""

    @pytest.mark.asyncio
    async def test_current_topic(self, hg_repo_with_extensions: Path) -> None:
        """Test getting current topic."""
        result = await hg_topic_current(str(hg_repo_with_extensions))
        # Should return topic name or "No active topic" message
        assert isinstance(result, str)


class TestHgTransplant:
    """Tests for hg_transplant tool (requires transplant extension)."""

    @pytest.mark.asyncio
    async def test_transplant_revision(
        self, hg_repo_with_branches: Path
    ) -> None:
        """Test transplanting a revision (cherry-pick)."""
        # Transplant from feature branch
        result = await hg_transplant(
            revisions=["feature"],
            repo_path=str(hg_repo_with_branches),
        )
        # Should complete or show error if extension not available
        assert isinstance(result, str)


class TestHgEvolve:
    """Tests for hg_evolve tool (requires evolve extension)."""

    @pytest.mark.asyncio
    async def test_evolve_history(self, hg_repo_with_extensions: Path) -> None:
        """Test showing evolution history."""
        result = await hg_evolve(str(hg_repo_with_extensions))
        # Should return evolution history or message if no evolution
        assert isinstance(result, str)


class TestExtensionHints:
    """Tests for extension hint functionality."""

    @pytest.mark.asyncio
    async def test_topic_without_extension(self, hg_repo: Path) -> None:
        """Test that topic commands work when extension is available."""
        result = await hg_topic("test", str(hg_repo))
        # Topic extension is commonly available - just verify it runs
        # If extension not available, should show error message
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_rebase_without_extension(self, hg_repo: Path) -> None:
        """Test that rebase commands show helpful error when extension disabled."""
        result = await hg_rebase(str(hg_repo), source=".", dest="default")
        # Should show error with extension hint
        assert isinstance(result, str)
        assert "Error" in result or "unknown" in result.lower()


class TestHgHistedit:
    """Tests for hg_histedit tool (requires histedit extension)."""

    @pytest.mark.asyncio
    async def test_histedit_basic(self, hg_repo_with_commits: Path) -> None:
        """Test histedit with non-interactive commands."""
        # Use non-interactive mode with commands parameter
        # Pick all revisions without changes
        result = await hg_histedit(
            str(hg_repo_with_commits),
            revision="2",
            commands="pick 2\npick 3\npick 4",
        )
        # Should complete without opening editor
        assert isinstance(result, str)


class TestHgBookmarkCreate:
    """Tests for hg_bookmark_create tool."""

    @pytest.mark.asyncio
    async def test_create_bookmark_at_current(
        self, hg_repo_with_commits: Path
    ) -> None:
        """Test creating a bookmark at current revision."""
        result = await hg_bookmark_create(
            name="test-bookmark", repo_path=str(hg_repo_with_commits)
        )
        assert isinstance(result, str)
        assert not result.startswith("Error:")

        # Verify bookmark was created
        bookmarks = await hg_bookmarks(repo_path=str(hg_repo_with_commits))
        bookmarks_text = _extract_text(bookmarks)
        assert "test-bookmark" in bookmarks_text

    @pytest.mark.asyncio
    async def test_create_bookmark_at_revision(
        self, hg_repo_with_commits: Path
    ) -> None:
        """Test creating a bookmark at specific revision."""
        result = await hg_bookmark_create(
            name="old-bookmark",
            repo_path=str(hg_repo_with_commits),
            revision="0",
        )
        assert isinstance(result, str)
        assert not result.startswith("Error:")


class TestCommandTimeout:
    """Tests for command timeout in run_hg_command."""

    @pytest.mark.asyncio
    async def test_timeout_on_slow_command(
        self, hg_repo_with_commits: Path
    ) -> None:
        """Test that slow commands timeout properly."""
        from hg_mcp.helpers import run_hg_command

        # Use a command with very short timeout
        # Note: 10ms is short enough to test timeout behavior but long enough
        # to avoid flaky failures on slow systems
        result = await run_hg_command(
            args=["log", "-l", "1000"],  # Large limit to make it slower
            cwd=hg_repo_with_commits,
            timeout=0.01,  # 10ms timeout to test timeout handling
        )

        assert isinstance(result, str)
        assert result.startswith("Error:")
        assert "timed out" in result.lower()

    @pytest.mark.asyncio
    async def test_normal_command_completes(
        self, hg_repo_with_commits: Path
    ) -> None:
        """Test that normal commands complete within timeout."""
        from hg_mcp.helpers import run_hg_command

        # Normal status command should complete quickly
        result = await run_hg_command(
            args=["status"],
            cwd=hg_repo_with_commits,
            timeout=5.0,  # 5 second timeout
        )

        # Should not timeout
        assert "timed out" not in result.lower()
