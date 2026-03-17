"""Tests for Phase 1 core workflow tools.

Tests the 11 essential workflow tools added in Phase 1:
- hg_annotate, hg_backout, hg_export, hg_import
- hg_heads, hg_incoming, hg_outgoing
- hg_files, hg_summary, hg_verify, hg_identify
"""

import json
import subprocess
from pathlib import Path

import pytest
from mcp.types import TextContent

from hg_mcp.main import (
    hg_annotate,
    hg_backout,
    hg_diff,
    hg_export,
    hg_files,
    hg_heads,
    hg_identify,
    hg_import,
    hg_incoming,
    hg_outgoing,
    hg_summary,
    hg_verify,
)


def _extract_text(result: str | list[TextContent]) -> str:
    """Extract text from test result (handles both str and list[TextContent])."""
    if isinstance(result, list):
        # Extract text from TextContent objects
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


class TestHgAnnotate:
    """Tests for hg_annotate tool."""

    @pytest.mark.asyncio
    async def test_annotate_single_file(
        self, hg_repo_with_commits: Path
    ) -> None:
        """Test annotating a single file."""
        result = await hg_annotate(
            str(hg_repo_with_commits), files=["README.txt"]
        )
        text = _extract_text(result)
        assert (
            "Test User" in text
            or "test@example.com" in text
            or "Initial" in text
        )

    @pytest.mark.asyncio
    async def test_annotate_with_revision(
        self, hg_repo_with_commits: Path
    ) -> None:
        """Test annotating with specific revision."""
        result = await hg_annotate(
            str(hg_repo_with_commits), revision="2", files=["file2.txt"]
        )
        text = _extract_text(result)
        assert text  # Should not be empty

    @pytest.mark.asyncio
    async def test_annotate_specific_file(
        self, hg_repo_with_commits: Path
    ) -> None:
        """Test annotating a specific file."""
        result = await hg_annotate(
            str(hg_repo_with_commits), files=["file2.txt"]
        )
        text = _extract_text(result)
        assert "file2.txt" in text or "Content 2" in text


class TestHgBackout:
    """Tests for hg_backout tool."""

    @pytest.mark.asyncio
    async def test_backout_without_merge(
        self, hg_repo_with_commits: Path
    ) -> None:
        """Test backing out a changeset without automatic merge."""
        # Backout revision 3 without committing (no-commit mode)
        result = await hg_backout("3", str(hg_repo_with_commits))
        # Should prepare backout but not commit
        assert "backed out" in result.lower() or "commit" in result.lower()

    @pytest.mark.asyncio
    async def test_backout_with_merge(self, hg_repo_with_commits: Path) -> None:
        """Test backing out with automatic merge commit."""
        result = await hg_backout("3", str(hg_repo_with_commits), merge=True)
        assert result  # Should complete without error


class TestHgExport:
    """Tests for hg_export tool."""

    @pytest.mark.asyncio
    async def test_export_specific_revision(
        self, hg_repo_with_commits: Path, temp_dir: Path
    ) -> None:
        """Test exporting a specific revision."""
        output_file = temp_dir / "test.patch"
        await hg_export(
            str(hg_repo_with_commits), revisions=["3"], output=str(output_file)
        )
        assert output_file.exists()
        content = output_file.read_text(encoding="utf-8")
        assert "Commit 3" in content or "diff" in content.lower()

    @pytest.mark.asyncio
    async def test_export_multiple_revisions(
        self, hg_repo_with_commits: Path, temp_dir: Path
    ) -> None:
        """Test exporting multiple revisions."""
        output_pattern = temp_dir / "test-%r.patch"
        await hg_export(
            str(hg_repo_with_commits),
            revisions=["2", "3"],
            output=str(output_pattern),
        )
        # Should create patch files


