"""Helper functions for the hg-mcp MCP server.

Provides common utilities for repo validation, command execution,
and parameter parsing.
"""

import asyncio
import configparser
import json
import secrets
import subprocess
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any


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
            f"Path '{resolved}' is outside the allowed jail directory "
            f"'{mcp.jail_path}'. "
            f"Access is restricted to '{mcp.jail_path}' and its subdirectories."
        )

    return resolved


# Mapping of command names to their required extensions for error hints
EXTENSION_HINTS: dict[str, str] = {
    "topic": "topic",
    "topics": "topic",
    "absorb": "absorb",
    "evolve": "evolve",
    "prune": "evolve",
    "fold": "evolve",
    "metaedit": "evolve",
    "split": "evolve",
    "uncommit": "evolve",
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
        "identify",
        "incoming",
        "log",
        "lfile",
        "lfiles",
        "outgoing",
        "parents",
        "paths",
        "phase",
        "resolve",
        "stack",
        "status",
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

_HEX_CHARS: frozenset[str] = frozenset("0123456789abcdefABCDEF")
_NULL_NODE: str = "0" * 40
_WDIR_NODE: str = "f" * 40


def _is_hex_node(value: object) -> bool:
    """Return True if value is a 40-character hexadecimal node hash."""
    return (
        isinstance(value, str)
        and len(value) == 40
        and all(ch in _HEX_CHARS for ch in value)
    )


def _is_git_dir(candidate: Path) -> bool:
    """Return True if candidate is a local Git working tree or bare Git repo."""
    try:
        if not candidate.is_dir():
            return False
        if (candidate / ".hg").exists():
            return False
        if (candidate / ".git").exists():
            return True
        return (
            (candidate / "HEAD").is_file()
            and (candidate / "objects").is_dir()
            and (candidate / "refs").is_dir()
        )
    except OSError:
        return False


def _is_git_remote_value(value: str) -> bool:
    """Return True if a configured remote path or URL points to a Git repository."""
    cleaned = value.strip()
    if not cleaned:
        return False

    lower = cleaned.lower()
    if (
        lower.startswith("git+")
        or lower.endswith(".git")
        or any(pattern in lower for pattern in GIT_REMOTE_PATTERNS)
    ):
        return True

    # SCP-style SSH remote such as git@host:org/repo
    if "://" not in lower and ":" in lower and lower.startswith("git@"):
        return True

    if lower.startswith("file://"):
        local_target = cleaned[len("file://") :]
    elif "://" in cleaned:
        return False
    else:
        local_target = cleaned

    return _is_git_dir(Path(local_target))


def _find_hg_dir(start_path: Path) -> Path | None:
    """Walk up from start_path to locate the repository's .hg directory."""
    try:
        current = start_path.absolute()
    except OSError:
        return None

    while True:
        hg_dir = current / ".hg"
        if hg_dir.is_dir():
            return hg_dir
        if current.parent == current:
            return None
        current = current.parent


def _resolve_store_hg_dir(hg_dir: Path) -> Path:
    """Resolve the shared repository source .hg directory if hg share is used."""
    sharedpath_file = hg_dir / "sharedpath"
    if not sharedpath_file.is_file():
        return hg_dir

    try:
        raw = sharedpath_file.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return hg_dir

    if not raw:
        return hg_dir

    shared = Path(raw)
    if shared.is_absolute():
        return shared if shared.is_dir() else hg_dir

    for base in (hg_dir, hg_dir.parent):
        candidate = (base / shared).resolve()
        if candidate.is_dir():
            return candidate
    return hg_dir


def _is_git_backed_repo(cwd: Path | None) -> tuple[bool, Path | None]:
    """Check whether cwd belongs to a Git-backed repo and return its mapfile path."""
    if cwd is None:
        return False, None

    hg_dir = _find_hg_dir(cwd)
    if hg_dir is None:
        return False, None

    store_hg_dir = _resolve_store_hg_dir(hg_dir)
    search_dirs = [store_hg_dir] if store_hg_dir == hg_dir else [store_hg_dir, hg_dir]

    mapfile: Path | None = None
    for candidate_dir in search_dirs:
        candidate_map = candidate_dir / "git-mapfile"
        if candidate_map.is_file():
            mapfile = candidate_map
            break

    for candidate_dir in search_dirs:
        if (
            (candidate_dir / "git-mapfile").is_file()
            or (candidate_dir / "git-branch").is_file()
            or (candidate_dir / "git-tags").is_file()
            or (candidate_dir / "git").is_dir()
        ):
            return True, mapfile

    for candidate_dir in search_dirs:
        hgrc_path = candidate_dir / "hgrc"
        if not hgrc_path.is_file():
            continue
        parser = configparser.RawConfigParser(allow_no_value=True)
        try:
            parser.read(hgrc_path, encoding="utf-8")
            if parser.has_section("paths"):
                for _, remote_val in parser.items("paths"):
                    if remote_val and _is_git_remote_value(remote_val):
                        return True, mapfile
        except (configparser.Error, OSError, UnicodeDecodeError):
            continue

    return False, None


def _load_git_mapfile(mapfile: Path | None) -> dict[str, str]:
    """Load hg-node -> git-node mapping from an hg-git git-mapfile."""
    mapping: dict[str, str] = {}
    if mapfile is None or not mapfile.is_file():
        return mapping

    try:
        with mapfile.open("r", encoding="utf-8", errors="replace") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) != 2:
                    continue
                git_sha, hg_sha = parts[0], parts[1]
                if _is_hex_node(git_sha) and _is_hex_node(hg_sha):
                    mapping[hg_sha.lower()] = git_sha.lower()
    except OSError:
        return {}

    return mapping


