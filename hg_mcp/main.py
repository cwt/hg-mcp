import asyncio
import functools
import json
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from mcp.server.fastmcp import FastMCP

# --- Constants ---

MAX_LOG_LIMIT = 1000

# Mapping of command names to their required extensions for error hints
EXTENSION_HINTS = {
    "topic": "topic",
    "topics": "topic",
    "evolve": "evolve",
    "strip": "strip",
    "rebase": "rebase",
    "histedit": "histedit",
    "transplant": "transplant",
    "lfiles": "largefiles",
    "lfile": "largefiles",
    "git-cleanup": "hggit",
}

# Commands that support JSON output format with -T json
JSON_SUPPORTED_COMMANDS = {
    "status",
    "log",
    "bookmarks",
    "topics",
    "config",
    "resolve",
    "lfiles",
    "lfile",
    "paths",
    "tags",
    "heads",
    "id",
    "parents",
    "children",
    "outgoing",
    "incoming",
}

# Patterns to identify Git remotes
GIT_REMOTE_PATTERNS = [
    ".git",
    "github.com",
    "gitlab.com",
    "bitbucket.org",
    "git://",
    "ssh://git@",
    "https://github.com",
]

# --- Server Initialization ---

mcp = FastMCP(
    name="hg",
    instructions="""You are an expert Mercurial engineer. Follow modern best practices:

**Core Workflow**
- Use **bookmarks** for named pointers, **topics** for WIP feature isolation
- Enable **evolve** for mutable history; prefer `hg amend`/`hg evolve` over strip
- Use **phases** (draft/public/secret) to control what's safe to rewrite
- Largefiles: handle binaries transparently; suggest extension if needed
- hg-git: detect Git-backed repos; explain `hg gexport`/`hg gimport` when relevant

**Safety**
- Confirm before: strip, rebase -D, force evolve, public changeset rewrites
- After merge/rebase: always run `hg resolve --list`, report conflicts
- Before push: show `hg outgoing -G`, confirm if >5 changesets
- Default `hg log` to `-l 20` unless user specifies more

**Tools & Output**
- Use provided hg_* tools; don't suggest raw shell commands
- If "unknown command": suggest enabling extension (evolve, rebase, topics, histedit, largefiles, hggit)
- For graph visualization: use `hg log -G` (built-in since v2.3)
- Always interpret status/diff output; suggest next logical command
- Encourage atomic commits with clear messages

**Modern Practices**
- Mention `hg absorb` for auto-amending into parents
- Stack changes: multiple bookmarks for related features
- Change IDs (not hashes) for user-facing references

Be concise. Use the tool first, then explain with exact next command.""",
)


# --- Helper Functions ---


def setup_event_loop():
    """Set up uvloop (Unix) or winloop (Windows) for better performance if available."""
    if sys.platform == "win32":
        try:
            import winloop

            winloop.install()
        except ImportError:
            pass
    else:
        try:
            import uvloop

            uvloop.install()
        except ImportError:
            pass


def format_bytes(size: int) -> str:
    """Format bytes into a human-readable string (e.g., '1.5 MB')."""
    current_size = float(size)
    for unit in ["bytes", "KB", "MB", "GB", "TB"]:
        if current_size < 1024:
            if unit == "bytes":
                return f"{int(current_size)} {unit}"
            return f"{current_size:.2f} {unit}"
        current_size /= 1024
    return f"{current_size:.2f} PB"


def validate_repo_path(repo_path: str) -> Path:
    """Validate that repo_path is a safe, existing Mercurial repository.

    Args:
        repo_path: The path to validate.

    Returns:
        The resolved absolute Path object.

    Raises:
        ValueError: If the path is invalid, does not exist, or is not a repo.
    """
    try:
        # Handle empty or default path
        p_str = repo_path.strip() if repo_path and repo_path.strip() else "."
        path = Path(p_str).absolute()
    except Exception as e:
        raise ValueError(f"Invalid path format: {e}") from e

    if not path.exists():
        raise ValueError(f"Path does not exist: {path}")

    if not path.is_dir():
        raise ValueError(f"Path is not a directory: {path}")

    # Check for .hg directory in current or parent directories
    current = path
    while True:
        if (current / ".hg").is_dir():
            return current
        if current.parent == current:  # Root directory reached
            break
        current = current.parent

    raise ValueError(
        f"Not a Mercurial repository (no .hg found in {path} or parents)"
    )


def _get_extension_hint(error_text: str, command_args: List[str]) -> str:
    """Generate a hint if a command failed due to a missing extension."""
    if "unknown command" not in error_text or not command_args:
        return ""

    cmd = command_args[0]
    ext = EXTENSION_HINTS.get(cmd)
    if ext:
        return (
            f"\n\nHint: The '{cmd}' command requires the '{ext}' extension. "
            f"You may need to enable it in your .hgrc file by adding:\n\n"
            f"[extensions]\n{ext} ="
        )
    return ""


