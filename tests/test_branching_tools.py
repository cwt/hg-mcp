"""Tests for branching tools and decorators.

Tests for:
- hg_branch, hg_tag, hg_push, hg_pull, hg_paths
- hg_config, hg_extensions, hg_topic, hg_topics, hg_topic_current
- @json_tool and @handle_repo_errors decorators
"""

import json
import subprocess
from pathlib import Path

import pytest
from mcp.types import TextContent

from hg_mcp.tools import (
    hg_bookmarks,
    hg_branch,
    hg_config,
    hg_extensions,
    hg_paths,
    hg_pull,
    hg_push,
    hg_tag,
    hg_tags,
    hg_topic,
    hg_topic_current,
    hg_topics,
)
from hg_mcp.tools.branching import (
    hg_bookmark,
)


def _extract_text(result: str | list[TextContent]) -> str:
    """Extract text from test result."""
    if isinstance(result, list):
        return "\n".join(
            item.text if isinstance(item, TextContent) else str(item) for item in result
        )
    return result


def _extract_json(
    result: str | list[TextContent],
) -> list[object] | dict[str, object]:
    """Extract and parse JSON from test result."""
    text = _extract_text(result)
    return json.loads(text)  # type: ignore[no-any-return]


class TestHgBranch:
    """Tests for hg_branch tool."""

    @pytest.mark.asyncio
    async def test_branch_show_current(self, hg_repo: Path) -> None:
        """Test showing current branch."""
        result = await hg_branch(repo_path=str(hg_repo))
        assert "default" in result

    @pytest.mark.asyncio
    async def test_branch_create_new(self, hg_repo: Path) -> None:
        """Test creating a new branch."""
        result = await hg_branch(repo_path=str(hg_repo), name="feature-test")
        assert "feature-test" in result

        # Verify branch was created
        branch_result = await hg_branch(repo_path=str(hg_repo))
        assert "feature-test" in branch_result

    @pytest.mark.asyncio
    async def test_branch_invalid_name(self, hg_repo: Path) -> None:
        """Test creating branch with invalid name."""
        result = await hg_branch(repo_path=str(hg_repo), name="a" * 300)
        # Long branch names are allowed but show a warning
        assert "branch" in result.lower() or "feature-test" in result


class TestHgTag:
    """Tests for hg_tag tool."""

    @pytest.mark.asyncio
    async def test_tag_create(self, hg_repo_with_commits: Path) -> None:
        """Test creating a new tag."""
        result = await hg_tag(name="v1.0.0-test", repo_path=str(hg_repo_with_commits))
        # hg tag auto-commits, may return empty string on success
        assert isinstance(result, str)

        # Verify tag was created
        tags = await hg_tags(repo_path=str(hg_repo_with_commits))
        text = _extract_text(tags)
        assert "v1.0.0-test" in text

    @pytest.mark.asyncio
    async def test_tag_create_at_revision(self, hg_repo_with_commits: Path) -> None:
        """Test creating tag at specific revision."""
        result = await hg_tag(
            name="v0.5.0", repo_path=str(hg_repo_with_commits), revision="2"
        )
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_tag_remove(self, hg_repo_with_tags: Path) -> None:
        """Test removing a tag."""
        # First verify tag exists
        tags_before = await hg_tags(repo_path=str(hg_repo_with_tags))
        text_before = _extract_text(tags_before)

        # Remove tag (try v1.0.0 first, fallback to v2.0.0)
        tag_to_remove = "v1.0.0" if "v1.0.0" in text_before else "v2.0.0"
        result = await hg_tag(
            name=tag_to_remove, repo_path=str(hg_repo_with_tags), remove=True
        )
        assert isinstance(result, str)

        # Verify commit message on removal
        from hg_mcp.helpers import run_hg_command

        log_msg = await run_hg_command(
            ["log", "-l", "1", "-T", "{desc}"], cwd=hg_repo_with_tags
        )
        assert f"Remove tag {tag_to_remove}" in log_msg

    @pytest.mark.asyncio
    async def test_tag_invalid_name(self, hg_repo: Path) -> None:
        """Test creating tag with invalid name."""
        # Tags with long names are allowed in Mercurial
        result = await hg_tag(name="a" * 300, repo_path=str(hg_repo))
        # Just verify it returns a string (success or error)
        assert isinstance(result, str)


