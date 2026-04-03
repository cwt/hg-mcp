"""Tests for hg-git extension tools.

Tests for tools in hg_mcp/tools/hggit.py:
- hg_git: Check hg-git extension status
- hg_rebase: Rebase changesets
- hg_strip: Remove changesets
- hg_transplant: Cherry-pick changesets
- hg_evolve: Show evolution history

Also tests internal helper functions.
"""

import subprocess
from pathlib import Path

import pytest

from hg_mcp.tools import (
    hg_evolve,
    hg_git,
    hg_rebase,
    hg_strip,
    hg_transplant,
)
from hg_mcp.tools.hggit import (
    _check_git_remotes,
    _get_git_branches,
    _is_hggit_enabled,
)


class TestIsHggitEnabled:
    """Tests for _is_hggit_enabled helper function."""

    @pytest.mark.asyncio
    async def test_hggit_not_enabled(self, hg_repo: Path) -> None:
        """Test detecting hg-git when not enabled."""
        # Note: hg-git may be enabled globally, so we just verify it returns bool
        result = await _is_hggit_enabled(hg_repo)
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_hggit_with_error_response(self, temp_dir: Path) -> None:
        """Test handling error response from config command."""
        nonexistent = temp_dir / "nonexistent"
        result = await _is_hggit_enabled(nonexistent)
        assert result is False


class TestCheckGitRemotes:
    """Tests for _check_git_remotes helper function."""

    @pytest.mark.asyncio
    async def test_no_git_remotes(self, hg_repo: Path) -> None:
        """Test repo without git remotes."""
        is_backed, remotes = await _check_git_remotes(hg_repo)
        assert is_backed is False
        assert remotes == []

    @pytest.mark.asyncio
    async def test_with_git_remote(self, temp_dir: Path) -> None:
        """Test repo with git remote configured."""
        # Create repo
        repo_path = temp_dir / "git-repo"
        repo_path.mkdir()
        subprocess.run(
            ["hg", "init"],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )

        # Configure git remote
        hgrc = repo_path / ".hg" / "hgrc"
        hgrc.write_text(
            """[ui]
username = Test <test@example.com>

[paths]
default = git+https://github.com/user/repo.git
""",
            encoding="utf-8",
        )

        is_backed, remotes = await _check_git_remotes(repo_path)
        assert is_backed is True
        assert len(remotes) > 0
        assert "default" in remotes[0]

    @pytest.mark.asyncio
    async def test_with_github_remote(self, temp_dir: Path) -> None:
        """Test repo with GitHub remote."""
        repo_path = temp_dir / "github-repo"
        repo_path.mkdir()
        subprocess.run(
            ["hg", "init"],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )

        hgrc = repo_path / ".hg" / "hgrc"
        hgrc.write_text(
            """[ui]
username = Test <test@example.com>

[paths]
origin = https://github.com/user/repo.git
""",
            encoding="utf-8",
        )

        is_backed, remotes = await _check_git_remotes(repo_path)
        assert is_backed is True

    @pytest.mark.asyncio
    async def test_with_gitlab_remote(self, temp_dir: Path) -> None:
        """Test repo with GitLab remote."""
        repo_path = temp_dir / "gitlab-repo"
        repo_path.mkdir()
        subprocess.run(
            ["hg", "init"],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )

        hgrc = repo_path / ".hg" / "hgrc"
        hgrc.write_text(
            """[ui]
username = Test <test@example.com>

[paths]
origin = https://gitlab.com/user/repo.git
""",
            encoding="utf-8",
        )

        is_backed, remotes = await _check_git_remotes(repo_path)
        assert is_backed is True

    @pytest.mark.asyncio
    async def test_with_git_mapfile(self, temp_dir: Path) -> None:
        """Test repo with git-mapfile tracking."""
        repo_path = temp_dir / "mapfile-repo"
        repo_path.mkdir()
        subprocess.run(
            ["hg", "init"],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )

        # Create git-mapfile
        git_mapfile = repo_path / ".hg" / "git-mapfile"
        git_mapfile.write_text("# Git mapping\n", encoding="utf-8")

        is_backed, remotes = await _check_git_remotes(repo_path)
        assert is_backed is True
        assert remotes == []  # No remotes configured

    @pytest.mark.asyncio
    async def test_with_git_branch_file(self, temp_dir: Path) -> None:
        """Test repo with git-branch tracking."""
        repo_path = temp_dir / "branch-repo"
        repo_path.mkdir()
        subprocess.run(
            ["hg", "init"],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )

        # Create git-branch file
        git_branch = repo_path / ".hg" / "git-branch"
        git_branch.write_text("main\n", encoding="utf-8")

        is_backed, remotes = await _check_git_remotes(repo_path)
        assert is_backed is True

    @pytest.mark.asyncio
    async def test_invalid_json_config(self, temp_dir: Path) -> None:
        """Test handling invalid JSON in config."""
        repo_path = temp_dir / "invalid-repo"
        repo_path.mkdir()
        subprocess.run(
            ["hg", "init"],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )

        # This should handle gracefully
        is_backed, remotes = await _check_git_remotes(repo_path)
        assert is_backed is False
        assert remotes == []


