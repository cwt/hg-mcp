"""Branching and bookmark management tools.

Provides tools for working with bookmarks, topics, branches, and tags.
"""

from mcp.types import TextContent, ToolAnnotations

from hg_mcp.decorators import handle_repo_errors, json_tool
from hg_mcp.helpers import (
    run_hg_command,
    sanitize_input,
    sync_git_bookmarks,
    validate_repo_path,
)
from hg_mcp.server import mcp


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
@handle_repo_errors
@json_tool
async def hg_bookmarks(repo_path: str = ".") -> list[TextContent]:
    """List all bookmarks.

    Bookmarks are lightweight pointers to revisions (like Git branches).
    Unlike Mercurial branches, bookmarks can be moved and deleted.
    """
    try:
        path = validate_repo_path(repo_path)
        return await run_hg_command(["bookmarks"], cwd=path)  # type: ignore[return-value]
    except Exception as e:
        return f"Error: {e}"  # type: ignore[return-value]


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
@handle_repo_errors
async def hg_bookmark(
    repo_path: str = ".",
    name: str | None = None,
    revision: str = "",
) -> str:
    """Show or create a bookmark.

    Bookmarks are lightweight pointers to revisions (like Git branches).
    Unlike Mercurial branches, bookmarks can be moved and deleted.

    **hg-git:** After creating a bookmark in a Git-backed repo, this tool will
    automatically run `hg gexport` to sync bookmarks to Git branches.

    Args:
        repo_path: The repository path
        name: Name of bookmark to create (optional, shows current if omitted)
        revision: Revision to point bookmark to (defaults to current parent)

    Examples:
        - hg_bookmark() -> Show current bookmark
        - hg_bookmark(name="feature") -> Create bookmark "feature"
        - hg_bookmark(name="feature", revision="tip") -> Create at tip
    """
    try:
        path = validate_repo_path(repo_path)

        if name:
            try:
                safe_name = sanitize_input(name, max_length=200)
            except ValueError as e:
                return f"Error: Invalid bookmark name - {e}"

            args = ["bookmark", safe_name]

            if revision:
                try:
                    safe_revision = sanitize_input(revision, max_length=200)
                except ValueError as e:
                    return f"Error: Invalid revision - {e}"
                args.extend(["-r", safe_revision])

            result = await run_hg_command(args, cwd=path)

            if not result.startswith("Error"):
                result += await sync_git_bookmarks(path)

            return result

        return await run_hg_command(["bookmark"], cwd=path)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
@handle_repo_errors
async def hg_branch(repo_path: str = ".", name: str | None = None) -> str:
    """Show or set the current branch.

    Equivalent to 'git branch'.

    **Note:** Mercurial branches are permanent (unlike Git's lightweight branches).
    For lightweight pointers, use bookmarks instead.
    """
    try:
        path = validate_repo_path(repo_path)
        if name:
            try:
                safe_name = sanitize_input(name, max_length=200)
            except ValueError as e:
                return f"Error: Invalid branch name - {e}"
            return await run_hg_command(["branch", safe_name], cwd=path)
        return await run_hg_command(["branch"], cwd=path)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
@handle_repo_errors
@json_tool
async def hg_tags(repo_path: str = ".") -> list[TextContent]:
    """List all tags.

    Shows all tags in the repository with their associated revision numbers
    and changeset IDs.
    """
    try:
        path = validate_repo_path(repo_path)
        return await run_hg_command(["tags"], cwd=path)  # type: ignore[return-value]
    except Exception as e:
        return f"Error: {e}"  # type: ignore[return-value]


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=False,
    )
)
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
    try:
        path = validate_repo_path(repo_path)

        try:
            safe_name = sanitize_input(name, max_length=200)
        except ValueError as e:
            return f"Error: Invalid tag name - {e}"

        args = ["tag"]

        if remove:
            args.append("--remove")
            args.extend(["-m", f"Remove tag {safe_name}"])
        else:
            args.extend(["-m", f"Add tag {safe_name}"])
        args.append(safe_name)

        if revision:
            try:
                safe_revision = sanitize_input(revision, max_length=200)
            except ValueError as e:
                return f"Error: Invalid revision - {e}"
            args.extend(["-r", safe_revision])

        return await run_hg_command(args, cwd=path)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
