# TODO - v0.8.0 Development

## Lessons Learned from v0.7.x

### What Went Wrong

#### 1. Type Annotation Mismatch with `@json_tool` Decorator

**Problem:** Changed return type annotations from `-> list[TextContent]` to `-> str` for functions decorated with `@json_tool`.

**Why it failed:** FastMCP validates tool return types against annotations. The `@json_tool` decorator wraps `str` results in `list[TextContent]`, but the annotation said `-> str`, causing validation errors.

**Correct Pattern (v0.6.2):**
```python
@mcp.tool()
@json_tool
@handle_repo_errors
async def hg_status(repo_path: str = ".") -> list[TextContent]:
    """Show the status of files in the working directory."""
    path = validate_repo_path(repo_path)
    return await run_hg_command(["status"], cwd=path)  # type: ignore[return-value]
```

**Key Points:**
- Return type annotation documents what **MCP receives** (after decoration): `list[TextContent]`
- The `# type: ignore[return-value]` comment is **necessary and correct**
- The decorator's job is to transform `str` → `list[TextContent]`
- Don't try to be "clever" with type annotations - follow the working pattern

#### 2. Refactoring Without Proper Testing

**Problem:** v0.7.2 refactored main.py into submodules but forgot to add `@mcp.tool()` decorators, resulting in zero tools registered.

**Lesson:** Always verify tool registration after refactoring:
```python
from hg_mcp.server import mcp
print(f"Tools registered: {len(mcp._tool_manager._tools)}")
```

---

## Features from v0.7.x to Preserve

### Code Quality Improvements (v0.7.3)

- [x] **Input sanitization** - `sanitize_input()` function for defense-in-depth
- [x] **Better error handling** - hg-git integration wrapped in try-except
- [x] **Temp file cleanup** - `hg_histedit` uses try-finally for guaranteed cleanup
- [x] **Logging** - Added `logger.exception()` for debugging unexpected errors
- [x] **Timeout race condition fix** - Catch `ProcessLookupError` in `run_hg_command`

### Code Organization (v0.7.2)

- [x] **Modular structure** - Split into submodules by functionality:
  - `hg_mcp/decorators.py` - Decorators
  - `hg_mcp/helpers.py` - Helper functions
  - `hg_mcp/server.py` - MCP server instance
  - `hg_mcp/tools/*.py` - Tool modules by category

### Test Improvements

- [x] **Faster tests** - Use `/dev/shm` (tmpfs) on Linux for ~10-100x speedup
- [x] **Better organization** - Tests organized by functionality, not version

---

## Code Quality Rules for v0.8.0

### Before Every Commit

```bash
# 1. Lint check
./scripts/lint-check-and-fix.sh

# 2. Type check
./scripts/type-check.sh

# 3. Code format
./scripts/code-format.sh

# 4. Run tests
pytest
```

### Type Annotation Rules

1. **Functions with `@json_tool`:**
   - Return type: `-> list[TextContent]`
   - Add `# type: ignore[return-value]` comment
   - This documents what MCP receives after decoration

2. **Functions without `@json_tool`:**
   - Return type: `-> str`
   - No ignore comment needed

3. **Never change working patterns** without verifying with FastMCP first

### Decorator Pattern

```python
def json_tool(func):
    """Wraps str in TextContent(audience=['assistant'])."""
    # Returns: list[TextContent]
```

```python
def handle_repo_errors(func):
    """Handles ValueError from validate_repo_path."""
    # Checks for _is_json_tool marker attribute
    # Returns errors as list[TextContent] if @json_tool, else str
```

---

## v0.8.0 Goals

1. **Stability** - No breaking changes to working patterns
2. **Documentation** - Clear comments explaining why patterns exist
3. **Testing** - Verify all tools work after any refactoring
4. **Code quality** - Maintain clean lint/type-check/format

---

## Reference

- **v0.6.2**: Last known stable version (baseline for v0.8.0)
- **v0.7.0-v0.7.3**: Development cycle with good ideas but some broken patterns
- **backup-0.7.x**: Bookmark preserving v0.7.x code for reference
