# Development Guide for hg-mcp

This document describes development conventions and best practices
for the hg-mcp MCP server.

## References

- **FastMCP Documentation**: <https://gofastmcp.com/>
- **FastMCP Tools Guide**:
  <https://gofastmcp.com/servers/tools>
- **FastMCP Dependencies & Parameter Reordering**:
  <https://gofastmcp.com/python-sdk/fastmcp-server-dependencies>
- **MCP Protocol Documentation**:
  <https://modelcontextprotocol.info/docs/concepts/tools/>
- **FastMCP GitHub**: <https://github.com/PrefectHQ/fastmcp>

## Tool Parameter Ordering

**CRITICAL**: All MCP tools must follow this parameter ordering convention:

1. **Required parameters** (without defaults) come FIRST
2. **`repo_path`** (with default value `"."`) comes next
3. **Optional parameters** (with defaults) come last

### Why This Matters

While FastMCP automatically reorders parameters (placing those without
defaults first), this project enforces a consistent position for
`repo_path` for:

- **MCP client compatibility**: Ensures consistent parameter ordering
  across all tools
- **Predictable schema generation**: MCP clients can rely on consistent
  parameter positions
- **Code consistency**: All tools follow the same pattern, making the
  codebase easier to maintain

### FastMCP's Default Behavior

