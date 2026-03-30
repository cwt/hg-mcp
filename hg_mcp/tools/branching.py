"""Branching tools for hg-mcp server - bookmarks, branches, tags, topics."""

import json

from mcp.types import TextContent

from hg_mcp.decorators import handle_repo_errors, json_tool
from hg_mcp.helpers import run_hg_command, validate_repo_path


@json_tool
@handle_repo_errors
async def hg_bookmarks(repo_path: str = ".") -> list[TextContent]:
    """List all bookmarks.

    Bookmarks are lightweight pointers to revisions (like Git branches).
    Unlike Mercurial branches, bookmarks can be moved and deleted.
    """
    path = validate_repo_path(repo_path)
    return await run_hg_command(["bookmarks"], cwd=path)  # type: ignore[return-value]


@handle_repo_errors
async def hg_bookmark_create(
    name: str, repo_path: str = ".", revision: str = ""
) -> str:
    """Create a new bookmark.

    Bookmarks are lightweight pointers to revisions (like Git branches).
    Unlike Mercurial branches, bookmarks can be moved and deleted.

    Args:
        name: Name of the bookmark to create
        repo_path: The repository path
        revision: Revision to point the bookmark to (defaults to current parent)
    """
    path = validate_repo_path(repo_path)
    args = ["bookmark", name]

    if revision:
        args.extend(["-r", revision])

    return await run_hg_command(args, cwd=path)


@handle_repo_errors
async def hg_branch(repo_path: str = ".", name: str | None = None) -> str:
    """Show or set the current branch.

    Equivalent to 'git branch'.

    **Note:** Mercurial branches are permanent (unlike Git's lightweight branches).
    For lightweight pointers, use bookmarks instead.
    """
    path = validate_repo_path(repo_path)
    if name:
        return await run_hg_command(["branch", name], cwd=path)
    return await run_hg_command(["branch"], cwd=path)


@json_tool
@handle_repo_errors
async def hg_tags(repo_path: str = ".") -> list[TextContent]:
    """List all tags.

    Shows all tags in the repository with their associated revision numbers
    and changeset IDs.
    """
    path = validate_repo_path(repo_path)
    return await run_hg_command(["tags"], cwd=path)  # type: ignore[return-value]


@handle_repo_errors
async def hg_tag(
    name: str,
    repo_path: str = ".",
    revision: str = "",
    remove: bool = False,
) -> str:
    """Create or remove a tag.

    Equivalent to 'hg tag'. Creates a new tag pointing to a specific revision.

    Args:
        name: The name of the tag to create or remove
        repo_path: The repository path
        revision: The revision to tag (defaults to current working directory parent)
        remove: If True, remove the tag instead of creating it
    """
    path = validate_repo_path(repo_path)
    args = ["tag"]

    if remove:
        args.append("--remove")

    args.extend(["-m", f"Add tag {name}"])
    args.append(name)

    if revision:
        args.extend(["-r", revision])

    return await run_hg_command(args, cwd=path)


@handle_repo_errors
async def hg_topic(name: str, repo_path: str = ".") -> str:
    """Create a new topic.

    Requires the 'topic' extension.
    """
    path = validate_repo_path(repo_path)
    return await run_hg_command(["topic", name], cwd=path)


@json_tool
@handle_repo_errors
async def hg_topics(repo_path: str = ".") -> list[TextContent]:
    """List all topics.

    Requires the 'topic' extension.
    """
    path = validate_repo_path(repo_path)
    return await run_hg_command(["topics"], cwd=path)  # type: ignore[return-value]


@handle_repo_errors
async def hg_topic_current(repo_path: str = ".") -> str:
    """Show the current topic."""
    path = validate_repo_path(repo_path)
    output = await run_hg_command(["topics"], cwd=path)

    if output.startswith("Error"):
        return output

    # Parse JSON output to find active topic
    try:
        topics = json.loads(output)
        for topic in topics:
            if isinstance(topic, dict) and topic.get("active"):
                return str(topic.get("name", "unknown"))
            # Fallback: check for marker in string format
            if isinstance(topic, str) and topic.startswith("*"):
                return topic.lstrip("* ").strip()
    except (json.JSONDecodeError, TypeError):
        # Fallback to text parsing if JSON parsing fails
        for line in output.splitlines():
            if line.strip().startswith("*"):
                parts = line.strip().split(None, 1)
                if len(parts) > 1:
                    return parts[1].strip()
                return parts[0][1:].strip()

    return "No active topic found."
