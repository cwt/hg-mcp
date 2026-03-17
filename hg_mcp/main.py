import asyncio
import functools
import json
import subprocess
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.types import Annotations, TextContent

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
    "annotate",
    "bookmarks",
    "branches",
    "children",
    "config",
    "files",
    "heads",
    "id",
    "incoming",
    "log",
    "lfile",
    "lfiles",
    "outgoing",
    "parents",
    "paths",
    "resolve",
    "status",
    "tags",
    "topics",
    "verify",
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


# --- Decorators for Tool Output ---


def json_tool(
    func: Callable[..., Awaitable[list[TextContent] | str]],
) -> Callable[..., Awaitable[list[TextContent]]]:
    """Decorator for tools that return JSON output.

    Wraps the returned JSON string in TextContent with audience: ["assistant"]
    annotation to indicate this content is intended for AI agents (minified,
    machine-readable) rather than human users.

    The decorated function should return a string (JSON output) or list[TextContent].
    """

    @functools.wraps(func)
    async def wrapper(  # type: ignore[no-untyped-def]
        *args, **kwargs
    ) -> list[TextContent]:
        result = await func(*args, **kwargs)

        # If result is an error (str type), return as plain text in TextContent
        # (users should see errors)
        if isinstance(result, str) and result.startswith("Error:"):
            return [
                TextContent(
                    type="text",
                    text=result,
                    annotations=Annotations(audience=["user"], priority=1.0),
                )
            ]

        # If result is already list[TextContent], return as-is
        if isinstance(result, list):
            return result

        # Wrap JSON output (str) in TextContent with assistant-only annotation
        return [
            TextContent(
                type="text",
                text=result,
                annotations=Annotations(audience=["assistant"], priority=0.5),
            )
        ]

    return wrapper


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

**hg-git Bookmark Synchronization**
- **CRITICAL**: When working in a Git-backed repo (via `hg_git`),
  bookmark-to-branch synchronization is essential.
- Git-backed repos use bookmark suffixes (e.g., `main.git`, `feature.git`)
  to track Git branches.
- The suffix is configured via `branch_bookmark_suffix` in Mercurial config
  (default: `.git`).
- Use `hg_git` to detect the current suffix setting and verify bookmark mapping.
- The `hg_commit` tool automatically runs `hg gexport` after committing in
  Git-backed repos to sync bookmarks to Git branches.

**Safety**
- Confirm before: strip, rebase -D, force evolve, public changeset rewrites
- After merge/rebase: always run `hg resolve --list`, report conflicts
- Before push: show `hg outgoing -G`, confirm if >5 changesets
- Default `hg log` to `-l 20` unless user specifies more

**Tools & Output**
- Use provided hg_* tools; don't suggest raw shell commands
- If "unknown command": suggest enabling extension (evolve, rebase, topics,
  histedit, largefiles, hggit)
- For graph visualization: use `hg log -G` (built-in since v2.3)
- Always interpret status/diff output; suggest next logical command
- Encourage atomic commits with clear messages
- **Diff**: Use `hg_diff()` for working directory diffs and
  `hg_diff(revisions="<spec>")` for revision diffs (e.g., "v1.0.0..tip", "500..510")

**Tags Usage**
- List all tags: use `hg_tags` to see all tags with revisions
- Create a tag: use `hg_tag(name="v1.0.0")` for current revision, or
  `hg_tag(name="v1.0.0", revision="tip")`
- Remove a tag: use `hg_tag(name="v1.0.0", remove=True)`
- **Important**:
  * Creating or removing a tag automatically creates a new commit.
  * Mercurial stores tags in `.hgtags` file.
  * This means the tag points to the revision *before* the tag commit,
    not the latest commit.
  * Warn users before creating tags.

**Modern Practices**
- Mention `hg absorb` for auto-amending into parents
- Stack changes: multiple bookmarks for related features
- Change IDs (not hashes) for user-facing references