class TestHgImport:
    """Tests for hg_import tool."""

    @pytest.mark.asyncio
    async def test_import_patch(
        self, hg_repo_with_commits: Path, temp_dir: Path
    ) -> None:
        """Test importing a patch file."""
        # First export a revision
        patch_file = temp_dir / "test.patch"
        await hg_export(
            str(hg_repo_with_commits), revisions=["3"], output=str(patch_file)
        )

        # Strip the revision
        subprocess.run(
            ["hg", "strip", "-r", "3", "--keep"],
            cwd=hg_repo_with_commits,
            check=True,
            capture_output=True,
        )

        # Import it back
        result = await hg_import(
            str(hg_repo_with_commits), patches=[str(patch_file)]
        )
        assert result  # Should complete without error

    @pytest.mark.asyncio
    async def test_import_no_commit(
        self, hg_repo_with_commits: Path, temp_dir: Path
    ) -> None:
        """Test importing without automatic commit."""
        patch_file = temp_dir / "test.patch"
        await hg_export(
            str(hg_repo_with_commits), revisions=["3"], output=str(patch_file)
        )

        subprocess.run(
            ["hg", "strip", "-r", "3", "--keep"],
            cwd=hg_repo_with_commits,
            check=True,
            capture_output=True,
        )

        result = await hg_import(
            str(hg_repo_with_commits), patches=[str(patch_file)], no_commit=True
        )
        assert result  # Should apply without committing


class TestHgHeads:
    """Tests for hg_heads tool."""

    @pytest.mark.asyncio
    async def test_heads_default(self, hg_repo_with_commits: Path) -> None:
        """Test listing all heads."""
        result = await hg_heads(str(hg_repo_with_commits))
        text = _extract_text(result)
        assert "tip" in text or "default" in text

    @pytest.mark.asyncio
    async def test_heads_active_only(self, hg_repo_with_commits: Path) -> None:
        """Test listing only active heads."""
        result = await hg_heads(str(hg_repo_with_commits), active=True)
        text = _extract_text(result)
        assert text  # Should return active head

    @pytest.mark.asyncio
    async def test_heads_with_branch(self, hg_repo_with_branches: Path) -> None:
        """Test listing heads for specific branch."""
        result = await hg_heads(str(hg_repo_with_branches), branch="feature")
        text = _extract_text(result)
        assert "feature" in text


class TestHgIncoming:
    """Tests for hg_incoming tool."""

    @pytest.mark.asyncio
    async def test_incoming_no_changes(self, hg_repo_with_remote: Path) -> None:
        """Test incoming when repos are in sync."""
        result = await hg_incoming(str(hg_repo_with_remote))
        # Should indicate no new changes or return empty
        assert isinstance(result, str | list)

    @pytest.mark.asyncio
    async def test_incoming_with_changes(self, temp_dir: Path) -> None:
        """Test incoming when remote has new changes."""
        # Create origin with commits
        origin_path = temp_dir / "origin"
        origin_path.mkdir()
        subprocess.run(
            ["hg", "init"],
            cwd=origin_path,
            check=True,
            capture_output=True,
        )

        # Add commit to origin
        test_file = origin_path / "origin_file.txt"
        test_file.write_text("From origin\n", encoding="utf-8")
        subprocess.run(
            ["hg", "add", "origin_file.txt"],
            cwd=origin_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["hg", "commit", "-m", "Origin commit"],
            cwd=origin_path,
            check=True,
            capture_output=True,
        )

        # Create local repo with remote
        local_path = temp_dir / "local"
        local_path.mkdir()
        subprocess.run(
            ["hg", "init"],
            cwd=local_path,
            check=True,
            capture_output=True,
        )

        hgrc = local_path / ".hg" / "hgrc"
        hgrc.write_text(
            f"""[ui]
username = Test User <test@example.com>

[paths]
default = {origin_path}
""",
            encoding="utf-8",
        )

        # Test incoming
        result = await hg_incoming(str(local_path))
        text = _extract_text(result)
        assert "Origin commit" in text or "changeset" in text.lower()


