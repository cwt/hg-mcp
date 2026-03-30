"""Repository inspection tools for hg-mcp server."""

from mcp.types import TextContent

from hg_mcp.decorators import handle_repo_errors, json_tool
from hg_mcp.helpers import format_bytes, run_hg_command, validate_repo_path
from hg_mcp.server import mcp


@mcp.tool()
@handle_repo_errors
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
@json_tool
@handle_repo_errors
async def hg_files(repo_path: str = ".") -> list[TextContent]:
    """List tracked files.

    Shows all files tracked by Mercurial in the current revision.
    """
    path = validate_repo_path(repo_path)
    return await run_hg_command(["files"], cwd=path)  # type: ignore[return-value]


@mcp.tool()
@handle_repo_errors
async def hg_help(repo_path: str = ".", topic: str = "") -> str:
    """Get help on Mercurial commands and concepts."""
    # Special handling: hg_help can work without a repo, but prefers one.
    try:
        path = validate_repo_path(repo_path)
    except ValueError:
        path = None

    if topic:
        return await run_hg_command(["help", topic], cwd=path)
    return await run_hg_command(["help"], cwd=path)


@mcp.tool()
@json_tool
@handle_repo_errors
async def hg_identify(
    repo_path: str = ".", revision: str = ""
) -> list[TextContent]:
    """Identify the working directory or specified revision.

    Returns the changeset ID (hash) and branch information for the
    working directory or a specific revision.

    Args:
        repo_path: The repository path
        revision: Revision to identify (defaults to working directory parent)
    """
    path = validate_repo_path(repo_path)
    args = ["identify"]
    if revision:
        args.extend(["-r", revision])
    return await run_hg_command(args, cwd=path)  # type: ignore[return-value]


@mcp.tool()
@handle_repo_errors
async def hg_largefiles(repo_path: str = ".") -> str:
    """Show large files tracked by the largefiles extension."""
    path = validate_repo_path(repo_path)
    hglf_path = path / ".hglf"

    if not hglf_path.is_dir():
        return "No largefiles found in this repository."

    largefiles = []
    try:
        # Recursively find all standin files
        for file_path in hglf_path.rglob("*"):
            if not file_path.is_file():
                continue

            rel_path = str(file_path.relative_to(hglf_path))
            size = 0

            try:
                # Standin files format: hash\nsize\nfilename
                content = file_path.read_text(encoding="utf-8").strip()
                lines = content.split("\n")
                if len(lines) >= 2 and lines[1].isdigit():
                    size = int(lines[1])
            except (ValueError, UnicodeDecodeError, OSError):
                # If we can't read/parse the standin, just report 0 size
                pass

            largefiles.append((rel_path, size))

    except Exception as e:
        return f"Error reading largefiles: {e}"

    if not largefiles:
        return "No largefiles found in this repository."

    # Sort by size (descending)
    largefiles.sort(key=lambda x: x[1], reverse=True)

    lines = ["Largefiles in repository:", "-" * 50]
    for filename, size in largefiles:
        lines.append(f"  {filename}: {format_bytes(size)}")

    return "\n".join(lines)


@mcp.tool()
@handle_repo_errors
async def hg_summary(repo_path: str = ".") -> str:
    """Summarize working directory state.

    Provides a concise summary of the working directory including:
    - Current branch and parent revision
    - Commit phase
    - Pending commits, merges, and updates
    - Repository status
    """
    path = validate_repo_path(repo_path)
    return await run_hg_command(["summary"], cwd=path)


@mcp.tool()
@json_tool
@handle_repo_errors
async def hg_verify(repo_path: str = ".") -> list[TextContent]:
    """Verify the integrity of the repository.

    Checks the repository for corruption and reports any issues found.
    This is a read-only operation that validates repository integrity.
    """
    path = validate_repo_path(repo_path)
    return await run_hg_command(["verify"], cwd=path)  # type: ignore[return-value]
