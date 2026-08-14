"""hg-git extension tools.

Provides tools for working with hg-git extension for Git-backed repositories.
"""

from mcp.types import TextContent

from hg_mcp.decorators import handle_repo_errors, json_tool
from hg_mcp.helpers import (
    _check_git_remotes,
    _get_git_branches,
    _is_hggit_enabled,
    parse_list_param,
    run_hg_command,
    sanitize_input,
    validate_repo_path,
)
from hg_mcp.server import mcp


@mcp.tool()
@handle_repo_errors
async def hg_git(repo_path: str = ".") -> str:
    """Check hg-git extension status and whether this repo is Git-backed."""
    path = validate_repo_path(repo_path)

    # 1. Check Extension
    if not await _is_hggit_enabled(path):
        return (
            "hg-git extension is NOT enabled.\n\n"
            "To enable hg-git, add to your ~/.hgrc or .hg/hgrc:\n"
            "[extensions]\n"
            "hggit =\n"
        )

    # 2. Check Git Backing & Remotes
    is_git_backed, git_paths = await _check_git_remotes(path)

    # 3. Get Git Config (returns JSON)
    config_out = await run_hg_command(["config", "git"], cwd=path)
    suffix = None  # No default - hg-git doesn't set a default suffix
    if not config_out.startswith("Error"):
        try:
            import json

            config_items = json.loads(config_out)
            for item in config_items:
                if item.get("name") == "git.branch_bookmark_suffix":
                    suffix = item.get("value")
                    break
        except (json.JSONDecodeError, TypeError):
            pass

    # 4. Get Bookmarks
    git_branches, local_bookmarks = await _get_git_branches(path, suffix)

    # Build Output
    lines = ["hg-git extension is ENABLED ✓\n"]

    if is_git_backed:
        lines.append("✓ This repository IS Git-backed\n")
        if git_paths:
            lines.append("Git remotes:")
            lines.extend(git_paths)
            lines.append("")
    else:
        lines.append("✗ This repository is NOT Git-backed\n")

    lines.append("=" * 50)
    lines.append("Git Branch Mapping (branch_bookmark_suffix)")
    lines.append("=" * 50)
    if suffix is not None:
        lines.append(f"\nCurrent suffix: '{suffix}'\n")
    else:
        lines.append(
            "\nNo branch_bookmark_suffix configured "
            "(bookmarks map directly to Git branches)\n"
        )

    if git_branches:
        lines.append("Git-tracked bookmarks:")
        lines.extend(git_branches)
    else:
        lines.append("No Git-tracked bookmarks found.")

    if local_bookmarks:
        lines.append("\nLocal bookmarks:")
        lines.extend(local_bookmarks)

    return "\n".join(lines)


@mcp.tool()
@handle_repo_errors
async def hg_rebase(
    repo_path: str = ".",
    source: str = "",
    dest: str = "",
    collapse: bool = False,
    keep: bool = False,
) -> str:
    """Rebase changes using the rebase extension.

    Equivalent to 'git rebase'.

    **Note:** Mercurial rebase rewrites draft changesets only.
    Use `--collapse` to fold multiple changesets into one.
    """
    path = validate_repo_path(repo_path)
    args = ["rebase"]
    if source:
        try:
            safe_source = sanitize_input(source, max_length=200)
        except ValueError as e:
            return f"Error: Invalid source - {e}"
        args.extend(["-s", safe_source])
    if dest:
        try:
            safe_dest = sanitize_input(dest, max_length=200)
        except ValueError as e:
            return f"Error: Invalid destination - {e}"
        args.extend(["-d", safe_dest])
    if collapse:
        args.append("--collapse")
    if keep:
        args.append("--keep")
    return await run_hg_command(args, cwd=path)


@mcp.tool()
@handle_repo_errors
async def hg_strip(
    revision: str,
    repo_path: str = ".",
    keep: bool = False,
) -> str:
    """Remove a changeset using the strip extension.

    Similar to 'git reset --hard' but removes specific changesets.

    **Warning:** Permanently deletes changesets. Use with caution on public history.
    """
    path = validate_repo_path(repo_path)

    # Sanitize revision
    try:
        safe_revision = sanitize_input(revision, max_length=200)
    except ValueError as e:
        return f"Error: Invalid revision - {e}"

    args = ["strip"]
    if keep:
        args.append("--keep")
    args.append(safe_revision)
    return await run_hg_command(args, cwd=path)


@mcp.tool()
@handle_repo_errors
async def hg_transplant(
    revisions: list[str] | str,
    repo_path: str = ".",
    source: str = "",
) -> str:
    """Cherry-pick changesets using the transplant extension.

    Use --source/-s to specify another repository to transplant from.
    """
    path = validate_repo_path(repo_path)
    args = ["transplant"]
    if source:
        try:
            safe_source = sanitize_input(source, max_length=500)
        except ValueError as e:
            return f"Error: Invalid source - {e}"
        args.extend(["--source", safe_source])
    revisions_list = parse_list_param(revisions)
    if not revisions_list:
        return "Error: revisions are required (e.g., ['abc123', 'def456']). Interactive mode is not supported."
    for rev in revisions_list:
        try:
            safe_rev = sanitize_input(rev, max_length=200)
        except ValueError as e:
            return f"Error: Invalid revision - {e}"
        args.extend(["-r", safe_rev])
    return await run_hg_command(args, cwd=path)