class TestHgOutgoing:
    """Tests for hg_outgoing tool."""

    @pytest.mark.asyncio
    async def test_outgoing_no_changes(self, hg_repo_with_remote: Path) -> None:
        """Test outgoing when repos are in sync."""
        result = await hg_outgoing(str(hg_repo_with_remote))
        # Should indicate no outgoing changes
        assert isinstance(result, str | list)

    @pytest.mark.asyncio
    async def test_outgoing_with_changes(self, temp_dir: Path) -> None:
        """Test outgoing when local has new changes."""
        # Create origin
        origin_path = temp_dir / "origin"
        origin_path.mkdir()
        subprocess.run(
            ["hg", "init"],
            cwd=origin_path,
            check=True,
            capture_output=True,
        )

        # Initial commit on origin
        test_file = origin_path / "README.txt"
        test_file.write_text("Initial\n", encoding="utf-8")
        subprocess.run(
            ["hg", "add", "README.txt"],
            cwd=origin_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["hg", "commit", "-m", "Initial commit"],
            cwd=origin_path,
            check=True,
            capture_output=True,
        )

        # Clone by pulling to local
        local_path = temp_dir / "local"
        local_path.mkdir()
        subprocess.run(
            ["hg", "init"],
            cwd=local_path,
            check=True,
            capture_output=True,
        )

        hgrc = local_path / ".hg" / "hgrc"
        hgrc.write_text(
            f"""[ui]
username = Test User <test@example.com>

[paths]
default = {origin_path}
""",
            encoding="utf-8",
        )

        subprocess.run(
            ["hg", "pull"],
            cwd=local_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["hg", "update"],
            cwd=local_path,
            check=True,
            capture_output=True,
        )

        # Add new commit to local
        new_file = local_path / "local_file.txt"
        new_file.write_text("Local change\n", encoding="utf-8")
        subprocess.run(
            ["hg", "add", "local_file.txt"],
            cwd=local_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["hg", "commit", "-m", "Local commit"],
            cwd=local_path,
            check=True,
            capture_output=True,
        )

        # Test outgoing
        result = await hg_outgoing(str(local_path))
        text = _extract_text(result)
        assert "Local commit" in text or "changeset" in text.lower()


class TestHgFiles:
    """Tests for hg_files tool."""

    @pytest.mark.asyncio
    async def test_files_lists_tracked(
        self, hg_repo_with_commits: Path
    ) -> None:
        """Test that files lists all tracked files."""
        result = await hg_files(str(hg_repo_with_commits))
        text = _extract_text(result)
        assert "README.txt" in text
        assert "file2.txt" in text or "file3.txt" in text


class TestHgSummary:
    """Tests for hg_summary tool."""

    @pytest.mark.asyncio
    async def test_summary_shows_branch(
        self, hg_repo_with_commits: Path
    ) -> None:
        """Test that summary shows current branch."""
        result = await hg_summary(str(hg_repo_with_commits))
        text = _extract_text(result)
        assert "default" in text or "branch" in text.lower()

    @pytest.mark.asyncio
    async def test_summary_shows_parent(
        self, hg_repo_with_commits: Path
    ) -> None:
        """Test that summary shows parent revision."""
        result = await hg_summary(str(hg_repo_with_commits))
        text = _extract_text(result)
        assert "parent" in text.lower() or "changeset" in text.lower()


class TestHgVerify:
    """Tests for hg_verify tool."""

    @pytest.mark.asyncio
    async def test_verify_clean_repo(self, hg_repo_with_commits: Path) -> None:
        """Test verify on a clean repository."""
        result = await hg_verify(str(hg_repo_with_commits))
        text = _extract_text(result)
        # Should not contain error indicators
        assert "abort" not in text.lower()
        assert "corrupt" not in text.lower()


class TestHgIdentify:
    """Tests for hg_identify tool."""

    @pytest.mark.asyncio
    async def test_identify_current_revision(
        self, hg_repo_with_commits: Path
    ) -> None:
        """Test identifying current working directory revision."""
        result = await hg_identify(str(hg_repo_with_commits))
        text = _extract_text(result)
        # Should contain revision hash or branch info
        assert text

    @pytest.mark.asyncio
    async def test_identify_specific_revision(
        self, hg_repo_with_commits: Path
    ) -> None:
        """Test identifying a specific revision."""
        result = await hg_identify(str(hg_repo_with_commits), revision="2")
        text = _extract_text(result)
        assert text


class TestHgDiff:
    """Tests for hg_diff tool."""

    @pytest.mark.asyncio
    async def test_diff_working_directory(
        self, hg_repo_with_commits: Path
    ) -> None:
        """Test diff of working directory (no revisions specified)."""
        result = await hg_diff(str(hg_repo_with_commits))
        text = _extract_text(result)
        assert isinstance(text, str)

    @pytest.mark.asyncio
    async def test_diff_with_revision_spec(
        self, hg_repo_with_commits: Path
    ) -> None:
        """Test diff with revision spec (e.g., '0..2')."""
        result = await hg_diff(str(hg_repo_with_commits), revisions="0..2")
        text = _extract_text(result)
        assert text

    @pytest.mark.asyncio
    async def test_diff_single_revision(
        self, hg_repo_with_commits: Path
    ) -> None:
        """Test diff with single revision."""
        result = await hg_diff(str(hg_repo_with_commits), revisions="1")
        text = _extract_text(result)
        assert text
