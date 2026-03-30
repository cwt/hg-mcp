"""Remote operations tools for hg-mcp server."""

from mcp.types import TextContent

from hg_mcp.decorators import handle_repo_errors, json_tool
from hg_mcp.helpers import run_hg_command, validate_repo_path
from hg_mcp.server import mcp


@mcp.tool()
@json_tool
@handle_repo_errors
async def hg_incoming(
    repo_path: str = ".", source: str = ""
) -> list[TextContent]:
    """Show new changesets found in source.

    Displays changesets that exist in the source repository but not in the
    local repository. Useful for previewing what would be pulled.

    Args:
        repo_path: The repository path
        source: Remote source to check (defaults to default path)
    """
    path = validate_repo_path(repo_path)
    args = ["incoming"]
    if source:
        args.append(source)
    return await run_hg_command(args, cwd=path)  # type: ignore[return-value]


@mcp.tool()
@json_tool
@handle_repo_errors
async def hg_outgoing(
    repo_path: str = ".", destination: str = ""
) -> list[TextContent]:
    """Show changesets not found in the destination.

    Displays changesets that exist locally but not in the destination
    repository. Useful for previewing what would be pushed.

    Args:
        repo_path: The repository path
        destination: Remote destination to check (defaults to default path)
    """
    path = validate_repo_path(repo_path)
    args = ["outgoing"]
    if destination:
        args.append(destination)
    return await run_hg_command(args, cwd=path)  # type: ignore[return-value]


@mcp.tool()
@json_tool
@handle_repo_errors
async def hg_paths(repo_path: str = ".") -> list[TextContent]:
    """List configured paths/remotes with JSON output."""
    path = validate_repo_path(repo_path)
    return await run_hg_command(["paths"], cwd=path)  # type: ignore[return-value]


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
async def hg_push(repo_path: str = ".", destination: str = "") -> str:
    """Push changes to a remote repository.

    Equivalent to 'git push'. Use hg_paths to see available remotes.
    Note: Mercurial typically uses 'default' instead of Git's 'origin'.
    """
    path = validate_repo_path(repo_path)
    args = ["push"]
    if destination:
        args.append(destination)
    result = await run_hg_command(args, cwd=path)

    # Add helpful hint if push failed due to unknown destination
    # Mercurial error messages typically contain "does not exist" or "unknown"
    if result.startswith("Error:"):
        error_indicators = ["does not exist", "unknown", "abort:"]
        if any(indicator in result.lower() for indicator in error_indicators):
            paths_output = await run_hg_command(["paths"], cwd=path)
            if not paths_output.startswith("Error:") and paths_output:
                result += f"\n\nAvailable remotes:\n{paths_output}"

    return result
