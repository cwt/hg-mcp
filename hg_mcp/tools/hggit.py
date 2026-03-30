"""hg-git integration tool for hg-mcp server."""

import json

from hg_mcp.decorators import handle_repo_errors
from hg_mcp.helpers import run_hg_command, validate_repo_path
from hg_mcp.hggit import (
    _check_git_remotes,
    _get_git_branches,
    _is_hggit_enabled,
)


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
