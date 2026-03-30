"""History manipulation tools for hg-mcp server."""

import tempfile
from pathlib import Path

from mcp.types import TextContent

from hg_mcp.decorators import handle_repo_errors, json_tool
from hg_mcp.helpers import parse_list_param, run_hg_command, validate_repo_path


@json_tool
@handle_repo_errors
async def hg_annotate(
    repo_path: str = ".",
    revision: str = "",
    files: list[str] | str | None = None,
) -> list[TextContent]:
    """Show changeset information by line for each file.

    Equivalent to 'git blame'. Displays which changeset and user last modified
    each line in the specified files.
    """
    path = validate_repo_path(repo_path)
    args = ["annotate"]
    if revision:
        args.extend(["-r", revision])
    files_list = parse_list_param(files)
    if files_list:
        args.extend(files_list)
    return await run_hg_command(args, cwd=path)  # type: ignore[return-value]


@handle_repo_errors
async def hg_backout(
    revision: str,
    repo_path: str = ".",
    merge: bool = False,
    message: str = "",
) -> str:
    """Reverse effect of earlier changeset.

    Creates a new changeset that undoes the changes from the specified revision.

    **Note:** After backout, you need to commit the changes manually unless
    `merge=True` is specified, which will attempt an automatic merge.

    Args:
        revision: The revision to backout
        repo_path: The repository path
        merge: If True, automatically merge the result (creates commit)
        message: Commit message (required if merge=True, ignored otherwise)
    """
    path = validate_repo_path(repo_path)
    args = ["backout"]
    if merge:
        args.append("--merge")
        if message:
            args.extend(["-m", message])
        else:
            # Default message to avoid interactive editor
            args.extend(["-m", f"Backed out changeset {revision}"])
    else:
        # Don't commit, just prepare the backout
        args.append("--no-commit")
    args.append(revision)
    return await run_hg_command(args, cwd=path)


@handle_repo_errors
async def hg_evolve(repo_path: str = ".") -> str:
    """Show evolution history using the evolve extension."""
    path = validate_repo_path(repo_path)
    return await run_hg_command(["evolve"], cwd=path)


@handle_repo_errors
async def hg_export(
    repo_path: str = ".",
    revisions: list[str] | str | None = None,
    output: str = "",
) -> str:
    """Dump the header and diffs for one or more changesets.

    Exports changesets as patch files. If no revisions specified, exports
    all unpushed changes.

    Args:
        repo_path: The repository path
        revisions: List of revision IDs to export (defaults to all unpushed)
        output: Output file path pattern (e.g., "patch-%r.patch")
    """
    path = validate_repo_path(repo_path)
    args = ["export"]
    if output:
        args.extend(["-o", output])
    revisions_list = parse_list_param(revisions)
    for rev in revisions_list:
        args.append(rev)
    return await run_hg_command(args, cwd=path)


@json_tool
@handle_repo_errors
async def hg_heads(
    repo_path: str = ".",
    branch: str = "",
    active: bool = False,
) -> list[TextContent]:
    """Show branch heads.

    Returns the head changesets of branches. A head is a changeset with no
    children on the same branch.

    Args:
        repo_path: The repository path
        branch: Filter to specific branch name
        active: If True, only show the active head of each branch
    """
    path = validate_repo_path(repo_path)
    args = ["heads"]
    if branch:
        args.append(branch)
    if active:
        args.append("--active")
    return await run_hg_command(args, cwd=path)  # type: ignore[return-value]


@handle_repo_errors
async def hg_histedit(
    repo_path: str = ".",
    revision: str = "",
    commands: str = "",
) -> str:
    """Edit history using histedit extension (non-interactive mode).

    This command lets you edit a linear series of changesets non-interactively
    by providing a commands file.

    Commands (one per line):
    - 'pick' - reorder or keep changeset
    - 'drop' - omit changeset
    - 'mess' - reword commit message
    - 'fold' - combine with preceding changeset
    - 'roll' - like fold, but discard this commit's description
    - 'edit' - pause at this changeset for manual edits
    - 'base' - checkout changeset and apply further changesets from there

    Args:
        repo_path: The repository path
        revision: First revision to be edited (ancestor)
        commands: Commands file path or inline commands
            (e.g., "pick abc123\\ndrop def456")

    Example:
        # Fold two commits together:
        hg_histedit(revision="tip~2", commands="fold abc123\\npick def456")
    """
    path = validate_repo_path(repo_path)
    args = ["histedit"]

    # Track temp file for cleanup
    commands_file_exists = False
    commands_file = ""

    if revision:
        args.extend(["-r", revision])

    # Support inline commands by creating a temp file
    if commands:
        # Check if commands is a file path or inline commands
        starts_with_cmd = commands.strip().startswith(
            ("pick", "drop", "fold", "roll", "edit", "mess", "base")
        )
        if "\n" in commands or starts_with_cmd:
            # Inline commands - create temp file
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".histedit", delete=False
            ) as f:
                f.write(commands)
                commands_file = f.name
                commands_file_exists = True
            args.extend(["--commands", commands_file])
        else:
            # File path
            args.extend(["--commands", commands])

    result = await run_hg_command(args, cwd=path)

    # Clean up temp file
    if commands_file_exists:
        try:
            Path(commands_file).unlink()
        except Exception:
            pass

    return result


@handle_repo_errors
async def hg_import(
    repo_path: str = ".",
    patches: list[str] | str | None = None,
    no_commit: bool = False,
) -> str:
    """Import an ordered set of patches.

    Applies patch files to the working directory. Can optionally commit
    automatically if the patch includes proper header information.

    Args:
        repo_path: The repository path
        patches: List of patch file paths to import
        no_commit: If True, only apply patches without committing
    """
    path = validate_repo_path(repo_path)
    args = ["import"]
    if no_commit:
        args.append("--no-commit")
    patches_list = parse_list_param(patches)
    if patches_list:
        args.extend(patches_list)
    return await run_hg_command(args, cwd=path)


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
        args.extend(["-s", source])
    if dest:
        args.extend(["-d", dest])
    if collapse:
        args.append("--collapse")
    if keep:
        args.append("--keep")
    return await run_hg_command(args, cwd=path)


@handle_repo_errors
async def hg_strip(
    revision: str, repo_path: str = ".", keep: bool = False
) -> str:
    """Remove a changeset using the strip extension.

    Similar to 'git reset --hard' but removes specific changesets.

    **Warning:** Permanently deletes changesets. Use with caution on public history.
    """
    path = validate_repo_path(repo_path)
    args = ["strip"]
    if keep:
        args.append("--keep")
    args.append(revision)
    return await run_hg_command(args, cwd=path)


@handle_repo_errors
async def hg_transplant(
    revisions: list[str] | str, repo_path: str = ".", source: str = ""
) -> str:
    """Cherry-pick changesets using the transplant extension."""
    path = validate_repo_path(repo_path)
    args = ["transplant"]
    if source:
        args.extend(["--source", source])
    revisions_list = parse_list_param(revisions)
    for rev in revisions_list:
        args.extend(["-r", rev])
    return await run_hg_command(args, cwd=path)