Be concise. Use the tool first, then explain with exact next command.""",
)


# --- Helper Functions ---


def setup_event_loop() -> None:
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


def _get_extension_hint(error_text: str, command_args: list[str]) -> str:
    """Generate a hint if a command failed due to a missing extension."""
    if not command_args:
        return ""

    cmd = command_args[0]
    ext = EXTENSION_HINTS.get(cmd)

    # Check for extension-related errors
    is_extension_error = (
        "unknown command" in error_text.lower()
        or "unknown command" in error_text
        or f"'{cmd}'" in error_text
        and "unknown" in error_text.lower()
    )

    if not is_extension_error:
        return ""

    if ext:
        return (
            f"\n\nExtension '{ext}' is not enabled.\n\n"
            f"To enable it, add to your .hgrc file:\n\n"
            f"   [extensions]\n"
            f"   {ext} =\n\n"
            f"   Add this to ~/.hgrc (global) or .hg/hgrc (repository-specific)."
        )
    return ""


async def run_hg_command(
    args: list[str], cwd: Path | None = None, use_json: bool = True
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


def parse_list_param(
    param: list[str] | str | None, default: list[str] | None = None
) -> list[str]:
    """Parse a parameter that can be a list, a JSON string, or a single string.

    This handles MCP client serialization issues where arrays may be sent
    as JSON-encoded strings.

    Args:
        param: The parameter to parse (can be list, string, or None)
        default: Default value if param is None (defaults to empty list)

    Returns:
        A list of strings
    """
    if param is None:
        return default if default is not None else []
    if isinstance(param, list):
        # Type guard ensures this is list[str]
        return param
    if isinstance(param, str):
        # Could be a JSON array string or single value
        if param.startswith("["):
            try:
                parsed: object = json.loads(param)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed]
                # If JSON doesn't parse to a list, treat as single value
                return [param]
            except json.JSONDecodeError:
                # Not valid JSON, treat as single value
                return [param]
        return [param]
    # This should never happen, but return empty list as fallback
    return []  # type: ignore[unreachable]


def handle_repo_errors(
    func: Callable[..., Awaitable[str | list[TextContent]]],
) -> Callable[..., Awaitable[str | list[TextContent]]]:
    """Decorator to handle common repository validation errors.

    For functions decorated with @json_tool, returns errors as list[TextContent]
    with audience=['user'] to ensure errors are visible to users.
    For other functions, returns errors as plain str.
    """
    from mcp.types import Annotations as AnnotationsType

    @functools.wraps(func)
    async def wrapper(  # type: ignore[no-untyped-def]
        *args, **kwargs
    ) -> str | list[TextContent]:
        # We assume the first argument or 'repo_path' kwarg is the path
        # But since we invoke validate_repo_path inside the tools,
        # we essentially use this to catch the ValueErrors raised there.
        try:
            return await func(*args, **kwargs)
        except ValueError as e:
            msg = str(e)
            if "Not a Mercurial repository" in msg:
                error_msg = (
                    f"Error: {msg}\n\n"
                    "To verify if this is a Mercurial repository:\n"
                    "1. Check if a .hg directory exists\n"
                    "2. Try running hg_log to see commit history"
                )
            else:
                error_msg = f"Error: {msg}"

            # Check if the wrapped function is already decorated with @json_tool
            # by looking for the wrapper attribute or checking return type annotation
            import inspect

            hints = inspect.getfullargspec(func).annotations.get("return", None)
            is_json_tool = hints == list[TextContent] or "json_tool" in str(
                func
            )

            if is_json_tool:
                return [
                    TextContent(
                        type="text",
                        text=error_msg,
                        annotations=AnnotationsType(
                            audience=["user"], priority=1.0
                        ),
                    )
                ]
            return error_msg

    return wrapper


# --- Tools ---


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
    if limit < 1:
        return [
            TextContent(
                type="text",
                text="Error: limit must be at least 1",
                annotations=Annotations(audience=["user"], priority=1.0),
            )
        ]
    if limit > MAX_LOG_LIMIT:
        return [
            TextContent(
                type="text",
                text=f"Error: limit exceeds maximum allowed value of {MAX_LOG_LIMIT}",
                annotations=Annotations(audience=["user"], priority=1.0),
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
        args.extend(["-r", revisions])
    return await run_hg_command(args, cwd=path)


@mcp.tool()
@handle_repo_errors
async def hg_commit(
    message: str, repo_path: str = ".", files: list[str] | str | None = None
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
    if not result.startswith("Error:"):
        # Check if hg-git is enabled
        if await _is_hggit_enabled(path):
            # Check if repo is Git-backed
            is_git_backed, _ = await _check_git_remotes(path)
            if is_git_backed:
                # Run hg gexport to sync Mercurial bookmarks to Git branches
                export_result = await run_hg_command(["gexport"], cwd=path)
                if not export_result.startswith("Error:"):
                    result += "\n\n✓ hg-git: Bookmarks exported to Git branches"
                else:
                    result += f"\n\nNote: hg gexport skipped - {export_result}"

    return result


@mcp.tool()
@handle_repo_errors
async def hg_add(files: list[str] | str, repo_path: str = ".") -> str:
    """Add files to version control.

    Equivalent to 'git add'. Schedules new or modified files for commit.
    """
    path = validate_repo_path(repo_path)
    files_list = parse_list_param(files)
    return await run_hg_command(["add"] + files_list, cwd=path)


@mcp.tool()
@handle_repo_errors
async def hg_remove(files: list[str] | str, repo_path: str = ".") -> str:
    """Remove files from version control.

    Equivalent to 'git rm'. Schedules files for removal from the repository.
    """
    path = validate_repo_path(repo_path)
    files_list = parse_list_param(files)
    return await run_hg_command(["remove"] + files_list, cwd=path)


@mcp.tool()
@handle_repo_errors
async def hg_update(revision: str, repo_path: str = ".") -> str:
    """Update to a specific revision.

    Equivalent to 'git checkout' or 'git switch'.

    **Important:** Mercurial does NOT use 'HEAD' like Git. Use these instead:
    - `.` (dot) - Current parent revision
    - `tip` - Most recent changeset in the repository
    - `default` - Default branch head
    - Specific revision ID (e.g., "123" or "abc123def")
    - Bookmark name (e.g., "main", "feature-xyz")
    """
    path = validate_repo_path(repo_path)
    return await run_hg_command(["update", revision], cwd=path)


@mcp.tool()
@handle_repo_errors
async def hg_revert(
    repo_path: str = ".", files: list[str] | str | None = None
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
@handle_repo_errors
@json_tool
async def hg_resolve(repo_path: str = ".") -> list[TextContent]:
    """List and manage merge conflicts.

    Equivalent to 'git status' during a merge.
    """
    path = validate_repo_path(repo_path)
    return await run_hg_command(["resolve", "--list"], cwd=path)  # type: ignore[return-value]


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
@json_tool
async def hg_topics(repo_path: str = ".") -> list[TextContent]:
    """List all topics.

    Requires the 'topic' extension.
    """
    path = validate_repo_path(repo_path)
    return await run_hg_command(["topics"], cwd=path)  # type: ignore[return-value]


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
                return str(topic.get("name", "unknown"))
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
@json_tool
async def hg_bookmarks(repo_path: str = ".") -> list[TextContent]:
    """List all bookmarks.

    Bookmarks are lightweight pointers to revisions (like Git branches).
    Unlike Mercurial branches, bookmarks can be moved and deleted.
    """
    path = validate_repo_path(repo_path)
    return await run_hg_command(["bookmarks"], cwd=path)  # type: ignore[return-value]


@mcp.tool()
@handle_repo_errors
async def hg_branch(repo_path: str = ".", name: str | None = None) -> str:
    """Show or set the current branch.

    Equivalent to 'git branch'.

    **Note:** Mercurial branches are permanent (unlike Git's lightweight branches).
    For lightweight pointers, use bookmarks instead.
    """
    path = validate_repo_path(repo_path)
    if name:
        return await run_hg_command(["branch", name], cwd=path)
    return await run_hg_command(["branch"], cwd=path)


@mcp.tool()
@handle_repo_errors
@json_tool
async def hg_tags(repo_path: str = ".") -> list[TextContent]:
    """List all tags.

    Shows all tags in the repository with their associated revision numbers
    and changeset IDs.
    """
    path = validate_repo_path(repo_path)
    return await run_hg_command(["tags"], cwd=path)  # type: ignore[return-value]


@mcp.tool()
@handle_repo_errors
async def hg_tag(
    name: str,
    repo_path: str = ".",
    revision: str = "",
    remove: bool = False,
) -> str:
    """Create or remove a tag.

    Equivalent to 'hg tag'. Creates a new tag pointing to a specific revision.

    Args:
        name: The name of the tag to create or remove
        repo_path: The repository path
        revision: The revision to tag (defaults to current working directory parent)
        remove: If True, remove the tag instead of creating it
    """
    path = validate_repo_path(repo_path)
    args = ["tag"]

    if remove:
        args.append("--remove")

    args.extend(["-m", f"Add tag {name}"])
    args.append(name)

    if revision:
        args.extend(["-r", revision])

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
@json_tool
async def hg_paths(repo_path: str = ".") -> list[TextContent]:
    """List configured paths/remotes with JSON output."""
    path = validate_repo_path(repo_path)
    return await run_hg_command(["paths"], cwd=path)  # type: ignore[return-value]


@mcp.tool()
@handle_repo_errors
@json_tool
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


@mcp.tool()
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


@mcp.tool()
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

    if revision:
        args.extend(["-r", revision])

    # Support inline commands by creating a temp file
    if commands:
        import tempfile

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
            args.extend(["--commands", commands_file])
        else:
            # File path
            args.extend(["--commands", commands])

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


@mcp.tool()
@handle_repo_errors
@json_tool
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


@mcp.tool()
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


@mcp.tool()
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


@mcp.tool()
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


@mcp.tool()
@handle_repo_errors
@json_tool
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


@mcp.tool()
@handle_repo_errors
@json_tool
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
@handle_repo_errors
@json_tool
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
@handle_repo_errors
@json_tool
async def hg_files(repo_path: str = ".") -> list[TextContent]:
    """List tracked files.

    Shows all files tracked by Mercurial in the current revision.
    """
    path = validate_repo_path(repo_path)
    return await run_hg_command(["files"], cwd=path)  # type: ignore[return-value]


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
@handle_repo_errors
@json_tool
async def hg_verify(repo_path: str = ".") -> list[TextContent]:
    """Verify the integrity of the repository.

    Checks the repository for corruption and reports any issues found.
    This is a read-only operation that validates repository integrity.
    """
    path = validate_repo_path(repo_path)
    return await run_hg_command(["verify"], cwd=path)  # type: ignore[return-value]


@mcp.tool()
@handle_repo_errors
@json_tool
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


async def _check_git_remotes(path: Path) -> tuple[bool, list[str]]:
    """Check for git remotes in configuration."""
    output = await run_hg_command(["config", "paths"], cwd=path)
    remotes = []
    is_backed = False

    if not output.startswith("Error"):
        try:
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


def main() -> None:
    setup_event_loop()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
