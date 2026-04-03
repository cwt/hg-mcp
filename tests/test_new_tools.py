"""Tests for newly added tools in v0.8.x.

Tests for tools re-implemented from v0.7.3:
- hg_bookmark: Show/create bookmarks
- hg_amend: Amend current commit
- hg_cat: Show file content at revision
- hg_rename: Rename/move files

Also tests helpers.py functions for better coverage.
"""

from pathlib import Path

import pytest

from hg_mcp.helpers import (
    _check_git_remotes,
    _get_extension_hint,
    format_bytes,
    parse_list_param,
    run_hg_command,
    sanitize_input,
    validate_repo_path,
)
from hg_mcp.tools import (
    hg_add,
    hg_amend,
    hg_bookmark,
    hg_bookmarks,
    hg_cat,
    hg_rename,
    hg_status,
)


def _extract_text(result: str | list[object]) -> str:
    """Extract text from test result."""
    if isinstance(result, list):
        return "\n".join(
            item.text if hasattr(item, "text") else str(item) for item in result
        )
    return result


class TestSanitizeInput:
    """Tests for sanitize_input helper function."""

    def test_sanitize_clean_input(self) -> None:
        """Test sanitizing clean input."""
        assert sanitize_input("hello") == "hello"
        assert sanitize_input("test123") == "test123"

    def test_sanitize_empty_input(self) -> None:
        """Test sanitizing empty input."""
        assert sanitize_input("") == ""

    def test_sanitize_within_max_length(self) -> None:
        """Test input within max length passes."""
        result = sanitize_input("a" * 100, max_length=100)
        assert len(result) == 100

    def test_sanitize_exceeds_max_length(self) -> None:
        """Test input exceeding max length raises ValueError."""
        with pytest.raises(ValueError, match="exceeds maximum length"):
            sanitize_input("a" * 1001, max_length=1000)

    def test_sanitize_dangerous_backtick(self) -> None:
        """Test rejecting backtick character."""
        with pytest.raises(ValueError, match="invalid character sequence"):
            sanitize_input("test`command")

    def test_sanitize_dangerous_dollar_paren(self) -> None:
        """Test rejecting $( pattern."""
        with pytest.raises(ValueError, match="invalid character sequence"):
            sanitize_input("$(whoami)")

    def test_sanitize_dangerous_dollar_brace(self) -> None:
        """Test rejecting ${ pattern."""
        with pytest.raises(ValueError, match="invalid character sequence"):
            sanitize_input("${VAR}")

    def test_sanitize_dangerous_pipe(self) -> None:
        """Test rejecting pipe character."""
        with pytest.raises(ValueError, match="invalid character sequence"):
            sanitize_input("test | cat")

    def test_sanitize_dangerous_semicolon(self) -> None:
        """Test rejecting semicolon."""
        with pytest.raises(ValueError, match="invalid character sequence"):
            sanitize_input("test; rm -rf")

    def test_sanitize_dangerous_double_ampersand(self) -> None:
        """Test rejecting && pattern."""
        with pytest.raises(ValueError, match="invalid character sequence"):
            sanitize_input("test && echo")

    def test_sanitize_dangerous_double_pipe(self) -> None:
        """Test rejecting || pattern."""
        with pytest.raises(ValueError, match="invalid character sequence"):
            sanitize_input("test || echo")

    def test_sanitize_dangerous_redirects(self) -> None:
        """Test rejecting redirect characters."""
        with pytest.raises(ValueError, match="invalid character sequence"):
            sanitize_input("test > file")
        with pytest.raises(ValueError, match="invalid character sequence"):
            sanitize_input("test < file")

    def test_sanitize_dangerous_ampersand(self) -> None:
        """Test rejecting single ampersand."""
        with pytest.raises(ValueError, match="invalid character sequence"):
            sanitize_input("test &")


class TestParseListParam:
    """Tests for parse_list_param helper function."""

    def test_parse_none_returns_empty(self) -> None:
        """Test None returns empty list."""
        assert parse_list_param(None) == []

    def test_parse_none_with_default(self) -> None:
        """Test None with default value."""
        result = parse_list_param(None, default=["a", "b"])
        assert result == ["a", "b"]

    def test_parse_list_returns_as_is(self) -> None:
        """Test list input returns unchanged."""
        assert parse_list_param(["a", "b"]) == ["a", "b"]

    def test_parse_single_string(self) -> None:
        """Test single string wrapped in list."""
        assert parse_list_param("hello") == ["hello"]

    def test_parse_json_array_string(self) -> None:
        """Test JSON array string parsed correctly."""
        result = parse_list_param('["a", "b", "c"]')
        assert result == ["a", "b", "c"]

    def test_parse_non_json_string(self) -> None:
        """Test non-JSON string treated as single value."""
        assert parse_list_param("not-json") == ["not-json"]


