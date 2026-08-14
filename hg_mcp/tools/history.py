"""History and inspection tools.

Provides tools for viewing commit history, repository state, and integrity.
"""

from pathlib import Path

from mcp.types import TextContent

from hg_mcp.decorators import handle_repo_errors, json_tool
from hg_mcp.helpers import (
    format_bytes,
    parse_list_param,
    run_hg_command,
    sanitize_input,
    validate_repo_path,
)
from hg_mcp.server import mcp


@mcp.tool()
@handle_repo_errors
async def hg_bisect(
    repo_path: str = ".",
    command: str = "",
    revision: str = "",
    extend: bool = False,
) -> str:
    """Binary search for a regression-introducing changeset.

    Equivalent to 'git bisect'. Helps find the changeset that
    introduced a bug by marking revisions as good or bad.

    Usage workflow:
    1. hg_bisect(command="reset") - Reset any previous bisect
    2. hg_bisect(command="bad", revision="tip") - Mark current as bad
    3. hg_bisect(command="good", revision="42") - Mark a known good revision
    4. Test the revision Mercurial updates to
    5. hg_bisect(command="good") or hg_bisect(command="bad") - Mark result
    6. Repeat steps 4-5 until the culprit is found
    7. hg_bisect(command="reset") - End bisection

    Args:
        repo_path: The repository path
        command: Bisect action - "reset", "good", "bad", "skip", or "" for status
        revision: Revision to mark (optional; uses current if omitted)
        extend: If True, extend bisect range beyond current changeset

    Examples:
        - hg_bisect() -> Show current bisect status
        - hg_bisect(command="reset") -> Reset bisect state
        - hg_bisect(command="bad", revision="tip") -> Mark tip as bad
        - hg_bisect(command="good", revision="100") -> Mark r100 as good
    """
    path = validate_repo_path(repo_path)
    args = ["bisect"]

    cmd = command.strip().lower()
    if cmd in ("reset", "good", "bad", "skip"):
        args.extend(["--" + cmd])
        if revision:
            try:
                safe_revision = sanitize_input(revision, max_length=200)
            except ValueError as e:
                return f"Error: Invalid revision - {e}"
            args.append(safe_revision)

    if extend:
        args.append("--extend")

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

    # Sanitize revision
    try:
        safe_revision = sanitize_input(revision, max_length=200)
    except ValueError as e:
        return f"Error: Invalid revision - {e}"

    args = ["backout"]
    if merge:
        args.append("--merge")
        if message:
            try:
                safe_message = sanitize_input(
                    message, max_length=10000, allow_shell_chars=True
                )
            except ValueError as e:
                return f"Error: Invalid commit message - {e}"
            args.extend(["-m", safe_message])

        else:
            # Default message to avoid interactive editor
            args.extend(["-m", f"Backed out changeset {safe_revision}"])
    else:
        # Don't commit, just prepare the backout
        args.append("--no-commit")
    args.append(safe_revision)
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
        try:
            safe_output = sanitize_input(output, max_length=500)
        except ValueError as e:
            return f"Error: Invalid output path - {e}"
        args.extend(["-o", safe_output])
    revisions_list = parse_list_param(revisions)
    for rev in revisions_list:
        try:
            safe_rev = sanitize_input(rev, max_length=200)
        except ValueError as e:
            return f"Error: Invalid revision - {e}"
        args.append(safe_rev)
    return await run_hg_command(args, cwd=path)


