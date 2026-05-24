"""Extended tests for hg_mcp/tools/merge.py.

Tests for:
- hg_graft with various options
- hg_merge error paths
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from hg_mcp.tools import hg_graft, hg_merge


class TestHgGraft:
    """Tests for hg_graft tool."""

    @pytest.mark.asyncio
    async def test_graft_basic(self, hg_repo: Path) -> None:
        """Test basic graft call."""
        with patch("hg_mcp.tools.merge.run_hg_command") as mock_run:
            mock_run.return_value = "grafted"
            result = await hg_graft(repo_path=str(hg_repo), revisions="abc123")
            assert "grafted" in result

    @pytest.mark.asyncio
    async def test_graft_continue(self, hg_repo: Path) -> None:
        """Test graft continue operation."""
        with patch("hg_mcp.tools.merge.run_hg_command") as mock_run:
            mock_run.return_value = "graft continue"
            result = await hg_graft(repo_path=str(hg_repo), continue_op=True)
            assert "graft continue" in result
            mock_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_graft_abort(self, hg_repo: Path) -> None:
        """Test graft abort operation."""
        with patch("hg_mcp.tools.merge.run_hg_command") as mock_run:
            mock_run.return_value = "graft abort"
            result = await hg_graft(repo_path=str(hg_repo), abort=True)
            assert "graft abort" in result

    @pytest.mark.asyncio
    async def test_graft_stop(self, hg_repo: Path) -> None:
        """Test graft stop operation."""
        with patch("hg_mcp.tools.merge.run_hg_command") as mock_run:
            mock_run.return_value = "graft stop"
            result = await hg_graft(repo_path=str(hg_repo), stop=True)
            assert "graft stop" in result

    @pytest.mark.asyncio
    async def test_graft_invalid_revision(self, hg_repo: Path) -> None:
        """Test graft with invalid revision."""
        result = await hg_graft(repo_path=str(hg_repo), revisions="rev;bad")
        assert "Error: Invalid revision" in result

    @pytest.mark.asyncio
    async def test_graft_multiple_revisions(self, hg_repo: Path) -> None:
        """Test graft with multiple revisions."""
        with patch("hg_mcp.tools.merge.run_hg_command") as mock_run:
            mock_run.return_value = "grafted"
            result = await hg_graft(
                repo_path=str(hg_repo), revisions=["abc123", "def456"]
            )
            assert "grafted" in result

    @pytest.mark.asyncio
    async def test_graft_with_flags(self, hg_repo: Path) -> None:
        """Test graft with no_commit, log, force flags."""
        with patch("hg_mcp.tools.merge.run_hg_command") as mock_run:
            mock_run.return_value = "grafted"
            result = await hg_graft(
                repo_path=str(hg_repo),
                revisions="abc123",
                no_commit=True,
                log=True,
                force=True,
            )
            assert "grafted" in result


class TestHgMergeExtended:
    """Extended tests for hg_merge error paths."""

    @pytest.mark.asyncio
    async def test_merge_invalid_revision(self, hg_repo: Path) -> None:
        """Test merge with invalid revision."""
        result = await hg_merge(revision="rev;bad", repo_path=str(hg_repo))
        assert "Error: Invalid revision" in result
