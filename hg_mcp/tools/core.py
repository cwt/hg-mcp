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
    sanitize_input,
    validate_path,
    validate_repo_path,
)
from hg_mcp.server import mcp


@mcp.tool()
@handle_repo_errors
async def hg_init(repo_path: str = ".") -> str:
    """Create a new Mercurial repository in the specified directory.

    Equivalent to 'git init'.
    """
    # Use validate_path instead of validate_repo_path because .hg doesn't exist yet
    path = validate_path(repo_path, create_if_missing=True)
    return await run_hg_command(["init"], cwd=path)


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
        try:
            safe_revisions = sanitize_input(revisions, max_length=200)
        except ValueError as e:
            return f"Error: Invalid revision spec - {e}"
        args.extend(["-r", safe_revisions])
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
    if not result.startswith("Error"):
        # Check if hg-git is enabled
        if await _is_hggit_enabled(path):
            # Check if repo is Git-backed
            is_git_backed, _ = await _check_git_remotes(path)
            if is_git_backed:
                # Run hg gexport to sync Mercurial bookmarks to Git branches
                export_result = await run_hg_command(["gexport"], cwd=path)
                if not export_result.startswith("Error"):
                    result += "\n\n✓ hg-git: Bookmarks exported to Git branches"
                else:
                    result += f"\n\nNote: hg gexport skipped - {export_result}"

    return result


@mcp.tool()
@handle_repo_errors
async def hg_add(
    repo_path: str = ".",
    files: list[str] | str | None = None,
) -> str:
    """Add files to version control.

    Equivalent to 'git add'. Schedules new or modified files for commit.
    If no files specified, adds all untracked files.
    """
    path = validate_repo_path(repo_path)
    files_list = parse_list_param(files) if files else []
    return await run_hg_command(["add"] + files_list, cwd=path)


@mcp.tool()
@handle_repo_errors
async def hg_remove(
    files: list[str] | str,
    repo_path: str = ".",
) -> str:
    """Remove files from version control.

    Equivalent to 'git rm'. Schedules files for removal from the repository.
    """
    path = validate_repo_path(repo_path)
    files_list = parse_list_param(files)
    return await run_hg_command(["remove"] + files_list, cwd=path)


@mcp.tool()
@handle_repo_errors
async def hg_update(
    repo_path: str = ".",
    revision: str = "",
) -> str:
    """Update to a specific revision.

    Equivalent to 'git checkout' or 'git switch'.

    If no revision specified, updates to the tip of the current named branch
    and moves the active bookmark.

    **Important:** Mercurial does NOT use 'HEAD' like Git. Use these instead:
    - `.` (dot) - Current parent revision
    - `tip` - Most recent changeset in the repository
    - `default` - Default branch head
    - Specific revision ID (e.g., "123" or "abc123def")
    - Bookmark name (e.g., "main", "feature-xyz")
    """
    path = validate_repo_path(repo_path)
    if revision:
        return await run_hg_command(["update", "-r", revision], cwd=path)
    return await run_hg_command(["update"], cwd=path)


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


@mcp.tool()
@handle_repo_errors
async def hg_amend(
    message: str | None = None,
    repo_path: str = ".",
) -> str:
    """Amend the current commit.

    Equivalent to modifying the most recent commit. Requires the 'evolve'
    extension for full functionality (automatic phase management).

    **Note:** This updates the current parent commit with any uncommitted
    changes. The original commit is replaced with a new one.

    **hg-git:** After amending in a Git-backed repo, this tool will
    automatically run `hg gexport` to sync bookmarks to Git branches.

    Args:
        message: New commit message (optional, keeps original if not provided)
        repo_path: The repository path

    Examples:
        - hg_amend() -> Amend with original message
        - hg_amend(message="fix typo") -> Amend with new message
    """
    path = validate_repo_path(repo_path)
    args = ["commit", "--amend"]

    if message:
        # Sanitize commit message
        try:
            safe_message = sanitize_input(message, max_length=10000)
        except ValueError as e:
            return f"Error: Invalid commit message - {e}"
        args.extend(["-m", safe_message])
    else:
        args.append("--no-edit")

    result = await run_hg_command(args, cwd=path)

    # If amend succeeded, check if hg-git is enabled and sync bookmarks
    if not result.startswith("Error"):
        try:
            if await _is_hggit_enabled(path):
                is_git_backed, _ = await _check_git_remotes(path)
                if is_git_backed:
                    export_result = await run_hg_command(["gexport"], cwd=path)
                    if not export_result.startswith("Error"):
                        result += (
                            "\n\n✓ hg-git: Bookmarks exported to Git branches"
                        )
                    else:
                        result += (
                            f"\n\nNote: hg gexport skipped - {export_result}"
                        )
        except Exception as e:
            result += f"\n\nNote: hg-git integration check failed: {e}"

    return result


@mcp.tool()
@handle_repo_errors
async def hg_rename(
    src: str,
    dst: str,
    repo_path: str = ".",
) -> str:
    """Rename/move files.

    Equivalent to 'git mv'. Tracks file renames in history.

    Args:
        src: Source file path
        dst: Destination file path
        repo_path: The repository path

    Examples:
        - hg_rename(src="old.txt", dst="new.txt") -> Rename file
    """
    path = validate_repo_path(repo_path)
    # Sanitize file paths
    try:
        safe_src = sanitize_input(src, max_length=500)
        safe_dst = sanitize_input(dst, max_length=500)
    except ValueError as e:
        return f"Error: Invalid file path - {e}"
    return await run_hg_command(["rename", safe_src, safe_dst], cwd=path)


@mcp.tool()
@handle_repo_errors
async def hg_cat(
    file: str,
    repo_path: str = ".",
    revision: str = "",
) -> str:
    """Show file content at a specific revision.

    Equivalent to 'git show' or 'hg cat'. Displays the contents of a file
    as it existed at the specified revision.

    Args:
        file: Path to the file to display
        repo_path: The repository path
        revision: Revision to show (defaults to working directory parent)

    Examples:
        - hg_cat(file="README.md") -> Show file at current parent
        - hg_cat(file="README.md", revision="v1.0") -> Show file at tag v1.0
    """
    path = validate_repo_path(repo_path)
    args = ["cat"]

    if revision:
        # Sanitize revision string
        try:
            safe_revision = sanitize_input(revision, max_length=200)
        except ValueError as e:
            return f"Error: Invalid revision - {e}"
        args.extend(["-r", safe_revision])

    # Sanitize file path
    try:
        safe_file = sanitize_input(file, max_length=500)
    except ValueError as e:
        return f"Error: Invalid file path - {e}"
    args.append(safe_file)

    return await run_hg_command(args, cwd=path)