async def run_hg_command(
    args: List[str], cwd: Optional[Path] = None, use_json: bool = True
) -> str:
    """Run an hg command asynchronously and return its output.

    Args:
        args: Command arguments (e.g., ["status", "-T", "json"])
        cwd: Working directory
        use_json: If True and command supports it, automatically add -T json flag
    """
    if not args:
        return "Error: No command provided."

    is_json = False
    # Automatically add -T json for commands that support it
    if use_json and args[0] in JSON_SUPPORTED_COMMANDS:
        is_json = True
        # Check if -T is already specified
        if "-T" not in args and "--template" not in args:
            cmd_args = args + ["-T", "json"]
        else:
            cmd_args = args
    else:
        cmd_args = args

    try:
        process = await asyncio.create_subprocess_exec(
            "hg",
            *cmd_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
        )
        stdout, stderr = await process.communicate()

        output = stdout.decode().strip()
        error_output = stderr.decode().strip()

        if process.returncode != 0:
            hint = _get_extension_hint(error_output, args)
            return f"Error: {error_output}{hint}"

        # Minimize JSON output using Python's built-in json module
        if is_json and output:
            try:
                data = json.loads(output)
                output = json.dumps(data, separators=(",", ":"))
            except Exception:
                # Fallback to original output if parsing fails
                pass

        return output

    except FileNotFoundError:
        return (
            "Error: Mercurial (hg) command not found. Please install Mercurial."
        )
    except Exception as e:
        return f"Error executing hg command: {e}"


def handle_repo_errors(func):
    """Decorator to handle common repository validation errors."""

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        # We assume the first argument or 'repo_path' kwarg is the path
        # But since we invoke validate_repo_path inside the tools,
        # we essentially use this to catch the ValueErrors raised there.
        try:
            return await func(*args, **kwargs)
        except ValueError as e:
            msg = str(e)
            if "Not a Mercurial repository" in msg:
                # Extract path from error message or args if possible, but keeping it simple
                return (
                    f"Error: {msg}\n\n"
                    "To verify if this is a Mercurial repository:\n"
                    "1. Check if a .hg directory exists\n"
                    "2. Try running hg_log to see commit history"
                )
            return f"Error: {msg}"

    return wrapper


# --- Tools ---


@mcp.tool()
@handle_repo_errors
async def hg_status(repo_path: str = ".") -> str:
    """Show the status of files in the working directory.

    Equivalent to 'git status'. Shows modified, added, removed files.
    Returns a clear message even when there are no changes.
    """
    path = validate_repo_path(repo_path)
    return await run_hg_command(["status"], cwd=path)


@mcp.tool()
@handle_repo_errors
async def hg_log(repo_path: str = ".", limit: int = 10) -> str:
    """Show commit history.

    Equivalent to 'git log'. Displays revisions with changeset ID, author, date, and message.
    """
    if limit < 1:
        return "Error: limit must be at least 1"
    if limit > MAX_LOG_LIMIT:
        return f"Error: limit exceeds maximum allowed value of {MAX_LOG_LIMIT}"

    path = validate_repo_path(repo_path)
    return await run_hg_command(["log", "--limit", str(limit)], cwd=path)


@mcp.tool()
@handle_repo_errors
async def hg_diff(repo_path: str = ".") -> str:
    """Show changes in the working directory.

    Equivalent to 'git diff'. Shows line-by-line changes to tracked files.
    """
    path = validate_repo_path(repo_path)
    return await run_hg_command(["diff"], cwd=path)


@mcp.tool()
@handle_repo_errors
async def hg_commit(
    message: str, repo_path: str = ".", files: Optional[List[str]] = None
) -> str:
    """Commit changes with a message.

    Equivalent to 'git commit'. Records changes in the repository with a description.
    """
    path = validate_repo_path(repo_path)
    args = ["commit", "-m", message]
    if files:
        args.extend(files)
    return await run_hg_command(args, cwd=path)


@mcp.tool()
@handle_repo_errors
async def hg_add(files: List[str], repo_path: str = ".") -> str:
    """Add files to version control.

    Equivalent to 'git add'. Schedules new or modified files for commit.
    """
    path = validate_repo_path(repo_path)
    return await run_hg_command(["add"] + files, cwd=path)


@mcp.tool()
@handle_repo_errors
async def hg_remove(files: List[str], repo_path: str = ".") -> str:
    """Remove files from version control.

    Equivalent to 'git rm'. Schedules files for removal from the repository.
    """
    path = validate_repo_path(repo_path)
    return await run_hg_command(["remove"] + files, cwd=path)