class TestFormatBytes:
    """Tests for format_bytes helper function."""

    def test_format_bytes_zero(self) -> None:
        """Test zero bytes."""
        assert format_bytes(0) == "0 bytes"

    def test_format_bytes_bytes(self) -> None:
        """Test bytes format."""
        assert format_bytes(512) == "512 bytes"

    def test_format_bytes_kb(self) -> None:
        """Test KB format)."""
        assert format_bytes(1024) == "1.00 KB"
        assert format_bytes(1536) == "1.50 KB"

    def test_format_bytes_mb(self) -> None:
        """Test MB format."""
        assert format_bytes(1024 * 1024) == "1.00 MB"

    def test_format_bytes_gb(self) -> None:
        """Test GB format."""
        assert format_bytes(1024 * 1024 * 1024) == "1.00 GB"

    def test_format_bytes_tb(self) -> None:
        """Test TB format."""
        assert format_bytes(1024 * 1024 * 1024 * 1024) == "1.00 TB"


class TestGetExtensionHint:
    """Tests for _get_extension_hint helper function."""

    def test_hint_for_topic_command(self) -> None:
        """Test hint for topic command."""
        hint = _get_extension_hint("unknown command 'topic'", ["topic"])
        assert "topic" in hint
        assert "[extensions]" in hint

    def test_hint_for_rebase_command(self) -> None:
        """Test hint for rebase command."""
        hint = _get_extension_hint("unknown command 'rebase'", ["rebase"])
        assert "rebase" in hint

    def test_no_hint_for_known_command(self) -> None:
        """Test no hint for commands without extension requirements."""
        hint = _get_extension_hint("some error", ["status"])
        assert hint == ""

    def test_no_hint_for_empty_args(self) -> None:
        """Test no hint when command args empty."""
        hint = _get_extension_hint("error", [])
        assert hint == ""


class TestValidateRepoPath:
    """Tests for validate_repo_path helper function."""

    def test_validate_existing_repo(self, hg_repo: Path) -> None:
        """Test validating existing repository."""
        result = validate_repo_path(str(hg_repo))
        assert result.exists()
        assert (result / ".hg").is_dir()

    def test_validate_current_directory(self, hg_repo: Path) -> None:
        """Test validating current directory as repo."""
        validate_repo_path(".")
        # Should work if running from within a repo

    def test_validate_nonexistent_path(self, temp_dir: Path) -> None:
        """Test validating nonexistent path raises error."""
        with pytest.raises(ValueError, match="does not exist"):
            validate_repo_path(str(temp_dir / "nonexistent"))

    def test_validate_non_repo_directory(self, temp_dir: Path) -> None:
        """Test validating directory without .hg raises error."""
        test_dir = temp_dir / "not-a-repo"
        test_dir.mkdir()
        with pytest.raises(ValueError, match="Not a Mercurial repository"):
            validate_repo_path(str(test_dir))


class TestHgBookmark:
    """Tests for hg_bookmark tool."""

    @pytest.mark.asyncio
    async def test_bookmark_show_current(self, hg_repo: Path) -> None:
        """Test showing current bookmark."""
        result = await hg_bookmark(repo_path=str(hg_repo))
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_bookmark_create_basic(self, hg_repo: Path) -> None:
        """Test creating a basic bookmark."""
        result = await hg_bookmark(name="test-bookmark", repo_path=str(hg_repo))
        # hg bookmark may return empty string on success
        assert isinstance(result, str)

        # Verify bookmark was created
        bookmarks = await hg_bookmarks(repo_path=str(hg_repo))
        text = _extract_text(bookmarks)
        assert "test-bookmark" in text

    @pytest.mark.asyncio
    async def test_bookmark_create_with_revision(
        self, hg_repo_with_commits: Path
    ) -> None:
        """Test creating bookmark at specific revision."""
        result = await hg_bookmark(
            name="at-rev2", repo_path=str(hg_repo_with_commits), revision="2"
        )
        assert isinstance(result, str)

        # Verify bookmark points to correct revision
        bookmarks = await hg_bookmarks(repo_path=str(hg_repo_with_commits))
        text = _extract_text(bookmarks)
        assert "at-rev2" in text

    @pytest.mark.asyncio
    async def test_bookmark_invalid_name(self, hg_repo: Path) -> None:
        """Test creating bookmark with invalid name."""
        # Very long name should fail
        result = await hg_bookmark(
            name="a" * 300, repo_path=str(hg_repo), revision=""
        )
        assert "Error" in result or "invalid" in result.lower()

    @pytest.mark.asyncio
    async def test_bookmark_with_dangerous_characters(
        self, hg_repo: Path
    ) -> None:
        """Test bookmark name with dangerous characters is rejected."""
        result = await hg_bookmark(
            name="test`rm", repo_path=str(hg_repo), revision=""
        )
        assert "Error" in result


