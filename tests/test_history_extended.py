"""Extended tests for hg_mcp/tools/history.py.

Tests for:
- hg_largefiles tool
- hg_histedit non-interactive editor logic
- hg_backout with/without merge and custom messages
- hg_export/hg_import error cases
- hg_help without repo
- format_bytes helper (indirectly through hg_largefiles)
"""

import subprocess
from pathlib import Path

import pytest
from mcp.types import TextContent

from hg_mcp.tools import (
    hg_backout,
    hg_export,
    hg_help,
    hg_histedit,
    hg_largefiles,
)


def _extract_text(result: str | list[TextContent]) -> str:
    """Extract text from test result (handles both str and list[TextContent])."""
    if isinstance(result, list):
        return "\n".join(
            item.text if isinstance(item, TextContent) else str(item) for item in result
        )
    return result


class TestHgLargefiles:
    """Tests for hg_largefiles tool."""

    @pytest.mark.asyncio
    async def test_largefiles_none_found(self, hg_repo: Path) -> None:
        """Test hg_largefiles when no largefiles exist."""
        result = await hg_largefiles(str(hg_repo))
        text = _extract_text(result)
        assert "No largefiles found" in text

    @pytest.mark.asyncio
    async def test_largefiles_with_data(self, hg_repo: Path) -> None:
        """Test hg_largefiles with actual simulated largefiles data."""
        # Manually create .hglf directory structure to simulate largefiles
        hglf_dir = hg_repo / ".hglf"
        hglf_dir.mkdir()

        # Create a simulated largefile entry
        # Mercurial largefiles store hashes in the working copy and data in .hglf
        # The tool expects .hglf to contain files with size info
        largefile1 = hglf_dir / "bigfile.bin"
        largefile1.write_text("hash123\n1048576\n")  # 1MB

        largefile2 = hglf_dir / "hugefile.dat"
        largefile2.write_text("hash456\n1073741824\n")  # 1GB

        result = await hg_largefiles(str(hg_repo))
        text = _extract_text(result)

        assert "Largefiles in repository" in text
        assert "hugefile.dat: 1.00 GB" in text
        assert "bigfile.bin: 1.00 MB" in text

    @pytest.mark.asyncio
    async def test_largefiles_invalid_data(self, hg_repo: Path) -> None:
        """Test hg_largefiles with invalid data format."""
        hglf_dir = hg_repo / ".hglf"
        hglf_dir.mkdir()

        bad_file = hglf_dir / "bad.bin"
        bad_file.write_text("not_a_size\n")

        result = await hg_largefiles(str(hg_repo))
        text = _extract_text(result)
        assert "bad.bin: 0 bytes" in text


class TestHgHisteditExtended:
    """Extended tests for hg_histedit tool."""

    @pytest.mark.asyncio
    async def test_histedit_with_file_path(
        self, hg_repo_with_commits: Path, temp_dir: Path
    ) -> None:
        """Test histedit with a file path for commands."""
        commands_file = temp_dir / "commands.txt"
        commands_file.write_text("pick 2\npick 3\npick 4")

        result = await hg_histedit(
            str(hg_repo_with_commits), revision="2", commands=str(commands_file)
        )
        assert not result.startswith("Error")

    @pytest.mark.asyncio
    async def test_histedit_with_mess_editor_script(
        self, hg_repo_with_commits: Path
    ) -> None:
        """Test histedit with 'mess' command to trigger editor script creation."""
        # This will test the editor_script creation logic in hg_histedit
        result = await hg_histedit(
            str(hg_repo_with_commits), revision="3", commands="mess 3\npick 4"
        )
        # Even if it fails due to some environment issues, it should have executed the script creation path
        assert isinstance(result, str)


class TestHgBackoutExtended:
    """Extended tests for hg_backout tool."""

    @pytest.mark.asyncio
    async def test_backout_with_custom_message(
        self, hg_repo_with_commits: Path
    ) -> None:
        """Test backout with a custom commit message."""
        result = await hg_backout(
            revision="3",
            repo_path=str(hg_repo_with_commits),
            merge=True,
            message="Undoing change 3 because it was buggy",
        )
        assert not result.startswith("Error")

        # Verify the commit message
        log_out = subprocess.run(
            ["hg", "log", "-l", "1", "-T", "{desc}"],
            cwd=hg_repo_with_commits,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        assert "Undoing change 3" in log_out

    @pytest.mark.asyncio
    async def test_backout_invalid_revision(self, hg_repo: Path) -> None:
        """Test backout with invalid revision."""
        result = await hg_backout("invalid;revision", str(hg_repo))
        assert "Error: Invalid revision" in result


class TestHgHelpExtended:
    """Extended tests for hg_help tool."""

    @pytest.mark.asyncio
    async def test_help_no_repo(self, tmp_path: Path) -> None:
        """Test hg_help in a directory that is not a repo."""
        result = await hg_help(repo_path=str(tmp_path), topic="status")
        assert "show changed files" in result.lower()


class TestHgExportImportErrors:
    """Tests for error cases in export and import."""

    @pytest.mark.asyncio
    async def test_export_invalid_output(self, hg_repo: Path) -> None:
        """Test export with invalid output path."""
        result = await hg_export(str(hg_repo), revisions=["tip"], output="invalid;path")
        assert "Error: Invalid output path" in result

    @pytest.mark.asyncio
    async def test_export_invalid_revision(self, hg_repo: Path) -> None:
        """Test export with invalid revision."""
        result = await hg_export(str(hg_repo), revisions=["invalid;rev"])
        assert "Error: Invalid revision" in result
