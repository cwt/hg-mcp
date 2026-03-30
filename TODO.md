# HG-MCP TODO List

**Generated:** 2026-03-30  
**Based on:** Repository analysis and bug fixes #1-#3

---

## ✅ Completed

### Bug Fixes (v0.6.2)

- [x] **#1** - Memory leak in `hg_histedit()` - temp file not cleaned up (PR #4)
- [x] **#2** - Operator precedence bug in `_get_extension_hint()` (PR #5)
- [x] **#3** - Bare Exception catch in `hg_largefiles()` (PR #6)

---

## 📋 Missing Tools

### P0 - Critical (Should implement first)

| Tool | Description | Effort | Notes |
|------|-------------|--------|-------|
| `hg_amend` | Amend current commit (evolve extension) | Low | Mentioned in server instructions! |
| `hg_cat` | Show file content at revision | Low | Equivalent to `git show` |
| `hg_bookmark_create` | Create new bookmark | Low | Only list exists currently |

### P1 - High Priority

| Tool | Description | Effort | Notes |
|------|-------------|--------|-------|
| `hg_rename` / `hg_mv` | Rename/move files | Low | Like `git mv` |
| `hg_copy` | Copy files with history | Low | Track file ancestry |
| `hg_shelve` | Temporarily set aside changes | Medium | Like `git stash` |
| `hg_unshelve` | Restore shelved changes | Medium | Requires shelve extension |
| `hg_ignore` | Add pattern to .hgignore | Low | Common workflow |

### P2 - Medium Priority

| Tool | Description | Effort | Notes |
|------|-------------|--------|-------|
| `hg_grep` | Search commit history | Medium | Like `git log -S` |
| `hg_blame` | Alias for `hg_annotate` | Low | Git terminology |
| `hg_graph` | Show commit graph (`hg log -G`) | Low | Better UX |
| `hg_parents` | Show parent revisions | Low | JSON output |
| `hg_children` | Show child revisions | Low | JSON output |
| **Command timeout** | Add timeout to `run_hg_command()` | Medium | Reliability fix |
| **File validation** | Validate files exist in add/remove/annotate | Medium | Prevent silent failures |

### P3 - Nice to Have

| Tool | Description | Effort | Notes |
|------|-------------|--------|-------|
| `hg_archive` | Export repo to tarball/zip | Medium | Release snapshots |
| `hg_bundle` | Bundle changesets | Medium | Offline transfer |
| `hg_unbundle` | Apply bundle file | Low | Companion to bundle |
| `hg_ancestors` | List ancestor revisions | Low | Commit lineage |
| `hg_descendants` | List descendant revisions | Low | Forward history |
| `hg_debug` | Run hg debug commands | Low | Advanced diagnostics |
| `hg_stat` | Repository statistics | Low | Commits, branches, size |
| `hg_bisect` | Binary search for bugs | Medium | Bug hunting |
| `hg_phase` | Manage changeset phases | Medium | Draft/public/secret |

---

## 🔧 Missing Features

### Core Improvements

- [ ] **Command timeout protection** - Prevent hanging on long operations
- [ ] **File validation** - Check files exist before operations
- [ ] **Interactive mode support** - Better merge conflict handling
- [ ] **Batch operations** - Combine add+commit in one call
- [ ] **Pre-commit hooks validation** - Check hooks before committing

### hg-git Enhancements

- [ ] **`hg_gimport`** - Import Git branches after pull
- [ ] **`hg_gexport`** - Export bookmarks to Git (already called in commit, but could be standalone)
- [ ] **Bookmark suffix management** - Configure branch_bookmark_suffix
- [ ] **Git remote detection** - Auto-detect Git-backed repos in more tools

### Extension Support

- [ ] **Absorb extension** - `hg_absorb` for auto-amending into parents
- [ ] **Shelve extension** - Full shelve/unshelve support
- [ ] **Patchbomb extension** - Email patches
- [ ] **Revert extension** - Enhanced revert with revision support

---

## 📝 Documentation Improvements

- [ ] Add tool examples for each function
- [ ] Create workflow guides (Git users migrating to Mercurial)
- [ ] Add extension requirement badges in tool descriptions
- [ ] Create troubleshooting guide
- [ ] Add performance tuning guide (uvloop/winloop)

---

## 🧪 Testing Improvements

- [ ] Add tests for error conditions
- [ ] Add tests for invalid repo paths
- [ ] Add tests for malformed commands
- [ ] Add integration tests with real Git repos (hg-git)
- [ ] Add performance tests for large repositories

---

## 🐛 Known Issues / Technical Debt

- [ ] **JSON minification edge case** (Line 323) - Catches Exception silently
- [ ] **hg_tag() message** - Tag name not escaped in commit message
- [ ] **_get_git_branches()** - Assumes bookmarks are dicts, no validation
- [ ] **Inconsistent error messages** - Some use "Error:" prefix, some don't

---

## 📊 Tool Coverage Analysis

### Implemented: 41 tools

| Category | Count | Tools |
|----------|-------|-------|
| Core | 8 | status, log, diff, commit, add, remove, update, revert |
| Branching | 7 | branch, bookmarks, topic, topics, topic_current, tags, tag |
| Remote | 5 | push, pull, paths, incoming, outgoing |
| Merge | 3 | merge, resolve, backout |
| History Rewriting | 5 | rebase, strip, histedit, evolve, transplant |
| Inspection | 6 | annotate, files, summary, verify, identify, heads |
| Patches | 2 | export, import |
| hg-git | 1 | git |
| Help/Config | 4 | config, extensions, help, largefiles |

### Missing: 20+ tools

See "Missing Tools" section above for details.

---

## 🎯 Next Sprint Candidates

**Recommended for v0.7.0:**

1. `hg_amend` - Core modern workflow
2. `hg_cat` - Basic file viewing
3. `hg_bookmark_create` - Complete bookmark management
4. `hg_rename` - File move support
5. Command timeout - Reliability improvement

---

## 📈 Version History

- **v0.6.2** (2026-03-30) - Bug fixes #1, #2, #3
- **v0.6.1** - Previous release
- **v0.6.0** - Earlier release

---

## 📌 Notes

- Tools marked with "Low" effort can be implemented in < 50 lines of code
- Tools marked with "Medium" effort need 50-150 lines or complex logic
- Priority P0 tools are blockers for common workflows
- Priority P1 tools are frequently requested features
- Priority P2+ tools are enhancements or edge cases
