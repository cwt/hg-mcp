"""Branching and bookmark management tools.

Provides tools for working with bookmarks, topics, branches, and tags.
"""

from mcp.types import TextContent

from hg_mcp.decorators import handle_repo_errors, json_tool
from hg_mcp.helpers import run_hg_command, validate_repo_path
from hg_mcp.server import mcp


@mcp.tool()
@handle_repo_errors
@json_tool
async def hg_bookmarks(repo_path: str = ".") -> list[TextContent]:
    """List all bookmarks.

    Bookmarks are lightweight pointers to revisions (like Git branches).
    Unlike Mercurial branches, bookmarks can be moved and deleted.
    """
    path = validate_repo_path(repo_path)
    return await run_hg_command(["bookmarks"], cwd=path)  # type: ignore[return-value]


@mcp.tool()
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


@mcp.tool()
@handle_repo_errors
@json_tool
async def hg_tags(repo_path: str = ".") -> list[TextContent]:
    """List all tags.

    Shows all tags in the repository with their associated revision numbers
    and changeset IDs.
    """
    path = validate_repo_path(repo_path)
    return await run_hg_command(["tags"], cwd=path)  # type: ignore[return-value]


@mcp.tool()
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


@mcp.tool()
@handle_repo_errors
async def hg_push(
    repo_path: str = ".",
    destination: str = "",
) -> str:
    """Push changes to a remote repository.

    Equivalent to 'git push'. Use hg_paths to see available remotes.
    Note: Mercurial typically uses 'default' instead of Git's 'origin'.
    """
    path = validate_repo_path(repo_path)
    args = ["push"]
    if destination:
        args.append(destination)
    result = await run_hg_command(args, cwd=path)

    # Add helpful hint if destination doesn't exist
    if result.startswith("Error:") and "does not exist" in result:
        paths_output = await run_hg_command(["paths"], cwd=path)
        if not paths_output.startswith("Error:") and paths_output:
            result += f"\n\nAvailable remotes:\n{paths_output}"

    return result


@mcp.tool()
@handle_repo_errors
async def hg_pull(repo_path: str = ".", source: str = "") -> str:
    """Pull changes from a remote repository.

    Equivalent to 'git fetch' + 'git merge'.
    """
    path = validate_repo_path(repo_path)
    args = ["pull"]
    if source:
        args.append(source)
    return await run_hg_command(args, cwd=path)


@mcp.tool()
@handle_repo_errors
@json_tool
async def hg_paths(repo_path: str = ".") -> list[TextContent]:
    """List configured paths/remotes with JSON output."""
    path = validate_repo_path(repo_path)
    return await run_hg_command(["paths"], cwd=path)  # type: ignore[return-value]


@mcp.tool()
@handle_repo_errors
@json_tool
async def hg_config(repo_path: str = ".") -> list[TextContent]:
    """Show Mercurial configuration including enabled extensions."""
    path = validate_repo_path(repo_path)
    return await run_hg_command(["config"], cwd=path)  # type: ignore[return-value]


@mcp.tool()
@handle_repo_errors
async def hg_extensions(repo_path: str = ".") -> str:
    """List enabled Mercurial extensions."""
    path = validate_repo_path(repo_path)
    return await run_hg_command(["config", "extensions"], cwd=path)


@mcp.tool()
@handle_repo_errors
@json_tool
async def hg_topic_current(repo_path: str = ".") -> list[TextContent]:
    """Show the current topic."""

    path = validate_repo_path(repo_path)
    output = await run_hg_command(["topics"], cwd=path)

    if output.startswith("Error"):
        return [TextContent(type="text", text=output)]

    # Parse JSON output to find active topic
    try:
        import json

        topics = json.loads(output)
        for topic in topics:
            if isinstance(topic, dict) and topic.get("active"):
                name = str(topic.get("name", "unknown"))
                return [TextContent(type="text", text=name)]
            # Fallback: check for marker in string format
            if isinstance(topic, str) and topic.startswith("*"):
                text = topic.lstrip("* ").strip()
                return [TextContent(type="text", text=text)]
    except (json.JSONDecodeError, TypeError):
        # Fallback to text parsing if JSON parsing fails
        for line in output.splitlines():
            if line.strip().startswith("*"):
                parts = line.strip().split(None, 1)
                if len(parts) > 1:
                    return [TextContent(type="text", text=parts[1].strip())]
                return [TextContent(type="text", text=parts[0][1:].strip())]

    return [TextContent(type="text", text="No active topic found.")]


@mcp.tool()
@handle_repo_errors
async def hg_topic(name: str, repo_path: str = ".") -> str:
    """Create a new topic.

    Requires the 'topic' extension.
    """
    path = validate_repo_path(repo_path)
    return await run_hg_command(["topic", name], cwd=path)


@mcp.tool()
@handle_repo_errors
@json_tool
async def hg_topics(repo_path: str = ".") -> list[TextContent]:
    """List all topics.

    Requires the 'topic' extension.
    """
    path = validate_repo_path(repo_path)
    return await run_hg_command(["topics"], cwd=path)  # type: ignore[return-value]