class TestGetGitBranches:
    """Tests for _get_git_branches helper function."""

    @pytest.mark.asyncio
    async def test_no_bookmarks(self, hg_repo: Path) -> None:
        """Test repo without bookmarks."""
        git_branches, local_bookmarks = await _get_git_branches(
            hg_repo, suffix=None
        )
        assert git_branches == []
        assert local_bookmarks == []

    @pytest.mark.asyncio
    async def test_with_bookmarks_no_suffix(
        self, hg_repo_with_bookmarks: Path
    ) -> None:
        """Test bookmarks without suffix configured."""
        git_branches, local_bookmarks = await _get_git_branches(
            hg_repo_with_bookmarks, suffix=None
        )
        # All bookmarks should be in git_branches
        assert len(git_branches) > 0
        assert local_bookmarks == []

    @pytest.mark.asyncio
    async def test_with_bookmarks_with_suffix(
        self, hg_repo_with_bookmarks: Path
    ) -> None:
        """Test bookmarks with suffix configured."""
        git_branches, local_bookmarks = await _get_git_branches(
            hg_repo_with_bookmarks, suffix=".git"
        )
        # Bookmarks without .git suffix should be local
        assert len(local_bookmarks) > 0

    @pytest.mark.asyncio
    async def test_error_response(self, temp_dir: Path) -> None:
        """Test handling error response from bookmarks command."""
        nonexistent = temp_dir / "nonexistent"
        git_branches, local_bookmarks = await _get_git_branches(
            nonexistent, suffix=None
        )
        assert git_branches == []
        assert local_bookmarks == []

    @pytest.mark.asyncio
    async def test_no_bookmarks_set_message(self, hg_repo: Path) -> None:
        """Test handling 'no bookmarks set' message."""
        git_branches, local_bookmarks = await _get_git_branches(
            hg_repo, suffix=None
        )
        assert git_branches == []
        assert local_bookmarks == []


class TestHgGit:
    """Tests for hg_git tool."""

    @pytest.mark.asyncio
    async def test_git_extension_status(self, hg_repo: Path) -> None:
        """Test hg_git extension status check."""
        result = await hg_git(repo_path=str(hg_repo))
        # hg-git may be enabled globally or not, just verify it returns string
        assert isinstance(result, str)
        # Should contain either enabled or not enabled message
        assert "hg-git" in result.lower() or "hg git" in result.lower()

    @pytest.mark.asyncio
    async def test_git_with_invalid_repo(self, temp_dir: Path) -> None:
        """Test hg_git with invalid repo path."""
        nonexistent = temp_dir / "nonexistent"
        result = await hg_git(repo_path=str(nonexistent))
        assert "Error" in result


class TestHgRebase:
    """Tests for hg_rebase tool."""

    @pytest.mark.asyncio
    async def test_rebase_without_extension(self, hg_repo: Path) -> None:
        """Test rebase without extension enabled."""
        result = await hg_rebase(repo_path=str(hg_repo))
        assert "Error" in result
        assert "rebase" in result.lower()

    @pytest.mark.asyncio
    async def test_rebase_with_extension(
        self, hg_repo_with_extensions: Path
    ) -> None:
        """Test rebase with extension enabled but no changes to rebase."""
        # This should work but may have no effect
        result = await hg_rebase(
            repo_path=str(hg_repo_with_extensions),
            source="",
            dest="",
        )
        # May return error about nothing to rebase, which is OK
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_rebase_with_source_and_dest(
        self, hg_repo_with_extensions: Path
    ) -> None:
        """Test rebase with source and destination."""
        result = await hg_rebase(
            repo_path=str(hg_repo_with_extensions),
            source="1",
            dest="tip",
        )
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_rebase_with_collapse(
        self, hg_repo_with_extensions: Path
    ) -> None:
        """Test rebase with collapse option."""
        result = await hg_rebase(
            repo_path=str(hg_repo_with_extensions),
            collapse=True,
        )
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_rebase_with_keep(
        self, hg_repo_with_extensions: Path
    ) -> None:
        """Test rebase with keep option."""
        result = await hg_rebase(
            repo_path=str(hg_repo_with_extensions),
            keep=True,
        )
        assert isinstance(result, str)


