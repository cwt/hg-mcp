"""Extended tests for hg_mcp/tools/core.py.

Tests for:
- hg_log limit validation
- hg_diff sanitization and error cases
- hg_commit hg-git integration (mocked)
- hg_amend hg-git integration and message sanitization
- hg_rename and hg_cat path sanitization
- hg_clone source sanitization
- hg_shelve and hg_unshelve (mocked)
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from mcp.types import TextContent

from hg_mcp.helpers import MAX_LOG_LIMIT
from hg_mcp.tools import (
    hg_amend,
    hg_cat,
    hg_clone,
    hg_commit,
    hg_diff,
    hg_log,
    hg_rename,
    hg_shelve,
    hg_unshelve,
)


def _extract_text(result: str | list[TextContent]) -> str:
    """Extract text from test result."""
    if isinstance(result, list):
        return "\n".join(
            item.text if isinstance(item, TextContent) else str(item) for item in result
        )
    return result


class TestHgCoreExtended:
    """Extended tests for core.py."""

    @pytest.mark.asyncio
    async def test_log_limit_errors(self, hg_repo_with_commits: Path) -> None:
        """Test hg_log with invalid limits."""
        # Limit too small
        result = await hg_log(str(hg_repo_with_commits), limit=0)
        text = _extract_text(result)
        assert "Error: limit must be at least 1" in text

        # Limit too large
        result = await hg_log(str(hg_repo_with_commits), limit=MAX_LOG_LIMIT + 1)
        text = _extract_text(result)
        assert "Error: limit exceeds maximum allowed value" in text

    @pytest.mark.asyncio
    async def test_diff_errors(self, hg_repo_with_commits: Path) -> None:
        """Test hg_diff with invalid inputs."""
        # Invalid revision spec (dangerous chars)
        result = await hg_diff(str(hg_repo_with_commits), revisions="0..2; rm -rf /")
        assert "Error: Invalid revision spec" in result

    @pytest.mark.asyncio
    async def test_commit_hggit_integration(self, hg_repo_with_commits: Path) -> None:
        """Test hg_commit with hg-git integration mocked."""
        with patch("hg_mcp.tools.core._is_hggit_enabled", return_value=True):
            with patch(
                "hg_mcp.tools.core._check_git_remotes",
                return_value=(True, ["origin"]),
            ):
                with patch("hg_mcp.tools.core.run_hg_command") as mock_run:
                    # First call is for commit, second for gexport
                    mock_run.side_effect = [
                        "Commit successful",
                        "Export successful",
                    ]

                    result = await hg_commit("test message", str(hg_repo_with_commits))

                    assert "hg-git: Bookmarks exported" in result
                    assert mock_run.call_count == 2

    @pytest.mark.asyncio
    async def test_amend_hggit_integration(self, hg_repo_with_commits: Path) -> None:
        """Test hg_amend with hg-git integration mocked."""
        with patch("hg_mcp.tools.core._is_hggit_enabled", return_value=True):
            with patch(
                "hg_mcp.tools.core._check_git_remotes",
                return_value=(True, ["origin"]),
            ):
                with patch("hg_mcp.tools.core.run_hg_command") as mock_run:
                    mock_run.side_effect = [
                        "Amend successful",
                        "Export successful",
                    ]

                    result = await hg_amend(repo_path=str(hg_repo_with_commits))

                    assert "hg-git: Bookmarks exported" in result

    @pytest.mark.asyncio
    async def test_amend_message_sanitization(self, hg_repo_with_commits: Path) -> None:
        """Test hg_amend with dangerous commit message."""
        result = await hg_amend(
            message="bad message `rm -rf /`",
            repo_path=str(hg_repo_with_commits),
        )
        assert "Error: Invalid commit message" in result

    @pytest.mark.asyncio
    async def test_rename_sanitization(self, hg_repo_with_commits: Path) -> None:
        """Test hg_rename with dangerous paths."""
        result = await hg_rename(
            "old.txt", "new.txt; rm -rf /", str(hg_repo_with_commits)
        )
        assert "Error: Invalid file path" in result

    @pytest.mark.asyncio
    async def test_cat_errors(self, hg_repo_with_commits: Path) -> None:
        """Test hg_cat with invalid inputs."""
        # Invalid revision
        result = await hg_cat("file.txt", str(hg_repo_with_commits), revision="rev;bad")
        assert "Error: Invalid revision" in result

        # Invalid file path
        result = await hg_cat("file.txt;bad", str(hg_repo_with_commits))
        assert "Error: Invalid file path" in result


class TestHgClone:
    """Tests for hg_clone tool."""

    @pytest.mark.asyncio
    async def test_clone_source_sanitization(self) -> None:
        """Test hg_clone with dangerous source URL."""
        result = await hg_clone(source="https://repo; rm -rf /")
        assert "Error: Invalid source" in result

    @pytest.mark.asyncio
    async def test_clone_dest_sanitization(self) -> None:
        """Test hg_clone with dangerous destination path."""
        result = await hg_clone(source="https://example.com/repo", dest="path;bad")
        assert "Error: Invalid destination" in result

    @pytest.mark.asyncio
    async def test_clone_basic(self, temp_dir: Path) -> None:
        """Test hg_clone from a local repo."""
        # Create a source repo
        src_repo = temp_dir / "source"
        src_repo.mkdir()
        import subprocess

        subprocess.run(["hg", "init"], cwd=src_repo, check=True, capture_output=True)
        (src_repo / "README.txt").write_text("test\n")
        subprocess.run(
            ["hg", "add", "README.txt"],
            cwd=src_repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["hg", "commit", "-m", "init"],
            cwd=src_repo,
            check=True,
            capture_output=True,
        )

        result = await hg_clone(
            source=str(src_repo), dest=str(temp_dir / "clone-target")
        )
        assert not result.startswith("Error")


class TestHgShelve:
    """Tests for hg_shelve and hg_unshelve tools."""

    @pytest.mark.asyncio
    async def test_shelve_name_sanitization(self, hg_repo: Path) -> None:
        """Test hg_shelve with dangerous shelf name."""
        result = await hg_shelve(repo_path=str(hg_repo), name="bad;name")
        assert "Error: Invalid shelf name" in result

    @pytest.mark.asyncio
    async def test_shelve_message_sanitization(self, hg_repo: Path) -> None:
        """Test hg_shelve with dangerous message."""
        result = await hg_shelve(repo_path=str(hg_repo), message="bad `msg`")
        assert "Error: Invalid message" in result

    @pytest.mark.asyncio
    async def test_shelve_basic(self, hg_repo: Path) -> None:
        """Test hg_shelve basic call with mocked run_hg_command."""
        with patch("hg_mcp.tools.core.run_hg_command") as mock_run:
            mock_run.return_value = "shelved as default"
            result = await hg_shelve(repo_path=str(hg_repo))
            assert "shelved as default" in result

    @pytest.mark.asyncio
    async def test_shelve_with_files(self, hg_repo: Path) -> None:
        """Test hg_shelve with specific files."""
        with patch("hg_mcp.tools.core.run_hg_command") as mock_run:
            mock_run.return_value = "shelved as test"
            result = await hg_shelve(
                repo_path=str(hg_repo), name="test", files=["file1.txt"]
            )
            assert "shelved as test" in result

    @pytest.mark.asyncio
    async def test_unshelve_continue(self, hg_repo: Path) -> None:
        """Test hg_unshelve continue operation."""
        with patch("hg_mcp.tools.core.run_hg_command") as mock_run:
            mock_run.return_value = "unshelve continue"
            result = await hg_unshelve(repo_path=str(hg_repo), continue_op=True)
            assert "unshelve continue" in result
            mock_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_unshelve_abort(self, hg_repo: Path) -> None:
        """Test hg_unshelve abort operation."""
        with patch("hg_mcp.tools.core.run_hg_command") as mock_run:
            mock_run.return_value = "unshelve abort"
            result = await hg_unshelve(repo_path=str(hg_repo), abort=True)
            assert "unshelve abort" in result

    @pytest.mark.asyncio
    async def test_unshelve_basic(self, hg_repo: Path) -> None:
        """Test hg_unshelve basic call."""
        with patch("hg_mcp.tools.core.run_hg_command") as mock_run:
            mock_run.return_value = "unshelved default"
            result = await hg_unshelve(repo_path=str(hg_repo))
            assert "unshelved default" in result

    @pytest.mark.asyncio
    async def test_unshelve_with_name(self, hg_repo: Path) -> None:
        """Test hg_unshelve with named shelf."""
        with patch("hg_mcp.tools.core.run_hg_command") as mock_run:
            mock_run.return_value = "unshelved test"
            result = await hg_unshelve(repo_path=str(hg_repo), name="test")
            assert "unshelved test" in result
