"""Helper functions for the hg-mcp MCP server.

Provides common utilities for repo validation, command execution,
and parameter parsing.
"""

import asyncio
import json
import secrets
import subprocess
from pathlib import Path
from typing import Any, Awaitable, Callable


class APIKeyMiddleware:
    """ASGI Middleware that validates API key from request headers."""

    def __init__(self, app: Any, api_key: str) -> None:
        self.app = app
        self.api_key = api_key

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Skip auth for CORS preflight
        if scope["method"] == "OPTIONS":
            await self.app(scope, receive, send)
            return

        # Check API key from headers
        # Headers in scope are a list of (name, value) tuples as bytes
        headers = dict(scope.get("headers", []))
        provided_key_bytes = headers.get(b"x-api-key") or headers.get(b"api-key")

        is_authorized = False
        if provided_key_bytes:
            try:
                provided_key = provided_key_bytes.decode("latin-1")
                if secrets.compare_digest(provided_key, self.api_key):
                    is_authorized = True
            except Exception:
                pass

        if is_authorized:
            await self.app(scope, receive, send)
            return

        # Unauthorized response
        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": json.dumps(
                    {"error": "Unauthorized: Invalid or missing API key"}
                ).encode("utf-8"),
            }
        )


def validate_path_in_jail(path: Path) -> Path:
    """Validate that a path is within the jail directory.

    Args:
        path: The absolute path to validate.

    Returns:
        The resolved absolute Path object.

    Raises:
        ValueError: If jail is set and path is outside it.
    """
    from hg_mcp.server import mcp

    if mcp.jail_path is None:
        return path

    resolved = path.resolve()
    try:
        resolved.relative_to(mcp.jail_path)
    except ValueError:
        raise ValueError(
            f"Path '{resolved}' is outside the allowed jail directory '{mcp.jail_path}'. "
            f"Access is restricted to '{mcp.jail_path}' and its subdirectories."
        )

    return resolved


# Mapping of command names to their required extensions for error hints
EXTENSION_HINTS: dict[str, str] = {
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
JSON_SUPPORTED_COMMANDS: frozenset[str] = frozenset(
    [
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
        "rebase",
        "resolve",
        "status",
        "strip",
        "tags",
        "topics",
        "verify",
    ]
)

# Patterns to identify Git remotes
GIT_REMOTE_PATTERNS: list[str] = [
    ".git",
    "github.com",
    "gitlab.com",
    "bitbucket.org",
    "git://",
    "ssh://git@",
    "https://github.com",
]

MAX_LOG_LIMIT = 1000


def sanitize_input(value: str, max_length: int = 1000) -> str:
    """Sanitize user-provided input to prevent potential command injection.

    While subprocess.exec is used (safer than shell=True), this provides
    defense-in-depth by rejecting obviously malicious input.

    Args:
        value: The input string to sanitize
        max_length: Maximum allowed length (default 1000)

    Returns:
        The sanitized string

    Raises:
        ValueError: If input contains dangerous patterns or exceeds max length
    """
    if not value:
        return value

    if len(value) > max_length:
        raise ValueError(f"Input exceeds maximum length of {max_length}")

    # Reject whitespace-only input
    if not value.strip():
        raise ValueError("Input must not be empty or whitespace-only")

    # Check for shell metacharacters that could be dangerous
    # Even though we use subprocess.exec, this is defense-in-depth
    dangerous_patterns = ["`", "$(", "${", "|", ";", "&&", "||", ">", "<", "&"]
    for pattern in dangerous_patterns:
        if pattern in value:
            raise ValueError(f"Input contains invalid character sequence: {pattern}")

    return value


def setup_event_loop() -> None:
    """Set up uvloop (Unix) or winloop (Windows) for better performance if available."""
    import sys

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
    current_size: float = float(size)
    for unit in ["bytes", "KB", "MB", "GB", "TB"]:
        if current_size < 1024:
            if unit == "bytes":
                return f"{int(current_size)} {unit}"
            return f"{current_size:.2f} {unit}"
        current_size /= 1024
    return f"{current_size:.2f} PB"


def validate_path(repo_path: str, create_if_missing: bool = False) -> Path:
    """Validate that repo_path is a safe directory path.

    Args:
        repo_path: The path to validate.
        create_if_missing: If True, create the directory if it doesn't exist.

    Returns:
        The resolved absolute Path object.

    Raises:
        ValueError: If the path is invalid or is not a directory.
    """
    try:
        # Handle empty or default path
        p_str = repo_path.strip() if repo_path and repo_path.strip() else "."
        path = Path(p_str).absolute()
    except Exception as e:
        raise ValueError(f"Invalid path format: {e}") from e

    # Check jail restriction
    path = validate_path_in_jail(path)

    if not path.exists():
        if create_if_missing:
            try:
                path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                raise ValueError(f"Failed to create directory {path}: {e}")
        else:
            raise ValueError(f"Path does not exist: {path}")

    if not path.is_dir():
        raise ValueError(f"Path is not a directory: {path}")

    return path


def validate_repo_path(repo_path: str) -> Path:
    """Validate that repo_path is a safe, existing Mercurial repository.

    Args:
        repo_path: The path to validate.

    Returns:
        The resolved absolute Path object.

    Raises:
        ValueError: If the path is invalid, does not exist, or is not a repo.
    """
    # Check jail restriction first (before resolving)
    raw_path = Path(
        repo_path.strip() if repo_path and repo_path.strip() else "."
    ).absolute()
    validate_path_in_jail(raw_path)

    path = validate_path(repo_path)

    # Check for .hg directory in current or parent directories
    current = path
    repo_root = None
    while True:
        if (current / ".hg").is_dir():
            repo_root = current
            break
        if current.parent == current:  # Root directory reached
            break
        current = current.parent

    if repo_root is None:
        raise ValueError(
            f"Not a Mercurial repository (no .hg found in {path} or parents)"
        )

    # Verify the actual repo root is also within jail
    validate_path_in_jail(repo_root)

    return repo_root


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
        or (f"'{cmd}'" in error_text and "unknown" in error_text.lower())
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
    args: list[str],
    cwd: Path | None = None,
    use_json: bool = True,
    env: dict[str, str] | None = None,
) -> str:
    """Run an hg command asynchronously and return its output.

    Args:
        args: Command arguments (e.g., ["status", "-T", "json"])
        cwd: Working directory
        use_json: If True and command supports it, automatically add -T json flag
        env: Optional environment variables to pass to the command
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
        import os as os_module

        # Merge provided env with system environment
        process_env = os_module.environ.copy()
        if env:
            process_env.update(env)

        from hg_mcp.server import mcp

        hg_executable = mcp.hg_path if mcp.hg_path else "hg"

        process = await asyncio.create_subprocess_exec(
            hg_executable,
            *cmd_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            env=process_env,
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
        return "Error: Mercurial (hg) command not found. Please install Mercurial."
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


async def sync_git_bookmarks(path: Path) -> str:
    """Sync Mercurial bookmarks to Git branches if hg-git is enabled and repo is Git-backed."""
    try:
        if await _is_hggit_enabled(path):
            is_git_backed, _ = await _check_git_remotes(path)
            if is_git_backed:
                export_result = await run_hg_command(["gexport"], cwd=path)
                if not export_result.startswith("Error"):
                    return "\n\n✓ hg-git: Bookmarks exported to Git branches"
                return f"\n\nNote: hg gexport skipped - {export_result}"
    except Exception as e:
        return f"\n\nNote: hg-git integration check failed: {e}"
    return ""