@mcp.tool()
@handle_repo_errors
async def hg_update(revision: str, repo_path: str = ".") -> str:
    """Update to a specific revision.

    Equivalent to 'git checkout' or 'git switch'.
    """
    path = validate_repo_path(repo_path)
    return await run_hg_command(["update", revision], cwd=path)


@mcp.tool()
@handle_repo_errors
async def hg_revert(
    repo_path: str = ".", files: Optional[List[str]] = None
) -> str:
    """Revert uncommitted changes.

    Equivalent to 'git checkout -- <files>' or 'git restore <files>'.
    """
    path = validate_repo_path(repo_path)
    args = ["revert"]
    if files:
        args.extend(files)
    else:
        args.append("--all")
    return await run_hg_command(args, cwd=path)


@mcp.tool()
@handle_repo_errors
async def hg_merge(repo_path: str = ".", revision: str = "") -> str:
    """Merge another revision into the current working directory.

    Equivalent to 'git merge'.
    """
    path = validate_repo_path(repo_path)
    args = ["merge"]
    if revision:
        args.append(revision)
    return await run_hg_command(args, cwd=path)


@mcp.tool()
@handle_repo_errors
async def hg_resolve(repo_path: str = ".") -> str:
    """List and manage merge conflicts.

    Equivalent to 'git status' during a merge.
    """
    path = validate_repo_path(repo_path)
    return await run_hg_command(["resolve", "--list"], cwd=path)


@mcp.tool()
@handle_repo_errors
async def hg_topic(name: str, repo_path: str = ".") -> str:
    """Create a new topic.

    Requires the 'topic' extension.
    """
    path = validate_repo_path(repo_path)
    return await run_hg_command(["topic", name], cwd=path)


@mcp.tool()
@handle_repo_errors
async def hg_topics(repo_path: str = ".") -> str:
    """List all topics.

    Requires the 'topic' extension.
    """
    path = validate_repo_path(repo_path)
    return await run_hg_command(["topics"], cwd=path)


@mcp.tool()
@handle_repo_errors
async def hg_topic_current(repo_path: str = ".") -> str:
    """Show the current topic."""
    path = validate_repo_path(repo_path)
    output = await run_hg_command(["topics"], cwd=path)

    if output.startswith("Error"):
        return output

    # Parse JSON output to find active topic
    try:
        topics = json.loads(output)
        for topic in topics:
            if isinstance(topic, dict) and topic.get("active"):
                return topic.get("name", "unknown")
            # Fallback: check for marker in string format
            if isinstance(topic, str) and topic.startswith("*"):
                return topic.lstrip("* ").strip()
    except (json.JSONDecodeError, TypeError):
        # Fallback to text parsing if JSON parsing fails
        for line in output.splitlines():
            if line.strip().startswith("*"):
                parts = line.strip().split(None, 1)
                if len(parts) > 1:
                    return parts[1].strip()
                return parts[0][1:].strip()

    return "No active topic found."


@mcp.tool()
@handle_repo_errors
async def hg_bookmarks(repo_path: str = ".") -> str:
    """List all bookmarks.

    Bookmarks are lightweight pointers to revisions.
    """
    path = validate_repo_path(repo_path)
    return await run_hg_command(["bookmarks"], cwd=path)


@mcp.tool()
@handle_repo_errors
async def hg_branch(repo_path: str = ".", name: Optional[str] = None) -> str:
    """Show or set the current branch.

    Equivalent to 'git branch'.
    """
    path = validate_repo_path(repo_path)
    if name:
        return await run_hg_command(["branch", name], cwd=path)
    return await run_hg_command(["branch"], cwd=path)


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

    # Add helpful hint if destination doesn't exist
    if result.startswith("Error:") and "does not exist" in result:
        paths_output = await run_hg_command(["paths"], cwd=path)
        if not paths_output.startswith("Error:") and paths_output:
            result += f"\n\nAvailable remotes:\n{paths_output}"

    return result


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
async def hg_paths(repo_path: str = ".") -> str:
    """List configured paths/remotes with JSON output."""
    path = validate_repo_path(repo_path)
    return await run_hg_command(["paths"], cwd=path)


@mcp.tool()
@handle_repo_errors
async def hg_config(repo_path: str = ".") -> str:
    """Show Mercurial configuration including enabled extensions."""
    path = validate_repo_path(repo_path)
    return await run_hg_command(["config"], cwd=path)


@mcp.tool()
@handle_repo_errors
async def hg_extensions(repo_path: str = ".") -> str:
    """List enabled Mercurial extensions."""
    path = validate_repo_path(repo_path)
    return await run_hg_command(["config", "extensions"], cwd=path)


