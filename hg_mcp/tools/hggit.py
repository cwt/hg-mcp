"""hg-git extension tools.

Provides tools for working with hg-git extension for Git-backed repositories.
"""

from pathlib import Path

from hg_mcp.decorators import handle_repo_errors
from hg_mcp.helpers import (
    GIT_REMOTE_PATTERNS,
    parse_list_param,
    run_hg_command,
    sanitize_input,
    validate_repo_path,
)
from hg_mcp.server import mcp


async def _is_hggit_enabled(path: Path) -> bool:
    """Check if hg-git extension is enabled."""
    output = await run_hg_command(["config", "extensions"], cwd=path)
    if output.startswith("Error"):
        return False

    # Check for direct config entry
    for line in output.splitlines():
        if "=" in line:
            key = line.split("=", 1)[0].strip()
            if key in ["hggit", "hg-git", "hgext.hggit", "hgext.git"]:
                return True

    # Fallback: Check if help recognizes it (implicit enable)
    help_out = await run_hg_command(["help", "hggit"], cwd=path)
    return "hg-git" in help_out.lower() or "hggit" in help_out.lower()


async def _check_git_remotes(path: Path) -> tuple[bool, list[str]]:
    """Check for git remotes in configuration."""
    output = await run_hg_command(["config", "paths"], cwd=path)
    remotes = []
    is_backed = False

    if not output.startswith("Error"):
        try:
            import json

            config_items = json.loads(output)
            for item in config_items:
                name = item.get("name", "")
                value = item.get("value", "")
                is_git_remote = value.startswith("git+") or any(
                    p in value for p in GIT_REMOTE_PATTERNS
                )
                if is_git_remote:
                    is_backed = True
                    remotes.append(f"  {name} = {value}")
        except (json.JSONDecodeError, TypeError):
            pass

    # Check for internal tracking files
    if (path / ".hg" / "git-mapfile").exists() or (
        path / ".hg" / "git-branch"
    ).exists():
        is_backed = True

    return is_backed, remotes


async def _get_git_branches(
    path: Path, suffix: str | None
) -> tuple[list[str], list[str]]:
    """Get separated lists of git-tracked and local bookmarks."""
    output = await run_hg_command(["bookmarks"], cwd=path)
    git_branches = []
    local_bookmarks = []

    if output.startswith("Error") or "no bookmarks set" in output.lower():
        return [], []

    try:
        import json

        bookmarks = json.loads(output)
        for bm in bookmarks:
            name = bm.get("bookmark", "")
            is_active = bm.get("active", False)
            display_str = f"  {name}" + (" (active)" if is_active else "")

            # If suffix is configured, only match bookmarks ending with suffix
            # If no suffix, all bookmarks are treated as Git-tracked
            if suffix is None:
                # No suffix configured - all bookmarks map directly to Git branches
                git_branches.append(display_str)
            elif name.endswith(suffix):
                # Strip suffix to show original Git branch name
                git_name = name[: -len(suffix)]
                git_branches.append(f"{display_str} → {git_name}")
            else:
                # Bookmark doesn't match suffix pattern - treat as local
                local_bookmarks.append(display_str)
    except (json.JSONDecodeError, TypeError):
        pass

    return git_branches, local_bookmarks


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
