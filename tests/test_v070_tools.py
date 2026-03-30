"""Tests for v0.7.0 new tools.

Tests the new tools added in v0.7.0:
- hg_amend
- hg_cat
- hg_bookmark_create
- hg_rename
- Command timeout in run_hg_command
"""

import json
import subprocess
from pathlib import Path

import pytest
from mcp.types import TextContent

from hg_mcp.main import (
    hg_amend,
    hg_bookmark_create,
    hg_bookmarks,
    hg_cat,
    hg_log,
    hg_rename,
    hg_status,
)


def _extract_text(result: str | list[TextContent]) -> str:
    """Extract text from test result (handles both str and list[TextContent])."""
    if isinstance(result, list):
        return "\n".join(
            item.text if isinstance(item, TextContent) else str(item)
            for item in result
        )
    return result


def _extract_json(
    result: str | list[TextContent],
) -> list[object] | dict[str, object]:
    """Extract and parse JSON from test result."""
    text = _extract_text(result)
    return json.loads(text)  # type: ignore[no-any-return]


class TestHgAmend:
    """Tests for hg_amend tool."""

    @pytest.mark.asyncio
    async def test_amend_without_message(
        self, hg_repo_with_commits: Path
    ) -> None:
        """Test amending current commit without changing message."""
        # Make a small change
        test_file = hg_repo_with_commits / "extra.txt"
        test_file.write_text("Extra content\n", encoding="utf-8")
        subprocess.run(
            ["hg", "add", "extra.txt"],
            cwd=hg_repo_with_commits,
            check=True,
            capture_output=True,
        )

        # Amend without message change
        result = await hg_amend(repo_path=str(hg_repo_with_commits))
        assert not result.startswith("Error:")

    @pytest.mark.asyncio
    async def test_amend_with_message(self, hg_repo_with_commits: Path) -> None:
        """Test amending current commit with new message."""
        # Make a small change
        test_file = hg_repo_with_commits / "extra.txt"
        test_file.write_text("Extra content\n", encoding="utf-8")
        subprocess.run(
            ["hg", "add", "extra.txt"],
            cwd=hg_repo_with_commits,
            check=True,
            capture_output=True,
        )

        # Amend with new message
        result = await hg_amend(
            message="Amended: new message", repo_path=str(hg_repo_with_commits)
        )
        assert not result.startswith("Error:")

        # Verify the message was updated
        log_result = await hg_log(repo_path=str(hg_repo_with_commits), limit=1)
        log_text = _extract_text(log_result)
        assert "Amended: new message" in log_text


class TestHgCat:
    """Tests for hg_cat tool."""

    @pytest.mark.asyncio
    async def test_cat_current_revision(
        self, hg_repo_with_commits: Path
    ) -> None:
        """Test viewing file content at current revision."""
        # Create a file with known content
        test_file = hg_repo_with_commits / "test.txt"
        expected_content = "Test content for cat\n"
        test_file.write_text(expected_content, encoding="utf-8")
        subprocess.run(
            ["hg", "add", "test.txt"],
            cwd=hg_repo_with_commits,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["hg", "commit", "-m", "Add test file"],
            cwd=hg_repo_with_commits,
            check=True,
            capture_output=True,
        )

        # Cat the file
        result = await hg_cat(
            file="test.txt", repo_path=str(hg_repo_with_commits)
        )
        assert not result.startswith("Error:")
        assert expected_content.strip() in result

    @pytest.mark.asyncio
    async def test_cat_specific_revision(
        self, hg_repo_with_commits: Path
    ) -> None:
        """Test viewing file content at specific revision."""
        # Create file in revision 2
        test_file = hg_repo_with_commits / "file2.txt"
        original_content = test_file.read_text(encoding="utf-8")

        # Cat at revision 2
        result = await hg_cat(
            file="file2.txt", repo_path=str(hg_repo_with_commits), revision="2"
        )
        assert not result.startswith("Error:")
        assert original_content.strip() in result

    @pytest.mark.asyncio
    async def test_cat_nonexistent_file(
        self, hg_repo_with_commits: Path
    ) -> None:
        """Test viewing a file that doesn't exist."""
        result = await hg_cat(
            file="nonexistent.txt", repo_path=str(hg_repo_with_commits)
        )
        assert result.startswith("Error:")


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
            revision="2",
        )
        assert not result.startswith("Error:")

        # Verify bookmark was created at correct revision
        bookmarks = await hg_bookmarks(repo_path=str(hg_repo_with_commits))
        bookmarks_data = _extract_json(bookmarks)
        test_bookmark = None
        for bm in bookmarks_data:
            if isinstance(bm, dict) and bm.get("bookmark") == "old-bookmark":
                test_bookmark = bm
                break

        assert test_bookmark is not None
        assert test_bookmark.get("rev") == 2

    @pytest.mark.asyncio
    async def test_create_existing_bookmark(
        self, hg_repo_with_commits: Path
    ) -> None:
        """Test creating a bookmark that already exists."""
        # Create bookmark first time
        await hg_bookmark_create(
            name="dup-bookmark", repo_path=str(hg_repo_with_commits)
        )

        # Try to create again (should fail or update)
        # hg allows updating bookmarks, so this might succeed
        # The important thing is it doesn't crash
        await hg_bookmark_create(
            name="dup-bookmark", repo_path=str(hg_repo_with_commits)
        )


