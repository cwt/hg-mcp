# TODO - v0.9.x Development

## v0.9.2 Status (Current)

**Version:** v0.9.2 — 62 tools covering Mercurial 7.1.x operations | Coverage: 87%

---

## Missing Mercurial 7.1.x Features

Analysis of standard commands and built-in extensions (enabled/disabled) not yet exposed as MCP tools.

### High Priority

| Command | Source | Description |
|---|---|---|
| `clone` | standard | Copy a repository | [x] |
| `bisect` | standard | Binary search for regression-introducing changeset | [x] |
| `graft` | standard | Copy changesets (merge-based cherry-pick, safer than transplant) | [x] |
| `phases` | standard | Show/set changeset phases (draft/public/secret) | [x] |
| `absorb` | evolve | Auto-amend uncommitted changes into prior commits | [x] |
| `fold` | evolve | Combine multiple changesets into one | [x] |
| `split` | evolve | Split a changeset into multiple smaller ones | [x] |
| `uncommit` | evolve | Uncommit part of a changeset (move to working dir) | [x] |
| `next` | evolve | Move to next changeset in topic stack | [x] |
| `previous` | evolve | Move to previous changeset in topic stack | [x] |
| `rewind` | evolve | Recreate changesets that were pruned/evolved (undo) | [x] |
| `metaedit` | evolve | Edit commit metadata (message, user, date, branch) | [x] |
| `stack` | evolve | Show the current topic stack | [x] |
| `prune` | evolve | Mark changesets as obsolete (history cleanup) | [x] |
| `shelve` | shelve | Temporarily stash uncommitted changes | [x] |
| `unshelve` | shelve | Restore previously shelved changes | [x] |

### Medium Priority

| Command | Source | Description |
|---|---|---|
| `addremove` | standard | Auto-add new files, forget deleted ones |
| `copy` | standard | Mark files as copied (keeps original, unlike rename) |
| `forget` | standard | Stop tracking files without deleting them |
| `grep` | standard | Search for patterns in tracked files |
| `fixup` | evolve | Amend a working commit to the specified parent |
| `obslog` | evolve | Show obsolescence history of a changeset |
| `pick` | evolve | Pick a changeset on top of working directory |
| `touch` | evolve | Revive an obsolete changeset (makes it current) |
| `tstack` | topic | Show topic stack (graph view) |
| `tstatus` | topic | Show status relative to topic base |
| `git-cleanup` | hggit | Clean up stale Git bookmarks/internals |
| `purge` | purge | Delete untracked files from working directory |

### Low Priority

| Command | Source | Description |
|---|---|---|
| `archive` | standard | Create unversioned tarball/zip of repo |
| `bundle` | standard | Create a changegroup file (offline transfer) |
| `unbundle` | standard | Apply a changegroup file |
| `manifest` | standard | Show file manifest of a revision |
| `recover` | standard | Roll back an interrupted transaction |
| `root` | standard | Print repository root directory |
| `churn` | churn | Commit activity statistics |
| `convert` | convert | Import from foreign VCS |
| `lfconvert` | largefiles | Convert repo to largefiles |
| `lfpull` | largefiles | Pull largefiles without pulling history |
| `git-verify` | hggit | Verify integrity of Git-backed data |
| `change` | topic | Change topic name on existing revisions |
| `pstatus` | evolve | Status relative to predecessor |
| `pdiff` | evolve | Diff relative to predecessor |

### Not Planned

| Command | Reason |
|---|---|
| `serve` | Not useful in MCP context |
| `version` | Not useful in MCP context |
| `gpg` | Niche signing operations |
| `closehead` | Rarely needed |

---

## v0.8.2 Status (Previous)

**Version:** v0.8.2 - Added missing tools with input sanitization

### New Tools Added

- [x] **hg_bookmark** - Show/create bookmarks with hg-git gexport integration
- [x] **hg_amend** - Amend current commit with hg-git gexport integration
- [x] **hg_cat** - Show file content at specific revision
- [x] **hg_rename** - Rename/move files (hg mv equivalent)

### Security Improvements

- [x] **sanitize_input()** - New helper to prevent command injection
- [x] **Input validation** - Applied to bookmark names, revisions, commit messages, file paths
- [x] **Dangerous pattern detection** - Rejects shell metacharacters: `$(`, `${`, `|`, `;`, `&&`, `||`, `>`, `<`, `&`

### Test Coverage Added

- [x] **test_new_tools.py** - Comprehensive tests for new tools (457 lines)
- [x] **test_branching_tools.py** - Tests for bookmark, branch, tag, push, pull
- [x] **test_merge_helpers.py** - Tests for run_hg_command with JSON output
- [x] **test_hggit_tools.py** - Tests for hg-git integration tools
- [x] **test_main.py** - Basic server functionality tests

### Documentation Updated

- [x] **server.py** - Instructions updated with all new tools
- [x] **README.md** - Tool list updated
- [x] **DEVELOPMENT.md** - Reference updated

---

## v0.8.1 Status

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