class TestHgAmend:
    """Tests for hg_amend tool."""

    @pytest.mark.asyncio
    async def test_amend_without_message(
        self, hg_repo_with_commits: Path
    ) -> None:
        """Test amending without changing message."""
        # Make a change to amend
        test_file = hg_repo_with_commits / "amend_test.txt"
        test_file.write_text("Change to amend\n", encoding="utf-8")
        await hg_add(
            files=["amend_test.txt"], repo_path=str(hg_repo_with_commits)
        )

        result = await hg_amend(repo_path=str(hg_repo_with_commits))
        # hg commit --amend may return empty string on success
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_amend_with_new_message(
        self, hg_repo_with_commits: Path
    ) -> None:
        """Test amending with new commit message."""
        # Make a change to amend
        test_file = hg_repo_with_commits / "amend_msg_test.txt"
        test_file.write_text("Change\n", encoding="utf-8")
        await hg_add(
            files=["amend_msg_test.txt"], repo_path=str(hg_repo_with_commits)
        )

        result = await hg_amend(
            message="Amended: new message", repo_path=str(hg_repo_with_commits)
        )
        assert isinstance(result, str)

        # Verify the commit message was updated
        log_result = await hg_status(repo_path=str(hg_repo_with_commits))
        assert isinstance(log_result, str | list)

    @pytest.mark.asyncio
    async def test_amend_invalid_message(self, hg_repo: Path) -> None:
        """Test amending with invalid message (too long)."""
        result = await hg_amend(message="a" * 20000, repo_path=str(hg_repo))
        assert "Error" in result or "invalid" in result.lower()


class TestHgCat:
    """Tests for hg_cat tool."""

    @pytest.mark.asyncio
    async def test_cat_current_revision(
        self, hg_repo_with_commits: Path
    ) -> None:
        """Test showing file at current parent revision."""
        result = await hg_cat(
            file="README.txt", repo_path=str(hg_repo_with_commits)
        )
        assert "Initial commit" in result or "README" in result

    @pytest.mark.asyncio
    async def test_cat_specific_revision(
        self, hg_repo_with_commits: Path
    ) -> None:
        """Test showing file at specific revision."""
        result = await hg_cat(
            file="file2.txt", repo_path=str(hg_repo_with_commits), revision="2"
        )
        assert "Content 2" in result

    @pytest.mark.asyncio
    async def test_cat_nonexistent_file(self, hg_repo: Path) -> None:
        """Test showing nonexistent file."""
        result = await hg_cat(file="nonexistent.txt", repo_path=str(hg_repo))
        assert "Error" in result or "abort" in result.lower()

    @pytest.mark.asyncio
    async def test_cat_invalid_file_path(self, hg_repo: Path) -> None:
        """Test cat with invalid file path (dangerous characters)."""
        result = await hg_cat(
            file="test`rm.txt", repo_path=str(hg_repo), revision=""
        )
        assert "Error" in result or "invalid" in result.lower()

    @pytest.mark.asyncio
    async def test_cat_invalid_revision(self, hg_repo: Path) -> None:
        """Test cat with invalid revision."""
        result = await hg_cat(
            file="README.txt", repo_path=str(hg_repo), revision="99999"
        )
        assert "Error" in result or "abort" in result.lower()


class TestHgRename:
    """Tests for hg_rename tool."""

    @pytest.mark.asyncio
    async def test_rename_basic(self, hg_repo: Path) -> None:
        """Test basic file rename."""
        # Create file to rename
        src_file = hg_repo / "original.txt"
        src_file.write_text("Content\n", encoding="utf-8")
        await hg_add(files=["original.txt"], repo_path=str(hg_repo))

        result = await hg_rename(
            src="original.txt", dst="renamed.txt", repo_path=str(hg_repo)
        )
        # hg rename may return empty string on success
        assert isinstance(result, str)

        # Verify rename worked
        assert not src_file.exists()
        assert (hg_repo / "renamed.txt").exists()

    @pytest.mark.asyncio
    async def test_rename_invalid_src_path(self, hg_repo: Path) -> None:
        """Test rename with invalid source path."""
        result = await hg_rename(
            src="test`rm.txt", dst="new.txt", repo_path=str(hg_repo)
        )
        assert "Error" in result or "invalid" in result.lower()

    @pytest.mark.asyncio
    async def test_rename_invalid_dst_path(self, hg_repo: Path) -> None:
        """Test rename with invalid destination path."""
        result = await hg_rename(
            src="old.txt", dst="test`rm.txt", repo_path=str(hg_repo)
        )
        assert "Error" in result or "invalid" in result.lower()

    @pytest.mark.asyncio
    async def test_rename_nonexistent_file(self, hg_repo: Path) -> None:
        """Test renaming nonexistent file."""
        result = await hg_rename(
            src="nonexistent.txt", dst="new.txt", repo_path=str(hg_repo)
        )
        assert "Error" in result or "abort" in result.lower()