class TestHgRename:
    """Tests for hg_rename tool."""

    @pytest.mark.asyncio
    async def test_rename_file(self, hg_repo_with_commits: Path) -> None:
        """Test renaming a tracked file."""
        # Create and commit a file
        test_file = hg_repo_with_commits / "old_name.txt"
        test_file.write_text("Content\n", encoding="utf-8")
        subprocess.run(
            ["hg", "add", "old_name.txt"],
            cwd=hg_repo_with_commits,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["hg", "commit", "-m", "Add file to rename"],
            cwd=hg_repo_with_commits,
            check=True,
            capture_output=True,
        )

        # Rename the file
        result = await hg_rename(
            src="old_name.txt",
            dst="new_name.txt",
            repo_path=str(hg_repo_with_commits),
        )
        assert not result.startswith("Error:")

        # Verify file was renamed
        status_result = await hg_status(repo_path=str(hg_repo_with_commits))
        status_text = _extract_text(status_result)
        assert "old_name.txt" in status_text or "new_name.txt" in status_text

    @pytest.mark.asyncio
    async def test_rename_nonexistent_file(
        self, hg_repo_with_commits: Path
    ) -> None:
        """Test renaming a file that doesn't exist."""
        result = await hg_rename(
            src="nonexistent.txt",
            dst="new.txt",
            repo_path=str(hg_repo_with_commits),
        )
        assert result.startswith("Error:")


class TestCommandTimeout:
    """Tests for command timeout in run_hg_command."""

    @pytest.mark.asyncio
    async def test_timeout_on_slow_command(
        self, hg_repo_with_commits: Path
    ) -> None:
        """Test that slow commands timeout properly."""
        from hg_mcp.main import run_hg_command

        # Use a shell command that sleeps via hg debugrun
        # Since hg debug sleep doesn't exist, we use a workaround
        # by calling a slow hg command with artificial delay
        result = await run_hg_command(
            args=["log", "-l", "1000"],  # Large limit to make it slower
            cwd=hg_repo_with_commits,
            timeout=0.001,  # Very short timeout to force timeout
        )

        assert result.startswith("Error:")
        assert "timed out" in result.lower()

    @pytest.mark.asyncio
    async def test_normal_command_completes(
        self, hg_repo_with_commits: Path
    ) -> None:
        """Test that normal commands complete within timeout."""
        from hg_mcp.main import run_hg_command

        # Normal status command should complete quickly
        result = await run_hg_command(
            args=["status"],
            cwd=hg_repo_with_commits,
            timeout=5.0,  # 5 second timeout
        )

        # Should not timeout
        assert "timed out" not in result.lower()