@handle_repo_errors
async def hg_push(
    repo_path: str = ".",
    destination: str = "",
) -> str:
    """Push changes to a remote repository.

    Equivalent to 'git push'. Use hg_paths to see available remotes.
    Note: Mercurial typically uses 'default' instead of Git's 'origin'.
    """
    try:
        path = validate_repo_path(repo_path)
        args = ["push"]
        if destination:
            args.append(destination)
        result = await run_hg_command(args, cwd=path)

        # Add helpful hint if destination doesn't exist
        if result.startswith("Error") and "does not exist" in result:
            paths_output = await run_hg_command(["paths"], cwd=path)
            if not paths_output.startswith("Error") and paths_output:
                result += f"\n\nAvailable remotes:\n{paths_output}"

        return result
    except Exception as e:
        return f"Error: {e}"


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
@handle_repo_errors
async def hg_pull(repo_path: str = ".", source: str = "") -> str:
    """Pull changes from a remote repository.

    Equivalent to 'git fetch' + 'git merge'.
    """
    try:
        path = validate_repo_path(repo_path)
        args = ["pull"]
        if source:
            args.append(source)
        return await run_hg_command(args, cwd=path)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
@handle_repo_errors
@json_tool
async def hg_paths(repo_path: str = ".") -> list[TextContent]:
    """List configured paths/remotes with JSON output."""
    try:
        path = validate_repo_path(repo_path)
        return await run_hg_command(["paths"], cwd=path)  # type: ignore[return-value]
    except Exception as e:
        return f"Error: {e}"  # type: ignore[return-value]


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
@handle_repo_errors
@json_tool
async def hg_config(repo_path: str = ".") -> list[TextContent]:
    """Show Mercurial configuration including enabled extensions."""
    try:
        path = validate_repo_path(repo_path)
        return await run_hg_command(["config"], cwd=path)  # type: ignore[return-value]
    except Exception as e:
        return f"Error: {e}"  # type: ignore[return-value]


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
@handle_repo_errors
async def hg_extensions(repo_path: str = ".") -> str:
    """List enabled Mercurial extensions."""
    try:
        path = validate_repo_path(repo_path)
        return await run_hg_command(["config", "extensions"], cwd=path)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
@handle_repo_errors
@json_tool
async def hg_topic_current(repo_path: str = ".") -> list[TextContent]:
    """Show the current topic."""
    try:
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
                if isinstance(topic, str) and topic.startswith("*"):
                    text = topic.lstrip("* ").strip()
                    return [TextContent(type="text", text=text)]
        except (json.JSONDecodeError, TypeError):
            for line in output.splitlines():
                if line.strip().startswith("*"):
                    parts = line.strip().split(None, 1)
                    if len(parts) > 1:
                        return [TextContent(type="text", text=parts[1].strip())]
                    return [TextContent(type="text", text=parts[0][1:].strip())]

        return [TextContent(type="text", text="No active topic found.")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {e}")]


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
@handle_repo_errors
async def hg_topic(name: str, repo_path: str = ".") -> str:
    """Create a new topic.

    Requires the 'topic' extension.
    """
    try:
        path = validate_repo_path(repo_path)
        return await run_hg_command(["topic", name], cwd=path)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
@handle_repo_errors
@json_tool
async def hg_topics(repo_path: str = ".") -> list[TextContent]:
    """List all topics.

    Requires the 'topic' extension.
    """
    try:
        path = validate_repo_path(repo_path)
        return await run_hg_command(["topics"], cwd=path)  # type: ignore[return-value]
    except Exception as e:
        return f"Error: {e}"  # type: ignore[return-value]


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
@handle_repo_errors
@json_tool
async def hg_phases(
    repo_path: str = ".",
    revision: str = "",
    public: bool = False,
    draft: bool = False,
    secret: bool = False,
    force: bool = False,
) -> list[TextContent]:
    """Show or set changeset phases.

    Mercurial phases control which changesets are safe to rewrite:
    - **public**: Immutable, pushed to a publishing server
    - **draft**: Mutable, not yet pushed to a publishing server
    - **secret**: Not shared, never pushed

    Without any flags, shows phases of all visible changesets.
    Use --draft/--secret to demote phases (requires --force for public).

    Args:
        repo_path: The repository path
        revision: Revision(s) to query or modify (defaults to all)
        public: Set phase to public
        draft: Set phase to draft
        secret: Set phase to secret
        force: Force phase change (required for demoting public changesets)

    Examples:
        - hg_phases() -> Show phases of all changesets
        - hg_phases(revision="tip") -> Show phase of tip
        - hg_phases(revision="abc123", secret=True) -> Make a changeset secret
    """
    try:
        path = validate_repo_path(repo_path)
        args = ["phase"]

        if public:
            args.append("--public")
        elif draft:
            args.append("--draft")
        elif secret:
            args.append("--secret")

        if force:
            args.append("--force")

        if revision:
            try:
                safe_revision = sanitize_input(revision, max_length=200)
            except ValueError as e:
                return [TextContent(type="text", text=f"Error: Invalid revision - {e}")]
            args.extend(["-r", safe_revision])

        return await run_hg_command(args, cwd=path)  # type: ignore[return-value]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {e}")]
