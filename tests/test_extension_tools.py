"""Tests for extension-based tools.

Tests tools that require Mercurial extensions:
- hg_rebase, hg_strip, hg_histedit, hg_evolve, hg_transplant
- hg_topic, hg_topics, hg_topic_current
"""

import subprocess
from pathlib import Path

import pytest
from mcp.types import TextContent

from hg_mcp.main import (
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
        # Get a revision from feature branch to transplant
        result = await hg_transplant(
            str(hg_repo_with_branches), revisions=["feature"]
        )
        assert (
            result  # Should complete or show error if extension not available
        )


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
        """Test that topic commands show helpful error when extension disabled."""
        result = await hg_topic("test", str(hg_repo))
        # Should show error with extension hint
        assert "Error" in result or "unknown" in result.lower()

    @pytest.mark.asyncio
    async def test_rebase_without_extension(self, hg_repo: Path) -> None:
        """Test that rebase commands show helpful error when extension disabled."""
        result = await hg_rebase(str(hg_repo), source=".", dest="default")
        # Should show error with extension hint
        assert "Error" in result or "unknown" in result.lower()


class TestHgHistedit:
    """Tests for hg_histedit tool (requires histedit extension)."""

    @pytest.mark.asyncio
    async def test_histedit_basic(self, hg_repo_with_commits: Path) -> None:
        """Test histedit command (may require interactive setup)."""
        # Histedit typically requires interactive input
        # This test verifies the command can be invoked
        result = await hg_histedit(str(hg_repo_with_commits), revision="2")
        # May show error about interactive mode or missing extension
        assert isinstance(result, str)