@mcp.tool()
@handle_repo_errors
async def hg_evolve(repo_path: str = ".") -> str:
    """Show evolution history using the evolve extension."""
    path = validate_repo_path(repo_path)
    return await run_hg_command(["evolve"], cwd=path)


@mcp.tool()
@handle_repo_errors
async def hg_absorb(repo_path: str = ".") -> str:
    """Auto-amend uncommitted changes into prior commits.

    Requires the 'evolve' extension. Automatically finds the correct
    commit to amend each uncommitted change into its logical parent.

    This is similar to 'git absorb' and is useful for cleaning up
    changes after they've been made without remembering to amend.

    Use `hg_absorb` daily to keep commits logically organized.
    """
    path = validate_repo_path(repo_path)
    return await run_hg_command(["absorb"], cwd=path)


@mcp.tool()
@handle_repo_errors
async def hg_fold(
    revisions: list[str] | str,
    repo_path: str = ".",
    message: str = "",
    exact: bool = False,
) -> str:
    """Combine multiple changesets into one.

    Requires the 'evolve' extension. Folds the specified revisions
    on top of the current working directory parent. The folded result
    is a single commit with the combined changes.

    Args:
        revisions: Revisions to fold together (required)
        repo_path: The repository path
        message: Commit message for the folded result
        exact: Fold exactly these revisions (don't include intermediate)

    Examples:
        - hg_fold(revisions=["abc123", "def456"]) -> Fold two changesets
    """
    path = validate_repo_path(repo_path)
    args = ["fold"]

    if exact:
        args.append("--exact")

    if message:
        try:
            safe_message = sanitize_input(message, max_length=10000)
        except ValueError as e:
            return f"Error: Invalid commit message - {e}"
        args.extend(["-m", safe_message])

    revisions_list = parse_list_param(revisions)
    if not revisions_list:
        return "Error: revisions are required for fold."

    for rev in revisions_list:
        try:
            safe_rev = sanitize_input(rev, max_length=200)
        except ValueError as e:
            return f"Error: Invalid revision - {e}"
        args.extend(["-r", safe_rev])

    return await run_hg_command(args, cwd=path)


@mcp.tool()
@handle_repo_errors
async def hg_split(
    revision: str = "",
    repo_path: str = ".",
) -> str:
    """Split a changeset into multiple smaller ones.

    Requires the 'evolve' extension. Opens an interactive session
    (via the configured editor) to split the specified revision.
    Without a revision, splits the current working directory parent.

    Args:
        revision: Revision to split (defaults to current parent)
        repo_path: The repository path

    Examples:
        - hg_split() -> Split current changeset
        - hg_split(revision="abc123") -> Split specific changeset
    """
    path = validate_repo_path(repo_path)
    args = ["split"]

    if revision:
        try:
            safe_revision = sanitize_input(revision, max_length=200)
        except ValueError as e:
            return f"Error: Invalid revision - {e}"
        args.extend(["-r", safe_revision])

    return await run_hg_command(args, cwd=path)


@mcp.tool()
@handle_repo_errors
async def hg_uncommit(
    repo_path: str = ".",
    revisions: list[str] | str | None = None,
    keep: bool = False,
) -> str:
    """Uncommit part of a changeset (move to working directory).

    Requires the 'evolve' extension. Moves changes from the specified
    changesets into the working directory, effectively "un-committing"
    them. This is the opposite of commit/amend.

    Args:
        repo_path: The repository path
        revisions: Revision(s) to uncommit; use "." for all changes
        keep: Keep the changeset as an empty commit after uncommitting

    Examples:
        - hg_uncommit() -> Uncommit current changeset
        - hg_uncommit(revisions="abc123") -> Uncommit specific changeset
        - hg_uncommit(revisions=".") -> Uncommit all pending changes
        - hg_uncommit(keep=True) -> Keep empty commit skeleton
    """
    path = validate_repo_path(repo_path)
    args = ["uncommit"]

    if keep:
        args.append("--keep")

    revisions_list = parse_list_param(revisions)
    if revisions_list:
        for rev in revisions_list:
            try:
                safe_rev = sanitize_input(rev, max_length=200)
            except ValueError as e:
                return f"Error: Invalid revision - {e}"
            args.extend(["-r", safe_rev])

    return await run_hg_command(args, cwd=path)


@mcp.tool()
@handle_repo_errors
async def hg_next(repo_path: str = ".") -> str:
    """Move to the next changeset in the topic stack.

    Requires the 'evolve' (topic) extension. Navigates forward through
    changesets in the current topic stack. Works with --evolve to move
    forward while resolving instability.

    Use `hg_stack` to see the current topic stack.
    """
    path = validate_repo_path(repo_path)
    return await run_hg_command(["next"], cwd=path)