@mcp.tool()
@handle_repo_errors
async def hg_import(
    patches: list[str] | str,
    repo_path: str = ".",
    no_commit: bool = False,
) -> str:
    """Import an ordered set of patches.

    Applies patch files to the working directory. Can optionally commit
    automatically if the patch includes proper header information.

    Args:
        patches: List of patch file paths to import
        repo_path: The repository path
        no_commit: If True, only apply patches without committing
    """
    path = validate_repo_path(repo_path)
    args = ["import"]
    if no_commit:
        args.append("--no-commit")
    patches_list = parse_list_param(patches)
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
    repo_path: str = ".",
    source: str = "",
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
    repo_path: str = ".",
    destination: str = "",
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
    repo_path: str = ".",
    revision: str = "",
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
    - 'mess' - reword commit message (keeps original in non-interactive mode)
    - 'fold' - combine with preceding changeset (keeps combined messages)
    - 'roll' - like fold, but discard this commit's description
    - 'edit' - pause at this changeset for manual edits
    - 'base' - checkout changeset and apply further changesets from there

    Note: In non-interactive mode, 'mess' commands will keep the original
    commit message, and 'fold' will use the default combined message.

    Args:
        repo_path: The repository path
        revision: First revision to be edited (ancestor)
        commands: Commands file path or inline commands
            (e.g., "pick abc123\\ndrop def456")
    """
    import tempfile

    path = validate_repo_path(repo_path)
    args = ["histedit", "--noninteractive"]

    # Track temp files for cleanup
    commands_file_exists = False
    commands_file = ""
    editor_script = None

    if revision:
        args.extend(["-r", revision])

    # Support inline commands by creating a temp file
    if commands:
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
                commands_file_exists = True
            args.extend(["--commands", commands_file])

            # Check if we need a non-interactive editor for mess/fold commands
            has_mess_or_fold = any(
                line.strip().startswith(("mess ", "fold ", "m ", "f "))
                for line in commands.split("\n")
                if line.strip() and not line.startswith("#")
            )
            if has_mess_or_fold:
                # Create a temp editor script that keeps the original message
                # by copying stdin to the file (non-interactive)
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".sh", prefix="hg_mcp_editor_", delete=False
                ) as ef:
                    ef.write(
                        "#!/bin/sh\n# Non-interactive editor for histedit\n"
                        "# Keeps the original message by doing nothing\n"
                        "exit 0\n"
                    )
                    editor_script = Path(ef.name)
                editor_script.chmod(0o755)
        else:
            # File path
            args.extend(["--commands", commands])

    # Prepare environment with non-interactive editor if needed
    env = None
    if editor_script and editor_script.exists():
        env = {"EDITOR": str(editor_script), "VISUAL": str(editor_script)}

    try:
        result = await run_hg_command(args, cwd=path, env=env)
    finally:
        # Clean up temp files
        if commands_file_exists and commands_file:
            try:
                Path(commands_file).unlink(missing_ok=True)
            except Exception:
                pass

        # Clean up editor script
        if editor_script is not None:
            try:
                editor_script.unlink(missing_ok=True)
            except Exception:
                pass

    return result


@mcp.tool()
@handle_repo_errors
@json_tool
async def hg_largefiles(repo_path: str = ".") -> list[TextContent]:
    """Show large files tracked by the largefiles extension."""
    path = validate_repo_path(repo_path)
    hglf_path = path / ".hglf"

    if not hglf_path.is_dir():
        msg = "No largefiles found in this repository."
        return [TextContent(type="text", text=msg)]

    largefiles = []
    try:
        import os

        for root, dirs, files in os.walk(str(hglf_path)):
            for filename in files:
                if filename == "__MACOSX":
                    continue

                file_path = Path(root) / filename
                rel_path = str(file_path.relative_to(hglf_path))

                size = 0
                working_copy_file = path / rel_path
                if working_copy_file.is_file():
                    try:
                        size = working_copy_file.stat().st_size
                    except OSError:
                        size = 0

                if size == 0:
                    try:
                        content = file_path.read_text(encoding="utf-8").strip()
                        lines = content.split("\n")
                        if len(lines) >= 2 and lines[1].isdigit():
                            size = int(lines[1])
                    except (ValueError, UnicodeDecodeError, OSError):
                        size = 0

                largefiles.append((rel_path, size))

    except Exception as e:
        msg = f"Error reading largefiles: {e}"
        return [TextContent(type="text", text=msg)]

    if not largefiles:
        msg = "No largefiles found in this repository."
        return [TextContent(type="text", text=msg)]

    def _get_largefile_size(item: tuple[str, int]) -> int:
        return item[1]

    largefiles.sort(key=_get_largefile_size, reverse=True)

    lines = ["Largefiles in repository:", "-" * 50]
    for filename, size in largefiles:
        lines.append(f"  {filename}: {format_bytes(size)}")

    return [TextContent(type="text", text="\n".join(lines))]