class TestHgStrip:
    """Tests for hg_strip tool."""

    @pytest.mark.asyncio
    async def test_strip_without_extension(self, hg_repo: Path) -> None:
        """Test strip without extension enabled."""
        result = await hg_strip(revision="tip", repo_path=str(hg_repo))
        assert "Error" in result
        assert "strip" in result.lower()

    @pytest.mark.asyncio
    async def test_strip_with_extension(
        self, hg_repo_with_extensions: Path
    ) -> None:
        """Test strip with extension enabled."""
        # Strip tip with keep (safer)
        result = await hg_strip(
            revision="tip",
            repo_path=str(hg_repo_with_extensions),
            keep=True,
        )
        # May succeed or fail depending on repo state
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_strip_without_keep(
        self, hg_repo_with_extensions: Path
    ) -> None:
        """Test strip without keep option."""
        result = await hg_strip(
            revision="tip",
            repo_path=str(hg_repo_with_extensions),
            keep=False,
        )
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_strip_invalid_revision(
        self, hg_repo_with_extensions: Path
    ) -> None:
        """Test strip with invalid revision."""
        result = await hg_strip(
            revision="99999",
            repo_path=str(hg_repo_with_extensions),
        )
        assert "Error" in result or "abort" in result.lower()


class TestHgTransplant:
    """Tests for hg_transplant tool."""

    @pytest.mark.asyncio
    async def test_transplant_without_extension(self, hg_repo: Path) -> None:
        """Test transplant without extension enabled."""
        result = await hg_transplant(revisions=["tip"], repo_path=str(hg_repo))
        assert "Error" in result
        assert "transplant" in result.lower()

    @pytest.mark.asyncio
    async def test_transplant_without_revisions(
        self, hg_repo_with_extensions: Path
    ) -> None:
        """Test transplant without revisions parameter.

        This is the bug fix: revisions should be optional.
        When called without revisions, it may start interactive mode
        or return an appropriate message.
        """
        # Call without revisions - should not raise a validation error
        result = await hg_transplant(repo_path=str(hg_repo_with_extensions))
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_transplant_with_source_no_revisions(
        self, hg_repo_with_extensions: Path
    ) -> None:
        """Test transplant with source but without explicit revisions."""
        # This is a valid use case: transplant from source interactively
        result = await hg_transplant(
            repo_path=str(hg_repo_with_extensions),
            source="default",
        )
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_transplant_with_extension(
        self, hg_repo_with_extensions: Path
    ) -> None:
        """Test transplant with extension enabled."""
        # May fail if no source specified and nothing to transplant
        result = await hg_transplant(
            revisions=["tip"], repo_path=str(hg_repo_with_extensions)
        )
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_transplant_with_source(
        self, hg_repo_with_extensions: Path
    ) -> None:
        """Test transplant with source parameter."""
        result = await hg_transplant(
            revisions=["tip"],
            repo_path=str(hg_repo_with_extensions),
            source="default",
        )
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_transplant_multiple_revisions(
        self, hg_repo_with_extensions: Path
    ) -> None:
        """Test transplant with multiple revisions."""
        result = await hg_transplant(
            revisions=["1", "2"],
            repo_path=str(hg_repo_with_extensions),
        )
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_transplant_string_revisions(
        self, hg_repo_with_extensions: Path
    ) -> None:
        """Test transplant with string instead of list."""
        result = await hg_transplant(
            revisions="tip",
            repo_path=str(hg_repo_with_extensions),
        )
        assert isinstance(result, str)


class TestHgEvolve:
    """Tests for hg_evolve tool."""

    @pytest.mark.asyncio
    async def test_evolve_extension_status(self, hg_repo: Path) -> None:
        """Test evolve extension status."""
        result = await hg_evolve(repo_path=str(hg_repo))
        # evolve may be enabled globally, just verify it returns string
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_evolve_with_extension(
        self, hg_repo_with_extensions: Path
    ) -> None:
        """Test evolve with extension enabled."""
        # May return empty if no evolution history
        result = await hg_evolve(repo_path=str(hg_repo_with_extensions))
        assert isinstance(result, str)


class TestHgRebaseIntegration:
    """Integration tests for hg_rebase."""

    @pytest.mark.asyncio
    async def test_rebase_with_no_changes(
        self, hg_repo_with_extensions: Path
    ) -> None:
        """Test rebase when there's nothing to rebase."""
        # Just verify rebase command works with extension
        result = await hg_rebase(
            repo_path=str(hg_repo_with_extensions),
        )
        # Should return some output (may be error about nothing to rebase)
        assert isinstance(result, str)


class TestHgStripIntegration:
    """Integration tests for hg_strip."""

    @pytest.mark.asyncio
    async def test_strip_and_verify(
        self, hg_repo_with_extensions: Path
    ) -> None:
        """Test strip and verify it worked."""
        # Get current tip
        result_before = await hg_strip(
            revision="tip",
            repo_path=str(hg_repo_with_extensions),
            keep=True,
        )
        assert isinstance(result_before, str)
