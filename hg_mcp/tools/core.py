"""Core Mercurial tools.

Provides essential workflow tools for the MCP server.
"""

from mcp.types import TextContent

from hg_mcp.decorators import handle_repo_errors, json_tool
from hg_mcp.helpers import (
    MAX_LOG_LIMIT,
    _check_git_remotes,
    _is_hggit_enabled,
    parse_list_param,
    run_hg_command,
    validate_repo_path,
)
from hg_mcp.server import mcp


@mcp.tool()
@handle_repo_errors
@json_tool
async def hg_status(repo_path: str = ".") -> list[TextContent]:
    """Show the status of files in the working directory.

    Equivalent to 'git status'. Shows modified, added, removed files.
    Returns a clear message even when there are no changes.
    """
    path = validate_repo_path(repo_path)
    return await run_hg_command(["status"], cwd=path)  # type: ignore[return-value]


@mcp.tool()
@handle_repo_errors
@json_tool
async def hg_log(repo_path: str = ".", limit: int = 10) -> list[TextContent]:
    """Show commit history.

    Equivalent to 'git log'. Displays revisions with changeset ID, author,
    date, and message.
    """
    from mcp.types import Annotations as AnnotationsType

    if limit < 1:
        return [
            TextContent(
                type="text",
                text="Error: limit must be at least 1",
                annotations=AnnotationsType(audience=["user"], priority=1.0),
            )
        ]
    if limit > MAX_LOG_LIMIT:
        return [
            TextContent(
                type="text",
                text=f"Error: limit exceeds maximum allowed value of {MAX_LOG_LIMIT}",
                annotations=AnnotationsType(audience=["user"], priority=1.0),
            )
        ]

    path = validate_repo_path(repo_path)
    return await run_hg_command(["log", "--limit", str(limit)], cwd=path)  # type: ignore[return-value]


@mcp.tool()
@handle_repo_errors
async def hg_diff(repo_path: str = ".", revisions: str = "") -> str:
    """Show changes in the working directory or between revisions.

    Equivalent to 'git diff'. Shows line-by-line changes to tracked files.

    Args:
        repo_path: The repository path
        revisions: Revision spec (e.g., 'v1.0.0..tip', 'tip~3 tip', '0..2', '500..510')

    Examples:
        - hg_diff() -> diff of working directory
        - hg_diff(revisions="500..510") -> diff from 500 to 510
        - hg_diff(revisions="v1.0.0..tip") -> diff from tag v1.0.0 to tip
    """
    path = validate_repo_path(repo_path)
    args = ["diff"]
    if revisions:
        args.extend(["-r", revisions])
    return await run_hg_command(args, cwd=path)


@mcp.tool()
@handle_repo_errors
async def hg_commit(
    message: str,
    repo_path: str = ".",
    files: list[str] | str | None = None,
) -> str:
    """Commit changes with a message.

    Equivalent to 'git commit'. Records changes in the repository with a
    description.

    **Note:** Mercurial has no staging area; all modified files are committed.
    To select specific files, pass them in the `files` parameter.

    **hg-git:** After committing in a Git-backed repo, this tool will
    automatically check if bookmark synchronization is needed and run
    `hg gexport` if hg-git is enabled.
    """
    path = validate_repo_path(repo_path)
    args = ["commit", "-m", message]
    files_list = parse_list_param(files)
    if files_list:
        args.extend(files_list)

    result = await run_hg_command(args, cwd=path)

    # If commit succeeded, check if hg-git is enabled and sync bookmarks
    if not result.startswith("Error:"):
        # Check if hg-git is enabled
        if await _is_hggit_enabled(path):
            # Check if repo is Git-backed
            is_git_backed, _ = await _check_git_remotes(path)
            if is_git_backed:
                # Run hg gexport to sync Mercurial bookmarks to Git branches
                export_result = await run_hg_command(["gexport"], cwd=path)
                if not export_result.startswith("Error:"):
                    result += "\n\n✓ hg-git: Bookmarks exported to Git branches"
                else:
                    result += f"\n\nNote: hg gexport skipped - {export_result}"

    return result


@mcp.tool()
@handle_repo_errors
async def hg_add(files: list[str] | str, repo_path: str = ".") -> str:
    """Add files to version control.

    Equivalent to 'git add'. Schedules new or modified files for commit.
    """
    path = validate_repo_path(repo_path)
    files_list = parse_list_param(files)
    return await run_hg_command(["add"] + files_list, cwd=path)


@mcp.tool()
@handle_repo_errors
async def hg_remove(files: list[str] | str, repo_path: str = ".") -> str:
    """Remove files from version control.

    Equivalent to 'git rm'. Schedules files for removal from the repository.
    """
    path = validate_repo_path(repo_path)
    files_list = parse_list_param(files)
    return await run_hg_command(["remove"] + files_list, cwd=path)


@mcp.tool()
@handle_repo_errors
async def hg_update(revision: str, repo_path: str = ".") -> str:
    """Update to a specific revision.

    Equivalent to 'git checkout' or 'git switch'.

    **Important:** Mercurial does NOT use 'HEAD' like Git. Use these instead:
    - `.` (dot) - Current parent revision
    - `tip` - Most recent changeset in the repository
    - `default` - Default branch head
    - Specific revision ID (e.g., "123" or "abc123def")
    - Bookmark name (e.g., "main", "feature-xyz")
    """
    path = validate_repo_path(repo_path)
    return await run_hg_command(["update", revision], cwd=path)


@mcp.tool()
@handle_repo_errors
async def hg_revert(
    repo_path: str = ".",
    files: list[str] | str | None = None,
) -> str:
    """Revert uncommitted changes.

    Equivalent to 'git checkout -- <files>' or 'git restore <files>'.
    """
    path = validate_repo_path(repo_path)
    args = ["revert"]
    files_list = parse_list_param(files)
    if files_list:
        args.extend(files_list)
    else:
        args.append("--all")
    return await run_hg_command(args, cwd=path)