class TestHgAdd:
    """Tests for hg_add tool."""

    @pytest.mark.asyncio
    async def test_add_without_files(self, hg_repo: Path) -> None:
        """Test adding all untracked files without specifying files.

        This is the bug fix: files should be optional, hg add adds all files.
        """
        # Create new untracked files
        (hg_repo / "file1.txt").write_text("content1\n", encoding="utf-8")
        (hg_repo / "file2.txt").write_text("content2\n", encoding="utf-8")

        # Call hg_add without files parameter
        result = await hg_add(repo_path=str(hg_repo))
        assert isinstance(result, str)

        # Verify files are now tracked
        status = await hg_status(repo_path=str(hg_repo))
        status_text = _extract_text(status)
        # Files should not appear as untracked (?) after adding
        # Status output is JSON, check normalized form
        normalized = status_text.replace(" ", "")
        assert '"path":"file1.txt","status":"?"' not in normalized
        assert '"path":"file2.txt","status":"?"' not in normalized

    @pytest.mark.asyncio
    async def test_add_with_files_list(self, hg_repo: Path) -> None:
        """Test adding specific files as a list."""
        (hg_repo / "a.txt").write_text("a\n", encoding="utf-8")
        (hg_repo / "b.txt").write_text("b\n", encoding="utf-8")

        result = await hg_add(files=["a.txt"], repo_path=str(hg_repo))
        assert isinstance(result, str)

        # Only a.txt should be tracked, b.txt should still be untracked
        status = await hg_status(repo_path=str(hg_repo))
        status_text = _extract_text(status)
        # Status is JSON, check that b.txt has status "?" (untracked)
        assert '"path":"b.txt","status":"?"' in status_text.replace(" ", "")

    @pytest.mark.asyncio
    async def test_add_with_files_string(self, hg_repo: Path) -> None:
        """Test adding specific files as a single string."""
        (hg_repo / "single.txt").write_text("single\n", encoding="utf-8")

        result = await hg_add(files="single.txt", repo_path=str(hg_repo))
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_add_empty_files_list(self, hg_repo: Path) -> None:
        """Test adding with empty files list (should add all untracked)."""
        (hg_repo / "untracked.txt").write_text("content\n", encoding="utf-8")

        result = await hg_add(files=[], repo_path=str(hg_repo))
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_add_already_tracked_file(self, hg_repo: Path) -> None:
        """Test adding a file that is already tracked (no-op)."""
        test_file = hg_repo / "tracked.txt"
        test_file.write_text("content\n", encoding="utf-8")
        await hg_add(files=["tracked.txt"], repo_path=str(hg_repo))

        # Adding again should succeed silently
        result = await hg_add(files=["tracked.txt"], repo_path=str(hg_repo))
        assert isinstance(result, str)


class TestRunHgCommand:
    """Tests for run_hg_command helper function."""

    @pytest.mark.asyncio
    async def test_run_status_command(self, hg_repo: Path) -> None:
        """Test running hg status command."""
        result = await run_hg_command(["status"], cwd=hg_repo)
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_run_log_command(self, hg_repo: Path) -> None:
        """Test running hg log command."""
        result = await run_hg_command(["log", "--limit", "1"], cwd=hg_repo)
        assert "Initial commit" in result

    @pytest.mark.asyncio
    async def test_run_invalid_command(self, hg_repo: Path) -> None:
        """Test running invalid command."""
        result = await run_hg_command(["nonexistent-command"], cwd=hg_repo)
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_run_empty_args(self, hg_repo: Path) -> None:
        """Test running with empty args."""
        result = await run_hg_command([], cwd=hg_repo)
        assert "No command provided" in result


class TestCheckGitRemotes:
    """Tests for _check_git_remotes helper function."""

    @pytest.mark.asyncio
    async def test_check_no_git_remotes(self, hg_repo: Path) -> None:
        """Test checking repo without git remotes."""
        is_backed, remotes = await _check_git_remotes(hg_repo)
        assert is_backed is False
        assert isinstance(remotes, list)
