# TODO - v0.8.x Development

## v0.8.1 Status (Current)

**Version:** v0.8.1 - Stable release with all v0.7.x lessons learned applied

### Completed from v0.7.x

#### Lessons Learned - Applied ✓

- [x] **Type annotation pattern** - All `@json_tool` functions return `-> list[TextContent]` with `# type: ignore[return-value]`
- [x] **Tool registration** - All 41 tools have `@mcp.tool()` and are imported in `main.py`
- [x] **Verification step** - Tool registration verified: `from hg_mcp.main import mcp; print(len(mcp._tool_manager._tools))`

#### Code Quality Improvements - Applied ✓

- [x] **Modular structure** - Clean separation: decorators, helpers, server, tools/*
- [x] **Faster tests** - Tmpfs on Linux (`/dev/shm/hg-mcp-tests-{uid}/`) with user-specific directories
- [x] **Test organization** - Tests by functionality (core, extension, availability)
- [x] **`_is_json_tool` marker** - Reliable decorator detection in `handle_repo_errors`

### Code Quality Rules for v0.8.x

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
    @functools.wraps(func)
    async def wrapper(...) -> list[TextContent]:
        ...
    wrapper._is_json_tool = True  # type: ignore[attr-defined]
    return wrapper
```

```python
def handle_repo_errors(func):
    """Handles ValueError from validate_repo_path."""
    # Checks for _is_json_tool marker attribute
    is_json_tool = getattr(func, "_is_json_tool", False)
    # Returns errors as list[TextContent] if @json_tool, else str
```

---

## v0.8.0 Goals - COMPLETED ✓

1. **Stability** - No breaking changes to working patterns ✓
2. **Documentation** - Clear comments explaining why patterns exist ✓
3. **Testing** - Verify all tools work after any refactoring ✓
4. **Code quality** - Maintain clean lint/type-check/format ✓

---

## Architecture Notes

### Tool Registration Flow

```text
hg_mcp/main.py
  ├── imports hg_mcp.server.mcp
  ├── imports all tools from hg_mcp.tools.*  ← Registers @mcp.tool()
  └── calls mcp.run(transport="stdio")
```

**Critical:** Tools must be imported in `main.py` for decorators to execute and register with FastMCP.

### Module Structure

```text
hg_mcp/
├── main.py          # Entry point, imports & registers all tools
├── server.py        # FastMCP instance with instructions
├── decorators.py    # @json_tool, @handle_repo_errors
├── helpers.py       # run_hg_command, validate_repo_path, etc.
└── tools/
    ├── __init__.py  # Exports all tools
    ├── core.py      # status, log, diff, commit, add, remove, update, revert
    ├── branching.py # bookmarks, branch, tags, topic, topics, push, pull, etc.
    ├── history.py   # annotate, backout, export, import, heads, incoming, etc.
    ├── merge.py     # merge, resolve
    └── hggit.py     # git detection, rebase, strip, transplant, evolve
```

---

## Reference

- **v0.6.2**: Last known stable version (baseline for v0.8.0)
- **v0.7.0-v0.7.3**: Development cycle with good ideas but some broken patterns
- **v0.8.0**: Fresh start from v0.6.2 with all v0.7.x lessons applied
- **v0.8.1**: Fixed tool registration bug (main.py now imports all tools)
- **backup-0.7.x**: Bookmark preserving v0.7.x code for reference
