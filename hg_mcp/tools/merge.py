"""Merge tools for hg-mcp server."""

from mcp.types import TextContent

from hg_mcp.decorators import handle_repo_errors, json_tool
from hg_mcp.helpers import run_hg_command, validate_repo_path
from hg_mcp.server import mcp


@mcp.tool()
@handle_repo_errors
async def hg_merge(repo_path: str = ".", revision: str = "") -> str:
    """Merge another revision into the current working directory.

    Equivalent to 'git merge'.

    **Note:** Mercurial requires explicit merges; no fast-forward by default.
    """
    path = validate_repo_path(repo_path)
    args = ["merge"]
    if revision:
        args.append(revision)
    return await run_hg_command(args, cwd=path)


@mcp.tool()
@json_tool
@handle_repo_errors
async def hg_resolve(repo_path: str = ".") -> list[TextContent]:
    """List and manage merge conflicts.

    Equivalent to 'git status' during a merge.
    """
    path = validate_repo_path(repo_path)
    return await run_hg_command(["resolve", "--list"], cwd=path)  # type: ignore[return-value]