def _resolve_gitnode_for_item(
    item: dict[str, Any],
    git_map: dict[str, str],
    incoming_from_git: bool = False,
) -> str | None:
    """Resolve the companion 40-char gitnode hash for a JSON entry with 'node'."""
    node = item.get("node")
    if not isinstance(node, str):
        return None

    node_lower = node.lower()
    if node_lower == _NULL_NODE:
        return None

    # `hg identify` without -r reports working-dir virtual node ffff...;
    # resolve from its single parent commit when clean or dirty, else None.
    if node_lower == _WDIR_NODE:
        parents = item.get("parents")
        if isinstance(parents, list) and len(parents) == 1:
            parent = parents[0]
            if isinstance(parent, str):
                parent_lower = parent.lower()
                if parent_lower != _NULL_NODE and _is_hex_node(parent_lower):
                    return git_map.get(parent_lower)
        return None

    if not _is_hex_node(node_lower):
        return None

    # For `hg incoming` against a Git remote, hg-git's overlayrepo sets `node`
    # directly to the incoming Git SHA before pulling creates an hg node.
    if incoming_from_git:
        return node_lower

    return git_map.get(node_lower)


def _enrich_data_with_gitnode(
    data: object,
    git_map: dict[str, str],
    incoming_from_git: bool = False,
) -> None:
    """Add companion 'gitnode' field to JSON entries containing a 'node' field."""
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and "node" in item:
                item["gitnode"] = _resolve_gitnode_for_item(
                    item, git_map, incoming_from_git=incoming_from_git
                )
    elif isinstance(data, dict) and "node" in data:
        data["gitnode"] = _resolve_gitnode_for_item(
            data, git_map, incoming_from_git=incoming_from_git
        )


def _parse_hg_json_output(
    output: str, cmd: str
) -> tuple[object | None, str, str | None]:
    """Parse hg JSON output, stripping comparing/searching preambles if present."""
    try:
        return json.loads(output), "", None
    except json.JSONDecodeError:
        if cmd not in ("incoming", "outgoing"):
            return None, "", None

    comparing_target: str | None = None
    json_start_idx: int | None = None
    offset = 0
    for line in output.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith("comparing with "):
            comparing_target = stripped[len("comparing with ") :].strip()
        if stripped.startswith("["):
            json_start_idx = offset
            break
        offset += len(line)

    if json_start_idx is None:
        return None, "", None

    preamble = output[:json_start_idx]
    try:
        return json.loads(output[json_start_idx:]), preamble, comparing_target
    except json.JSONDecodeError:
        return None, "", None


def _format_json_output(output: str, cmd: str, cwd: Path | None) -> str:
    """Parse, enrich with gitnode if Git-backed, and minify hg JSON output."""
    data, preamble, comparing_target = _parse_hg_json_output(output, cmd)
    if data is None:
        return output

    is_git_backed, mapfile = _is_git_backed_repo(cwd)
    incoming_from_git = False
    if cmd == "incoming":
        incoming_from_git = bool(
            comparing_target and _is_git_remote_value(comparing_target)
        ) or (is_git_backed and "searching for changes" not in preamble.lower())

    if is_git_backed or incoming_from_git:
        git_map = _load_git_mapfile(mapfile)
        _enrich_data_with_gitnode(data, git_map, incoming_from_git=incoming_from_git)

    return json.dumps(data, separators=(",", ":"))


def sanitize_input(
    value: str,
    max_length: int = 1000,
    allow_shell_chars: bool = False,
) -> str:
    """Sanitize user input to prevent command injection and ensure valid values.

    Args:
        value: The string to sanitize
        max_length: Maximum allowed length for the input
        allow_shell_chars: If True, skips shell metacharacter checks (for messages)

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

    if allow_shell_chars:
        # For commit messages/descriptions: reject command substitution/expansion tokens
        dangerous_patterns = ["`", "$(", "${"]
    else:
        # For identifiers (branch, bookmark, tag, revision, file):
        # reject shell metacharacters
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
    is_extension_error = "unknown command" in error_text.lower() or (
        f"'{cmd}'" in error_text and "unknown" in error_text.lower()
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
        has_template = any(
            arg in ("-T", "--template", "-Tjson") or arg.startswith("--template=")
            for arg in args
        )
        if not has_template:
            is_json = True
            cmd_args = args + ["-T", "json"]
        else:
            cmd_args = args
            for idx, arg in enumerate(args):
                if arg in ("-T", "--template") and idx + 1 < len(args):
                    if args[idx + 1] == "json":
                        is_json = True
                elif arg.startswith("--template=") and arg.split("=", 1)[1] == "json":
                    is_json = True
                elif arg == "-Tjson":
                    is_json = True
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

        # Enrich with gitnode (if Git-backed) and minimize JSON output
        if is_json and output:
            output = _format_json_output(output, args[0], cwd)

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
        return [str(item) for item in param]
    if isinstance(param, str):
        cleaned = param.strip()
        if not cleaned:
            return default if default is not None else []
        if cleaned.startswith("[") and cleaned.endswith("]"):
            try:
                parsed: object = json.loads(cleaned)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed]
                return [cleaned]
            except json.JSONDecodeError:
                return [cleaned]
        return [cleaned]
    return default if default is not None else []  # type: ignore[unreachable]


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
                if isinstance(value, str) and _is_git_remote_value(value):
                    is_backed = True
                    remotes.append(f"  {name} = {value}")
        except (json.JSONDecodeError, TypeError):
            pass

    # Check for internal tracking files
    has_local_git, _ = _is_git_backed_repo(path)
    if has_local_git:
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
    """Sync Mercurial bookmarks to Git branches.

    Only applies if hg-git is enabled and repo is Git-backed.
    """
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