@mcp.tool()
@handle_repo_errors
async def hg_previous(repo_path: str = ".") -> str:
    """Move to the previous changeset in the topic stack.

    Requires the 'evolve' (topic) extension. Navigates backward through
    changesets in the current topic stack.

    Use `hg_stack` to see the current topic stack.
    """
    path = validate_repo_path(repo_path)
    return await run_hg_command(["previous"], cwd=path)


@mcp.tool()
@handle_repo_errors
async def hg_rewind(
    revisions: list[str] | str,
    repo_path: str = ".",
    keep: bool = False,
) -> str:
    """Recreate changesets that were pruned, stripped, or evolved away.

    Requires the 'evolve' extension. Rewinds history to bring back
    changesets that have been obsoleted. This is the undo command for
    prune, strip, amend, and evolve operations.

    Args:
        revisions: Revision(s) to rewind back from (required)
        repo_path: The repository path
        keep: Keep the original pruned changesets as obsolete

    Examples:
        - hg_rewind(revisions="abc123") -> Bring back pruned changeset
        - hg_rewind(revisions="abc123", keep=True) -> Keep original too
    """
    path = validate_repo_path(repo_path)
    args = ["rewind"]

    if keep:
        args.append("--keep")

    revisions_list = parse_list_param(revisions)
    if not revisions_list:
        return "Error: revisions are required for rewind."

    for rev in revisions_list:
        try:
            safe_rev = sanitize_input(rev, max_length=200)
        except ValueError as e:
            return f"Error: Invalid revision - {e}"
        args.extend(["-r", safe_rev])

    return await run_hg_command(args, cwd=path)


@mcp.tool()
@handle_repo_errors
async def hg_metaedit(
    repo_path: str = ".",
    revision: str = "",
    message: str = "",
    user: str = "",
    date: str = "",
    fold: bool = False,
) -> str:
    """Edit commit metadata (message, user, date, branch).

    Requires the 'evolve' extension. Modifies metadata of a changeset
    without changing its content. This creates a new changeset that
    replaces the original.

    Args:
        repo_path: The repository path
        revision: Revision to edit (defaults to current parent)
        message: New commit message
        user: New author (e.g., "Name <email@example.com>")
        date: New date (ISO 8601 format)
        fold: Combine with parent (fold into previous changeset)

    Examples:
        - hg_metaedit(message="Better commit message") -> Edit message
        - hg_metaedit(user="Name <email@example.com>") -> Change author
        - hg_metaedit(date="2024-01-15 10:30:00") -> Change date
    """
    path = validate_repo_path(repo_path)
    args = ["metaedit"]

    if revision:
        try:
            safe_revision = sanitize_input(revision, max_length=200)
        except ValueError as e:
            return f"Error: Invalid revision - {e}"
        args.extend(["-r", safe_revision])

    if message:
        try:
            safe_message = sanitize_input(message, max_length=10000)
        except ValueError as e:
            return f"Error: Invalid commit message - {e}"
        args.extend(["-m", safe_message])

    if user:
        try:
            safe_user = sanitize_input(user, max_length=500)
        except ValueError as e:
            return f"Error: Invalid user - {e}"
        args.extend(["-u", safe_user])

    if date:
        try:
            safe_date = sanitize_input(date, max_length=200)
        except ValueError as e:
            return f"Error: Invalid date - {e}"
        args.extend(["-d", safe_date])

    if fold:
        args.append("--fold")

    return await run_hg_command(args, cwd=path)


@mcp.tool()
@handle_repo_errors
@json_tool
async def hg_stack(repo_path: str = ".") -> list[TextContent]:
    """Show the current topic stack.

    Requires the 'evolve' (topic) extension. Displays all changesets
    in the current active topic with their status and relations.

    Use `hg_next`/`hg_previous` to navigate the stack, and
    `hg_absorb` or `hg_fold` to reorganize it.
    """
    path = validate_repo_path(repo_path)
    return await run_hg_command(["stack"], cwd=path)  # type: ignore[return-value]


@mcp.tool()
@handle_repo_errors
async def hg_prune(
    revisions: list[str] | str,
    repo_path: str = ".",
) -> str:
    """Mark changesets as obsolete (history cleanup).

    Requires the 'evolve' extension. Prunes revisions, marking them
    as obsolete. Unlike strip, prune doesn't actually delete anything
    immediately; the changesets remain until garbage collection.

    Pruned changesets can be recovered with `hg_rewind`.

    Args:
        revisions: Revision(s) to prune (required)
        repo_path: The repository path

    Examples:
        - hg_prune(revisions="abc123") -> Prune a changeset
        - hg_prune(revisions=["abc123", "def456"]) -> Prune multiple
    """
    path = validate_repo_path(repo_path)
    args = ["prune"]

    revisions_list = parse_list_param(revisions)
    if not revisions_list:
        return "Error: revisions are required for prune."

    for rev in revisions_list:
        try:
            safe_rev = sanitize_input(rev, max_length=200)
        except ValueError as e:
            return f"Error: Invalid revision - {e}"
        args.extend(["-r", safe_rev])

    return await run_hg_command(args, cwd=path)
