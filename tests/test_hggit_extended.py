"""Extended tests for hg_mcp/tools/hggit.py.

Tests for the new evolve extension tools:
- hg_absorb, hg_fold, hg_split, hg_uncommit
- hg_next, hg_previous
- hg_rewind, hg_metaedit, hg_stack, hg_prune
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from hg_mcp.tools import (
    hg_absorb,
    hg_fold,
    hg_metaedit,
    hg_next,
    hg_previous,
    hg_prune,
    hg_rewind,
    hg_split,
    hg_stack,
    hg_uncommit,
)


class TestHgAbsorb:
    """Tests for hg_absorb tool."""

    @pytest.mark.asyncio
    async def test_absorb_basic(self, hg_repo: Path) -> None:
        """Test basic absorb call."""
        with patch("hg_mcp.tools.hggit.run_hg_command") as mock_run:
            mock_run.return_value = "absorbed"
            result = await hg_absorb(str(hg_repo))
            assert "absorbed" in result
            mock_run.assert_called_once()


class TestHgFold:
    """Tests for hg_fold tool."""

    @pytest.mark.asyncio
    async def test_fold_basic(self, hg_repo: Path) -> None:
        """Test basic fold call."""
        with patch("hg_mcp.tools.hggit.run_hg_command") as mock_run:
            mock_run.return_value = "folded"
            result = await hg_fold("abc123", str(hg_repo))
            assert "folded" in result

    @pytest.mark.asyncio
    async def test_fold_no_revisions(self, hg_repo: Path) -> None:
        """Test fold without revisions."""
        result = await hg_fold([], str(hg_repo))
        assert "Error: revisions are required" in result

    @pytest.mark.asyncio
    async def test_fold_with_message_sanitization(self, hg_repo: Path) -> None:
        """Test fold with dangerous message."""
        result = await hg_fold("abc123", str(hg_repo), message="bad `msg`")
        assert "Error: Invalid commit message" in result

    @pytest.mark.asyncio
    async def test_fold_invalid_revision(self, hg_repo: Path) -> None:
        """Test fold with invalid revision."""
        result = await hg_fold("rev;bad", str(hg_repo))
        assert "Error: Invalid revision" in result

    @pytest.mark.asyncio
    async def test_fold_multiple_revisions(self, hg_repo: Path) -> None:
        """Test fold with multiple revisions."""
        with patch("hg_mcp.tools.hggit.run_hg_command") as mock_run:
            mock_run.return_value = "folded"
            result = await hg_fold(["abc123", "def456"], str(hg_repo))
            assert "folded" in result

    @pytest.mark.asyncio
    async def test_fold_with_exact(self, hg_repo: Path) -> None:
        """Test fold with --exact flag."""
        with patch("hg_mcp.tools.hggit.run_hg_command") as mock_run:
            mock_run.return_value = "folded"
            result = await hg_fold("abc123", str(hg_repo), exact=True)
            assert "folded" in result


class TestHgSplit:
    """Tests for hg_split tool."""

    @pytest.mark.asyncio
    async def test_split_basic(self, hg_repo: Path) -> None:
        """Test basic split call."""
        with patch("hg_mcp.tools.hggit.run_hg_command") as mock_run:
            mock_run.return_value = "split complete"
            result = await hg_split(repo_path=str(hg_repo))
            assert "split complete" in result

    @pytest.mark.asyncio
    async def test_split_with_revision(self, hg_repo: Path) -> None:
        """Test split with specific revision."""
        with patch("hg_mcp.tools.hggit.run_hg_command") as mock_run:
            mock_run.return_value = "split complete"
            result = await hg_split(revision="abc123", repo_path=str(hg_repo))
            assert "split complete" in result

    @pytest.mark.asyncio
    async def test_split_invalid_revision(self, hg_repo: Path) -> None:
        """Test split with invalid revision."""
        result = await hg_split(revision="rev;bad", repo_path=str(hg_repo))
        assert "Error: Invalid revision" in result


class TestHgUncommit:
    """Tests for hg_uncommit tool."""

    @pytest.mark.asyncio
    async def test_uncommit_basic(self, hg_repo: Path) -> None:
        """Test basic uncommit call."""
        with patch("hg_mcp.tools.hggit.run_hg_command") as mock_run:
            mock_run.return_value = "uncommitted"
            result = await hg_uncommit(repo_path=str(hg_repo))
            assert "uncommitted" in result

    @pytest.mark.asyncio
    async def test_uncommit_with_revision(self, hg_repo: Path) -> None:
        """Test uncommit with specific revision."""
        with patch("hg_mcp.tools.hggit.run_hg_command") as mock_run:
            mock_run.return_value = "uncommitted"
            result = await hg_uncommit(revisions="abc123", repo_path=str(hg_repo))
            assert "uncommitted" in result

    @pytest.mark.asyncio
    async def test_uncommit_invalid_revision(self, hg_repo: Path) -> None:
        """Test uncommit with invalid revision."""
        result = await hg_uncommit(revisions="rev;bad", repo_path=str(hg_repo))
        assert "Error: Invalid revision" in result

    @pytest.mark.asyncio
    async def test_uncommit_keep(self, hg_repo: Path) -> None:
        """Test uncommit with --keep flag."""
        with patch("hg_mcp.tools.hggit.run_hg_command") as mock_run:
            mock_run.return_value = "uncommitted (kept)"
            result = await hg_uncommit(repo_path=str(hg_repo), keep=True)
            assert "uncommitted (kept)" in result

    @pytest.mark.asyncio
    async def test_uncommit_multiple_revisions(self, hg_repo: Path) -> None:
        """Test uncommit with multiple revisions."""
        with patch("hg_mcp.tools.hggit.run_hg_command") as mock_run:
            mock_run.return_value = "uncommitted"
            result = await hg_uncommit(
                revisions=["abc123", "def456"], repo_path=str(hg_repo)
            )
            assert "uncommitted" in result


class TestHgNextPrevious:
    """Tests for hg_next and hg_previous tools."""

    @pytest.mark.asyncio
    async def test_next_basic(self, hg_repo: Path) -> None:
        """Test basic next call."""
        with patch("hg_mcp.tools.hggit.run_hg_command") as mock_run:
            mock_run.return_value = "moved to next"
            result = await hg_next(str(hg_repo))
            assert "moved to next" in result

    @pytest.mark.asyncio
    async def test_previous_basic(self, hg_repo: Path) -> None:
        """Test basic previous call."""
        with patch("hg_mcp.tools.hggit.run_hg_command") as mock_run:
            mock_run.return_value = "moved to previous"
            result = await hg_previous(str(hg_repo))
            assert "moved to previous" in result


class TestHgRewind:
    """Tests for hg_rewind tool."""

    @pytest.mark.asyncio
    async def test_rewind_basic(self, hg_repo: Path) -> None:
        """Test basic rewind call."""
        with patch("hg_mcp.tools.hggit.run_hg_command") as mock_run:
            mock_run.return_value = "rewound"
            result = await hg_rewind("abc123", str(hg_repo))
            assert "rewound" in result

    @pytest.mark.asyncio
    async def test_rewind_no_revisions(self, hg_repo: Path) -> None:
        """Test rewind without revisions."""
        result = await hg_rewind([], str(hg_repo))
        assert "Error: revisions are required" in result

    @pytest.mark.asyncio
    async def test_rewind_invalid_revision(self, hg_repo: Path) -> None:
        """Test rewind with invalid revision."""
        result = await hg_rewind("rev;bad", str(hg_repo))
        assert "Error: Invalid revision" in result

    @pytest.mark.asyncio
    async def test_rewind_keep(self, hg_repo: Path) -> None:
        """Test rewind with --keep flag."""
        with patch("hg_mcp.tools.hggit.run_hg_command") as mock_run:
            mock_run.return_value = "rewound (kept)"
            result = await hg_rewind("abc123", str(hg_repo), keep=True)
            assert "rewound (kept)" in result

    @pytest.mark.asyncio
    async def test_rewind_multiple_revisions(self, hg_repo: Path) -> None:
        """Test rewind with multiple revisions."""
        with patch("hg_mcp.tools.hggit.run_hg_command") as mock_run:
            mock_run.return_value = "rewound"
            result = await hg_rewind(["abc123", "def456"], str(hg_repo))
            assert "rewound" in result


class TestHgMetaedit:
    """Tests for hg_metaedit tool."""

    @pytest.mark.asyncio
    async def test_metaedit_message(self, hg_repo: Path) -> None:
        """Test metaedit with new message."""
        with patch("hg_mcp.tools.hggit.run_hg_command") as mock_run:
            mock_run.return_value = "metaedited"
            result = await hg_metaedit(repo_path=str(hg_repo), message="Better message")
            assert "metaedited" in result

    @pytest.mark.asyncio
    async def test_metaedit_invalid_message(self, hg_repo: Path) -> None:
        """Test metaedit with dangerous message."""
        result = await hg_metaedit(repo_path=str(hg_repo), message="bad `msg`")
        assert "Error: Invalid commit message" in result

    @pytest.mark.asyncio
    async def test_metaedit_invalid_revision(self, hg_repo: Path) -> None:
        """Test metaedit with invalid revision."""
        result = await hg_metaedit(repo_path=str(hg_repo), revision="rev;bad")
        assert "Error: Invalid revision" in result

    @pytest.mark.asyncio
    async def test_metaedit_user(self, hg_repo: Path) -> None:
        """Test metaedit with new user."""
        with patch("hg_mcp.tools.hggit.run_hg_command") as mock_run:
            mock_run.return_value = "metaedited"
            result = await hg_metaedit(repo_path=str(hg_repo), user="Test User")
            assert "metaedited" in result

    @pytest.mark.asyncio
    async def test_metaedit_invalid_user(self, hg_repo: Path) -> None:
        """Test metaedit with dangerous user string."""
        result = await hg_metaedit(repo_path=str(hg_repo), user="bad;user")
        assert "Error: Invalid user" in result

    @pytest.mark.asyncio
    async def test_metaedit_date(self, hg_repo: Path) -> None:
        """Test metaedit with new date."""
        with patch("hg_mcp.tools.hggit.run_hg_command") as mock_run:
            mock_run.return_value = "metaedited"
            result = await hg_metaedit(
                repo_path=str(hg_repo), date="2024-01-15 10:30:00"
            )
            assert "metaedited" in result

    @pytest.mark.asyncio
    async def test_metaedit_invalid_date(self, hg_repo: Path) -> None:
        """Test metaedit with dangerous date string."""
        result = await hg_metaedit(repo_path=str(hg_repo), date="2020;rm")
        assert "Error: Invalid date" in result

    @pytest.mark.asyncio
    async def test_metaedit_fold(self, hg_repo: Path) -> None:
        """Test metaedit with --fold flag."""
        with patch("hg_mcp.tools.hggit.run_hg_command") as mock_run:
            mock_run.return_value = "metaedited (folded)"
            result = await hg_metaedit(repo_path=str(hg_repo), fold=True)
            assert "metaedited (folded)" in result


class TestHgStack:
    """Tests for hg_stack tool."""

    @pytest.mark.asyncio
    async def test_stack_basic(self, hg_repo: Path) -> None:
        """Test basic stack call."""
        with patch("hg_mcp.tools.hggit.run_hg_command") as mock_run:
            mock_run.return_value = "[]"
            result = await hg_stack(str(hg_repo))
            text = result[0].text if hasattr(result, "text") else str(result)
            assert "[]" in text


class TestHgPrune:
    """Tests for hg_prune tool."""

    @pytest.mark.asyncio
    async def test_prune_basic(self, hg_repo: Path) -> None:
        """Test basic prune call."""
        with patch("hg_mcp.tools.hggit.run_hg_command") as mock_run:
            mock_run.return_value = "pruned"
            result = await hg_prune("abc123", str(hg_repo))
            assert "pruned" in result

    @pytest.mark.asyncio
    async def test_prune_no_revisions(self, hg_repo: Path) -> None:
        """Test prune without revisions."""
        result = await hg_prune([], str(hg_repo))
        assert "Error: revisions are required" in result

    @pytest.mark.asyncio
    async def test_prune_invalid_revision(self, hg_repo: Path) -> None:
        """Test prune with invalid revision."""
        result = await hg_prune("rev;bad", str(hg_repo))
        assert "Error: Invalid revision" in result

    @pytest.mark.asyncio
    async def test_prune_multiple_revisions(self, hg_repo: Path) -> None:
        """Test prune with multiple revisions."""
        with patch("hg_mcp.tools.hggit.run_hg_command") as mock_run:
            mock_run.return_value = "pruned"
            result = await hg_prune(["abc123", "def456"], str(hg_repo))
            assert "pruned" in result