According to the
[FastMCP documentation](https://gofastmcp.com/python-sdk/fastmcp-server-dependencies):

> **Note: Only POSITIONAL_OR_KEYWORD parameters are reordered (params with
> defaults after those without). KEYWORD_ONLY parameters keep their
> position since Python allows them to have defaults in any order.**

This means FastMCP will automatically reorder parameters, but we enforce
`repo_path` position for consistency.

### Reference

This convention was established in **changeset 12**
(`c3686dee2c7f`), which fixed parameter ordering in:
`hg_revert`, `hg_branch`, `hg_rebase`, `hg_histedit`,
`hg_merge`, `hg_push`, `hg_pull`, `hg_help`

### Examples

**✓ CORRECT:**

```python
@mcp.tool()
@handle_repo_errors
async def hg_tag(
    name: str,                 # 1. Required param (no default) comes FIRST
    repo_path: str = ".",      # 2. repo_path after required params
    revision: str = "",        # 3. Optional params last
    remove: bool = False,
) -> str:
    # name is required - no validation needed since Python enforces it
    # ...
```bash

```python
@mcp.tool()
@handle_repo_errors
async def hg_commit(
    message: str,              # 1. Required param (no default) comes FIRST
    repo_path: str = ".",      # 2. repo_path after required params
    files: Optional[List[str]] = None,  # 3. Optional param last
) -> str:
    # ...
```bash

```python
@mcp.tool()
@handle_repo_errors
async def hg_status(repo_path: str = ".") -> str:
    # Only repo_path - simplest case
    # ...
```bash

```python
@mcp.tool()
@handle_repo_errors
async def hg_add(
    files: List[str],          # 1. Required param (no default) comes FIRST
    repo_path: str = ".",      # 2. repo_path after required params
) -> str:
    # ...
```bash

```python
@mcp.tool()
@handle_repo_errors
async def hg_strip(
    revision: str,             # 1. Required param (no default) comes FIRST
    repo_path: str = ".",      # 2. repo_path after required params
    keep: bool = False,        # 3. Optional param last
) -> str:
    # ...
```bash

**✗ INCORRECT:**

```python
# WRONG: repo_path is not first (when there are no required params)
async def hg_tag(
    name: str,
    repo_path: str = ".",
    revision: str = "",
    remove: bool = False,
) -> str:
```bash

```python
# WRONG: repo_path is in the middle of optional params
async def hg_rebase(
    source: str = "",
    repo_path: str = ".",      # Should be before optional params!
    dest: str = "",
    collapse: bool = False,
) -> str:
```bash

```python
# WRONG: optional param 'keep' comes before repo_path
async def hg_strip(
    revision: str,
    keep: bool = False,        # Optional param should come AFTER repo_path
    repo_path: str = ".",
) -> str:
```bash

```python
# WRONG: optional param 'source' comes before repo_path
async def hg_transplant(
    revisions: List[str],
    source: str = "",          # Optional param should come AFTER repo_path
    repo_path: str = ".",
) -> str:
```bash

### Quick Reference Table

<!-- markdownlint-disable MD013 -->
|  Pattern | Order | Example  |
| ---------|-------|--------- |
|  Only `repo_path` | `repo_path` | `hg_status(repo_path)`  |
|  Required + `repo_path` | `required`, `repo_path` | `hg_add(files, repo_path)`  |
|  `repo_path` + Optional | `repo_path`, `optional` | `hg_revert(repo_path, files)`  |
|  Required + `repo_path` + Optional | `required`, `repo_path`, `optional` | `hg_commit(message, repo_path, files)`  |
|  Required + `repo_path` + Multiple Optional | `required`, `repo_path`, `optional...` | `hg_tag(name, repo_path, revision, remove)`  |
<!-- markdownlint-enable MD013 -->

## Adding New Tools

When adding a new MCP tool:

1. **Use the `@mcp.tool()` decorator**
2. **Apply `@handle_repo_errors` decorator** for repository operations
3. **Follow parameter ordering**: `repo_path` first, then required params,
   then optional params
4. **Validate `repo_path`** using `validate_repo_path(repo_path)`
5. **Use `run_hg_command()`** to execute Mercurial commands
6. **Add JSON output support** where appropriate
   (add to `JSON_SUPPORTED_COMMANDS` set)
7. **Update README.md** to document the new tool
8. **Update MCP server instructions** in `main.py` if the tool needs
   special usage notes

## Code Quality

Before committing changes, always run the following scripts in order:

```bash
# 1. Run linting and auto-fix issues
./scripts/lint-check-and-fix.sh

# 2. Run type checking
./scripts/type-check.sh

# 3. Fix all linting and typing errors manually
# (Edit files to resolve any remaining errors from steps 1-2)

# 4. Format code before final commit
./scripts/code-format.sh
```bash

**All linting and type checking errors must be fixed before committing.**

### Script Details

<!-- markdownlint-disable MD013 -->
|  Script | Description  |
| --------|------------- |
|  `lint-check-and-fix.sh` | Runs `ruff check --fix` to lint and auto-fix issues  |
|  `type-check.sh` | Runs `mypy` for static type checking  |
|  `code-format.sh` | Runs `black` formatter and removes trailing whitespace  |
<!-- markdownlint-enable MD013 -->

## Testing New Tools

### Test Repository Location (RAM-backed for Speed)

All test repositories are created in the fastest available RAM-backed
storage for each platform:

<!-- markdownlint-disable MD013 -->
|  Platform | Location | Speed | Notes  |
| ----------|----------|-------|------- |
|  **Linux** | `/dev/shm` (tmpfs) | ~10-100x faster (RAM-backed) | Built-in, no setup needed  |
|  **macOS** | `/tmp` (APFS) | Standard disk speed | No native tmpfs by default  |
|  **WSL** | `/dev/shm` (tmpfs) | ~10-100x faster (RAM-backed) | Inherits from Linux kernel  |
<!-- markdownlint-enable MD013 -->

**macOS users:** You can manually set up tmpfs for faster tests:

```bash
# Option 1: Create tmpfs mount (requires sudo)
sudo mount_tmpfs tmpfs /tmpfs -o size=2g
export TMPDIR=/tmpfs

# Option 2: Create RAM disk (requires sudo)
diskutil erasevolume HFS+ "RAMDisk" $(hdiutil attach -nomount ram://4194304)
export TMPDIR=/Volumes/RAMDisk
```bash

This provides:

- **Automatic platform detection** - no configuration needed
- **RAM-backed storage on Linux/WSL** - maximum speed
- **Graceful fallback on macOS** - works everywhere
- **Automatic cleanup** when tests complete (TemporaryDirectory)
- **Isolated repositories** for each test fixture

To verify tests are running on tmpfs (Linux):

```bash
# Check if /dev/shm is available and on tmpfs
df -h /dev/shm

# During test execution, verify temp dirs are created there
ls -la /dev/shm/tmp*
```bash

### Running Tests

Test new tools using the pytest test suite:

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_core_tools.py

# Run specific test class
pytest tests/test_core_tools.py::TestHgAmend

# Run specific test function
pytest tests/test_core_tools.py::TestHgAmend::test_amend_without_message

# Run with verbose output
pytest -v

# Run with coverage report
pytest --cov=hg_mcp --cov-report=term-missing
```bash

### Test Fixtures

The following fixtures are available in `tests/conftest.py`:

<!-- markdownlint-disable MD013 -->
|  Fixture | Description  |
| ---------|------------- |
|  `temp_dir` | Temporary directory in /dev/shm  |
|  `hg_repo` | Isolated repo with NO extensions  |
|  `hg_repo_with_commits` | Repo with 5 sample commits  |
|  `hg_repo_with_extensions` | Repo with configurable extensions  |
|  `hg_repo_with_branches` | Repo with feature branch  |
|  `hg_repo_with_bookmarks` | Repo with bookmarks  |
|  `hg_repo_with_tags` | Repo with tags  |
|  `hg_repo_with_remote` | Repo with remote configured  |
<!-- markdownlint-enable MD013 -->

### Manual Testing

Test new tools manually using the MCP client or by calling them directly
in a Python REPL:

```python
# Example: Test hg_tags tool
from hg_mcp.main import hg_tags
import asyncio

result = asyncio.run(hg_tags("."))
print(result)
```bash

## Commit Messages

Follow conventional commit format:

```bash
<type>: <description>

[Optional body with more details]

Tools added/modified: <list of tools>
```bash

Examples:

- `feat: Add hg_tag tool for creating and removing tags`
- `fix: Correct parameter ordering in hg_revert tool`
- `docs: Update README with new tool documentation`

## Release Process

**Important**: When tagging a new version, always update `pyproject.toml`
first and commit it before creating the tag. This ensures the tag
includes the correct version number.

### Workflow

```bash
# 1. Update version in pyproject.toml
# Edit pyproject.toml and change the version field:
# version = "X.Y.Z"

# 2. Commit the version change FIRST
hg commit pyproject.toml -m "chore: Bump version to vX.Y.Z"

# 3. Create the tag (it will include the version commit)
hg tag -m "Release vX.Y.Z" vX.Y.Z

# 4. Build and publish to PyPI (if applicable)
```bash

### Why This Order Matters

- The tag should point to a commit that includes the version update in
  `pyproject.toml`
- This ensures that checking out a tagged version always has the correct
  version number in the source
- Makes it easier to verify which version corresponds to which tag
