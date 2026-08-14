"""Extended tests for hg_mcp/helpers.py.

Tests for:
- format_bytes with all units
- validate_path directory creation failure
- validate_repo_path reaching root
- _get_extension_hint for non-extension errors
- run_hg_command FileNotFoundError and general Exception
- parse_list_param with invalid types
- _is_hggit_enabled error cases
- _check_git_remotes JSON decode error
- _get_git_branches error and JSON decode error
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from hg_mcp.helpers import (
    _check_git_remotes,
    _get_extension_hint,
    _get_git_branches,
    _is_hggit_enabled,
    format_bytes,
    parse_list_param,
    run_hg_command,
    sync_git_bookmarks,
    validate_path,
    validate_repo_path,
)


class TestHelpersExtended:
    """Extended tests for helpers.py."""

    def test_format_bytes_all_units(self) -> None:
        """Test format_bytes with various sizes to cover all units."""
        assert format_bytes(500) == "500 bytes"
        assert format_bytes(1024) == "1.00 KB"
        assert format_bytes(1024 * 1024) == "1.00 MB"
        assert format_bytes(1024 * 1024 * 1024) == "1.00 GB"
        assert format_bytes(1024 * 1024 * 1024 * 1024) == "1.00 TB"
        assert format_bytes(1024 * 1024 * 1024 * 1024 * 1024) == "1.00 PB"

    def test_validate_path_creation_failure(self, tmp_path: Path) -> None:
        """Test validate_path when directory creation fails."""
        # Create a file where a directory should be
        file_path = tmp_path / "not_a_dir"
        file_path.write_text("i am a file")

        # Try to create a subdirectory under the file
        nested = file_path / "subdir"

        with pytest.raises(ValueError) as exc_info:
            validate_path(str(nested), create_if_missing=True)
        assert "Failed to create directory" in str(exc_info.value)

    def test_validate_repo_path_not_found(self, tmp_path: Path) -> None:
        """Test validate_repo_path when reaching root without finding .hg."""
        with pytest.raises(ValueError) as exc_info:
            validate_repo_path(str(tmp_path))
        assert "Not a Mercurial repository" in str(exc_info.value)

    def test_get_extension_hint_non_extension_error(self) -> None:
        """Test _get_extension_hint when the error is not extension-related."""
        hint = _get_extension_hint("some other error", ["status"])
        assert hint == ""

        hint = _get_extension_hint("unknown command", [])
        assert hint == ""

    @pytest.mark.asyncio
    async def test_run_hg_command_not_found(self) -> None:
        """Test run_hg_command when hg is not found."""
        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            result = await run_hg_command(["status"])
            assert "Mercurial (hg) command not found" in result

    @pytest.mark.asyncio
    async def test_run_hg_command_general_exception(self) -> None:
        """Test run_hg_command when a general exception occurs."""
        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=RuntimeError("something went wrong"),
        ):
            result = await run_hg_command(["status"])
            assert "Error executing hg command: something went wrong" in result

    @pytest.mark.asyncio
    async def test_run_hg_command_empty_args(self) -> None:
        """Test run_hg_command with empty args."""
        result = await run_hg_command([])
        assert "Error: No command provided" in result

    def test_parse_list_param_invalid_types(self) -> None:
        """Test parse_list_param with invalid input types."""
        # Not a string or list
        assert parse_list_param(123) == []  # type: ignore[arg-type]

        # Invalid JSON string
        assert parse_list_param("[invalid") == ["[invalid"]

        # JSON but not a list
        assert parse_list_param('{"key": "value"}') == ['{"key": "value"}']

    @pytest.mark.asyncio
    async def test_is_hggit_enabled_error(self, tmp_path: Path) -> None:
        """Test _is_hggit_enabled when run_hg_command fails."""
        with patch("hg_mcp.helpers.run_hg_command", return_value="Error: fail"):
            result = await _is_hggit_enabled(tmp_path)
            assert result is False

    @pytest.mark.asyncio
    async def test_check_git_remotes_json_error(self, tmp_path: Path) -> None:
        """Test _check_git_remotes when JSON parsing fails."""
        with patch("hg_mcp.helpers.run_hg_command", return_value="not json"):
            is_backed, remotes = await _check_git_remotes(tmp_path)
            assert is_backed is False
            assert remotes == []

    @pytest.mark.asyncio
    async def test_get_git_branches_json_error(self, tmp_path: Path) -> None:
        """Test _get_git_branches when JSON parsing fails."""
        with patch("hg_mcp.helpers.run_hg_command", return_value="[not json"):
            git_branches, local_bookmarks = await _get_git_branches(tmp_path, ".git")
            assert git_branches == []
            assert local_bookmarks == []

    @pytest.mark.asyncio
    async def test_get_git_branches_no_bookmarks(self, tmp_path: Path) -> None:
        """Test _get_git_branches when no bookmarks exist."""
        with patch("hg_mcp.helpers.run_hg_command", return_value="no bookmarks set"):
            git_branches, local_bookmarks = await _get_git_branches(tmp_path, ".git")
            assert git_branches == []
            assert local_bookmarks == []

    @pytest.mark.asyncio
    async def test_sync_git_bookmarks_not_enabled(self, tmp_path: Path) -> None:
        """Test sync_git_bookmarks when hg-git is not enabled."""
        with patch("hg_mcp.helpers._is_hggit_enabled", return_value=False):
            result = await sync_git_bookmarks(tmp_path)
            assert result == ""

    @pytest.mark.asyncio
    async def test_sync_git_bookmarks_success(self, tmp_path: Path) -> None:
        """Test sync_git_bookmarks when hg-git is enabled and gexport succeeds."""
        with patch("hg_mcp.helpers._is_hggit_enabled", return_value=True):
            with patch(
                "hg_mcp.helpers._check_git_remotes", return_value=(True, ["remote"])
            ):
                with patch("hg_mcp.helpers.run_hg_command", return_value="exporting"):
                    result = await sync_git_bookmarks(tmp_path)
                    assert "Bookmarks exported" in result

    @pytest.mark.asyncio
    async def test_sync_git_bookmarks_skipped_on_error(self, tmp_path: Path) -> None:
        """Test sync_git_bookmarks when gexport returns an error."""
        with patch("hg_mcp.helpers._is_hggit_enabled", return_value=True):
            with patch(
                "hg_mcp.helpers._check_git_remotes", return_value=(True, ["remote"])
            ):
                with patch(
                    "hg_mcp.helpers.run_hg_command", return_value="Error: export failed"
                ):
                    result = await sync_git_bookmarks(tmp_path)
                    assert "hg gexport skipped" in result
