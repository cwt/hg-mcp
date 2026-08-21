"""Merge and conflict resolution tools.

Provides tools for merging revisions and managing merge conflicts.
"""

from mcp.types import TextContent, ToolAnnotations

from hg_mcp.decorators import handle_repo_errors, json_tool
from hg_mcp.helpers import (
    parse_list_param,
    run_hg_command,
    sanitize_input,
    validate_repo_path,
)
from hg_mcp.server import mcp


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=False,
    )
)
@handle_repo_errors
async def hg_merge(repo_path: str = ".", revision: str = "") -> str:
    """Merge another revision into the current working directory.

    Equivalent to 'git merge'.

    **Note:** Mercurial requires explicit merges; no fast-forward by default.
    """
    try:
        path = validate_repo_path(repo_path)
        args = ["merge"]
        if revision:
            try:
                safe_revision = sanitize_input(revision, max_length=200)
            except ValueError as e:
                return f"Error: Invalid revision - {e}"
            args.append(safe_revision)
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
async def hg_resolve(repo_path: str = ".") -> list[TextContent]:
    """List and manage merge conflicts.

    Equivalent to 'git status' during a merge.
    """
    try:
        path = validate_repo_path(repo_path)
        return await run_hg_command(["resolve", "--list"], cwd=path)  # type: ignore[return-value]
    except Exception as e:
        return f"Error: {e}"  # type: ignore[return-value]


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=False,
    )
)
@handle_repo_errors
async def hg_graft(
    repo_path: str = ".",
    revisions: list[str] | str | None = None,
    continue_op: bool = False,
    abort: bool = False,
    stop: bool = False,
    no_commit: bool = False,
    log: bool = False,
    force: bool = False,
) -> str:
    """Copy changesets from other branches (merge-based cherry-pick).

    Equivalent to 'git cherry-pick'. Unlike transplant, graft uses
    Mercurial's merge machinery for more reliable three-way merges.
    This is a standard command (no extension required).

    Args:
        repo_path: The repository path
        revisions: Revision(s) to graft (use list for multiple)
        continue_op: Continue an interrupted graft
        abort: Abort an interrupted graft
        stop: Stop an interrupted graft (keep working directory changes)
        no_commit: Don't commit; apply changes to working directory only
        log: Append graft info to commit message
        force: Force graft even if changesets are related

    Examples:
        - hg_graft(revisions="abc123") -> Graft a single changeset
        - hg_graft(revisions=["abc123", "def456"]) -> Graft multiple
        - hg_graft(continue_op=True) -> Continue interrupted graft
        - hg_graft(abort=True) -> Abort interrupted graft
    """
    try:
        path = validate_repo_path(repo_path)
        args = ["graft"]

        if continue_op:
            args.append("--continue")
            return await run_hg_command(args, cwd=path)

        if abort:
            args.append("--abort")
            return await run_hg_command(args, cwd=path)

        if stop:
            args.append("--stop")
            return await run_hg_command(args, cwd=path)

        if no_commit:
            args.append("--no-commit")

        if log:
            args.append("--log")

        if force:
            args.append("--force")

        revisions_list = parse_list_param(revisions)
        if revisions_list:
            for rev in revisions_list:
                try:
                    safe_rev = sanitize_input(rev, max_length=200)
                except ValueError as e:
                    return f"Error: Invalid revision - {e}"
                args.extend(["-r", safe_rev])

        return await run_hg_command(args, cwd=path)
    except Exception as e:
        return f"Error: {e}"