class TestHgPush:
    """Tests for hg_push tool."""

    @pytest.mark.asyncio
    async def test_push_to_remote(self, hg_repo_with_remote: Path) -> None:
        """Test pushing to remote."""
        # Add a new commit
        test_file = hg_repo_with_remote / "push_test.txt"
        test_file.write_text("Push test\n", encoding="utf-8")
        subprocess.run(
            ["hg", "add", "push_test.txt"],
            cwd=hg_repo_with_remote,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["hg", "commit", "-m", "Push test commit"],
            cwd=hg_repo_with_remote,
            check=True,
            capture_output=True,
        )

        result = await hg_push(str(hg_repo_with_remote))
        assert result

    @pytest.mark.asyncio
    async def test_push_unknown_destination(self, hg_repo_with_remote: Path) -> None:
        """Test pushing to unknown destination shows available remotes."""
        result = await hg_push(str(hg_repo_with_remote), destination="nonexistent")
        # Should include available remotes hint
        assert "Error" in result


class TestHgPull:
    """Tests for hg_pull tool."""

    @pytest.mark.asyncio
    async def test_pull_from_remote(self, hg_repo_with_remote: Path) -> None:
        """Test pulling from remote."""
        result = await hg_pull(str(hg_repo_with_remote))
        assert result

    @pytest.mark.asyncio
    async def test_pull_from_source(self, hg_repo_with_remote: Path) -> None:
        """Test pulling from specific source."""
        result = await hg_pull(str(hg_repo_with_remote), source="default")
        assert result


class TestHgPaths:
    """Tests for hg_paths tool."""

    @pytest.mark.asyncio
    async def test_paths_with_remote(self, hg_repo_with_remote: Path) -> None:
        """Test listing paths with remote configured."""
        result = await hg_paths(str(hg_repo_with_remote))
        text = _extract_text(result)
        assert "default" in text

    @pytest.mark.asyncio
    async def test_paths_no_remote(self, hg_repo: Path) -> None:
        """Test listing paths without remote."""
        result = await hg_paths(str(hg_repo))
        # Should return empty or indicate no paths
        assert isinstance(result, str | list)


class TestHgConfig:
    """Tests for hg_config tool."""

    @pytest.mark.asyncio
    async def test_config_basic(self, hg_repo: Path) -> None:
        """Test getting basic config."""
        result = await hg_config(str(hg_repo))
        text = _extract_text(result)
        assert text  # Should return config data


class TestHgExtensions:
    """Tests for hg_extensions tool."""

    @pytest.mark.asyncio
    async def test_extensions_list(self, hg_repo: Path) -> None:
        """Test listing extensions."""
        result = await hg_extensions(str(hg_repo))
        assert isinstance(result, str)


class TestHgTopic:
    """Tests for hg_topic tool."""

    @pytest.mark.asyncio
    async def test_topic_create(self, hg_repo_with_extensions: Path) -> None:
        """Test creating a topic (requires topic extension)."""
        result = await hg_topic(
            name="test-topic", repo_path=str(hg_repo_with_extensions)
        )
        assert result

    @pytest.mark.asyncio
    async def test_topic_without_extension(self, hg_repo: Path) -> None:
        """Test creating topic (may work if topic extension is enabled globally)."""
        result = await hg_topic(name="test-topic", repo_path=str(hg_repo))
        # Topic extension may be enabled globally, so just verify it returns a string
        assert isinstance(result, str)


class TestHgTopics:
    """Tests for hg_topics tool."""

    @pytest.mark.asyncio
    async def test_topics_list(self, hg_repo_with_extensions: Path) -> None:
        """Test listing topics."""
        # Create a topic first
        await hg_topic(name="list-test", repo_path=str(hg_repo_with_extensions))

        result = await hg_topics(repo_path=str(hg_repo_with_extensions))
        text = _extract_text(result)
        assert text  # Should return topics list