@mcp.tool()
@handle_repo_errors
async def hg_rebase(
    repo_path: str = ".",
    source: str = "",
    dest: str = "",
    collapse: bool = False,
    keep: bool = False,
) -> str:
    """Rebase changes using the rebase extension."""
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


@mcp.tool()
@handle_repo_errors
async def hg_strip(
    revision: str, keep: bool = False, repo_path: str = "."
) -> str:
    """Remove a changeset using the strip extension."""
    path = validate_repo_path(repo_path)
    args = ["strip"]
    if keep:
        args.append("--keep")
    args.append(revision)
    return await run_hg_command(args, cwd=path)


@mcp.tool()
@handle_repo_errors
async def hg_histedit(
    repo_path: str = ".", revision: str = "", action: str = ""
) -> str:
    """Edit history interactively using the histedit extension."""
    path = validate_repo_path(repo_path)
    args = ["histedit"]
    if revision:
        args.append(revision)
    return await run_hg_command(args, cwd=path)


@mcp.tool()
@handle_repo_errors
async def hg_evolve(repo_path: str = ".") -> str:
    """Show evolution history using the evolve extension."""
    path = validate_repo_path(repo_path)
    return await run_hg_command(["evolve"], cwd=path)


@mcp.tool()
@handle_repo_errors
async def hg_transplant(
    revisions: List[str], source: str = "", repo_path: str = "."
) -> str:
    """Cherry-pick changesets using the transplant extension."""
    path = validate_repo_path(repo_path)
    args = ["transplant"]
    if source:
        args.extend(["--source", source])
    for rev in revisions:
        args.extend(["-r", rev])
    return await run_hg_command(args, cwd=path)


@mcp.tool()
@handle_repo_errors
async def hg_help(repo_path: str = ".", topic: str = "") -> str:
    """Get help on Mercurial commands and concepts."""
    # Special handling: hg_help can work without a repo, but prefers one.
    try:
        path = validate_repo_path(repo_path)
    except ValueError:
        path = None  # type: ignore

    if topic:
        return await run_hg_command(["help", topic], cwd=path)
    return await run_hg_command(["help"], cwd=path)


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
            except Exception:
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


# --- hg-git Logic ---


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


async def _check_git_remotes(path: Path) -> Tuple[bool, List[str]]:
    """Check for git remotes in configuration."""
    output = await run_hg_command(["config", "paths"], cwd=path)
    remotes = []
    is_backed = False

    if not output.startswith("Error"):
        for line in output.splitlines():
            if "=" not in line:
                continue
            key, value = [p.strip() for p in line.split("=", 1)]

            is_git_remote = value.startswith("git+") or any(
                p in value for p in GIT_REMOTE_PATTERNS
            )

            if is_git_remote:
                is_backed = True
                remotes.append(f"  {key} = {value}")

    # Check for internal tracking files
    if (path / ".hg" / "git-mapfile").exists() or (
        path / ".hg" / "git-branch"
    ).exists():
        is_backed = True

    return is_backed, remotes


async def _get_git_branches(
    path: Path, suffix: str
) -> Tuple[List[str], List[str]]:
    """Get separated lists of git-tracked and local bookmarks."""
    output = await run_hg_command(["bookmarks"], cwd=path)
    git_branches = []
    local_bookmarks = []

    if output.startswith("Error") or "no bookmarks set" in output.lower():
        return [], []

    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue

        parts = line.split()
        if not parts:
            continue

        is_active = parts[0] == "*"
        name = parts[1] if is_active and len(parts) > 1 else parts[0]
        display_str = f"  {name}" + (" (active)" if is_active else "")

        if name.endswith(suffix):
            # Strip suffix to show original git name
            git_name = name[: -len(suffix)] if suffix else name
            git_branches.append(f"{display_str} → {git_name}")
        else:
            local_bookmarks.append(display_str)

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

    # 3. Get Git Config
    config_out = await run_hg_command(["config", "git"], cwd=path)
    suffix = ".git"  # Default
    if not config_out.startswith("Error"):
        for line in config_out.splitlines():
            if "branch_bookmark_suffix" in line:
                suffix = line.split("=", 1)[1].strip()
                break

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
    lines.append(f"\nCurrent suffix: '{suffix}'\n")

    if git_branches:
        lines.append("Git-tracked bookmarks:")
        lines.extend(git_branches)
    else:
        lines.append("No Git-tracked bookmarks found.")

    if local_bookmarks:
        lines.append("\nLocal bookmarks:")
        lines.extend(local_bookmarks)

    return "\n".join(lines)


def main():
    setup_event_loop()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