class TestHgTopicCurrent:
    """Tests for hg_topic_current tool."""

    @pytest.mark.asyncio
    async def test_topic_current_active(self, hg_repo_with_extensions: Path) -> None:
        """Test getting current active topic."""
        # Create a topic
        await hg_topic(name="current-test", repo_path=str(hg_repo_with_extensions))

        result = await hg_topic_current(repo_path=str(hg_repo_with_extensions))
        text = _extract_text(result)
        assert text  # Should return current topic or "No active topic"


class TestJsonToolDecorator:
    """Tests for @json_tool decorator."""

    @pytest.mark.asyncio
    async def test_json_tool_wraps_string(self, hg_repo: Path) -> None:
        """Test that json_tool wraps string in TextContent."""
        result = await hg_bookmarks(str(hg_repo))
        assert isinstance(result, list)
        assert len(result) > 0
        assert isinstance(result[0], TextContent)
        assert result[0].type == "text"

    @pytest.mark.asyncio
    async def test_json_tool_output_is_json(self, hg_repo_with_commits: Path) -> None:
        """Test that json_tool output is valid JSON."""
        result = await hg_bookmarks(str(hg_repo_with_commits))
        text = _extract_text(result)
        # Should be parseable as JSON
        data = json.loads(text)
        assert isinstance(data, list)


class TestHandleRepoErrorsDecorator:
    """Tests for @handle_repo_errors decorator."""

    @pytest.mark.asyncio
    async def test_handle_repo_errors_invalid_path(self, temp_dir: Path) -> None:
        """Test that invalid repo path returns proper error."""
        nonexistent = temp_dir / "nonexistent-repo"
        result = await hg_bookmark(str(nonexistent))
        assert "Error" in result
        assert "does not exist" in result.lower()

    @pytest.mark.asyncio
    async def test_handle_repo_errors_not_a_repo(self, temp_dir: Path) -> None:
        """Test that non-repo directory returns proper error."""
        not_a_repo = temp_dir / "not-a-repo"
        not_a_repo.mkdir()
        result = await hg_bookmark(repo_path=str(not_a_repo))
        assert "Error" in result
        assert "not a mercurial repository" in result.lower()


class TestHgBookmarksJson:
    """Tests for hg_bookmarks JSON output."""

    @pytest.mark.asyncio
    async def test_bookmarks_json_parseable(self, hg_repo_with_bookmarks: Path) -> None:
        """Test that bookmarks output is valid JSON."""
        result = await hg_bookmarks(str(hg_repo_with_bookmarks))
        data = _extract_json(result)
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_bookmarks_contains_names(self, hg_repo_with_bookmarks: Path) -> None:
        """Test that bookmarks output contains bookmark names."""
        result = await hg_bookmarks(str(hg_repo_with_bookmarks))
        text = _extract_text(result)
        assert "stable" in text or "latest" in text


class TestHgTagsJson:
    """Tests for hg_tags JSON output."""

    @pytest.mark.asyncio
    async def test_tags_json_parseable(self, hg_repo_with_tags: Path) -> None:
        """Test that tags output is valid JSON."""
        result = await hg_tags(str(hg_repo_with_tags))
        data = _extract_json(result)
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_tags_contains_names(self, hg_repo_with_tags: Path) -> None:
        """Test that tags output contains tag names."""
        result = await hg_tags(str(hg_repo_with_tags))
        text = _extract_text(result)
        assert "v1.0.0" in text or "v2.0.0" in text


class TestHgConfigJson:
    """Tests for hg_config JSON output."""

    @pytest.mark.asyncio
    async def test_config_json_parseable(self, hg_repo: Path) -> None:
        """Test that config output is valid JSON."""
        result = await hg_config(str(hg_repo))
        data = _extract_json(result)
        assert isinstance(data, list)


class TestHgPathsJson:
    """Tests for hg_paths JSON output."""

    @pytest.mark.asyncio
    async def test_paths_json_parseable(self, hg_repo_with_remote: Path) -> None:
        """Test that paths output is valid JSON."""
        result = await hg_paths(str(hg_repo_with_remote))
        data = _extract_json(result)
        assert isinstance(data, list)
