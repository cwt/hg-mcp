# HG MCP Server

[![PyPI Version](https://img.shields.io/pypi/v/hg-mcp.svg)](https://pypi.org/project/hg-mcp/)

A Model Context Protocol (MCP) server for Mercurial repository interaction, written in Python 3.10+ with AsyncIO.

## Features

### Core Version Control Operations

- **Status & Diff**: View working directory status and uncommitted changes (equivalent to `git status` and `git diff`)
- **Commit Management**: Add files, commit changes with messages, and remove files from version control
- **History Navigation**: View commit history with configurable limits, update to any revision (like `git checkout`/`git switch`)
- **Branch Management**: Create, list, and switch between branches; supports both permanent branches and lightweight bookmarks

### Advanced Branching with Topics

- **Topic Support**: Create and manage lightweight branches (topics) using the evolve extension
- **Topic Tracking**: List all topics and identify the currently active topic
- **Bookmark Integration**: Seamless bookmark management for Git-like branch workflows

### Remote Synchronization

- **Push/Pull**: Push changes to remote repositories and pull from remote sources
- **Remote Configuration**: Support for named remotes and direct URLs

### History Rewriting (Requires Extensions)

- **Rebase**: Move or combine changesets onto different revisions (like `git rebase`)
- **Strip**: Permanently remove changesets (like `git reset --hard`)
- **Histedit**: Interactive history editing (like `git rebase -i`)
- **Transplant**: Cherry-pick changesets from other branches (like `git cherry-pick`)
- **Evolve**: Track how changesets have been rewritten over time

### Merge & Conflict Resolution

- **Merge**: Combine changes from different branches
- **Conflict Management**: List and track files with unresolved merge conflicts
- **Revert**: Discard uncommitted changes and restore files to last committed state

### Large File Support

- **Largefiles Extension**: List and manage large files stored outside normal history with size information

### Git Integration (hg-git)

- **Git Remote Detection**: Automatically detect if repository is Git-backed
- **Branch Mapping**: View how bookmarks map to Git branches
- **Configuration Insights**: Display hg-git settings and branch bookmark suffix configuration

### Configuration & Diagnostics

- **Extension Detection**: List all enabled Mercurial extensions
- **Repository Validation**: Verify Mercurial repository status and configuration
- **Built-in Help**: Access Mercurial command documentation and concepts

### Performance & Reliability

- **Async I/O**: Asynchronous command execution for responsive operations
- **JSON Output Support**: Automatic JSON formatting for supported commands (`status`, `log`, `bookmarks`, `topics`, `config`, `resolve`, `tags`, `heads`, `id`, `parents`, `children`, `outgoing`, `incoming`)
- **Optional Performance Boost**: Support for uvloop (Unix/macOS) and winloop (Windows) for enhanced performance
- **Smart Error Handling**: Helpful error messages with hints for missing extensions
- **Path Validation**: Automatic repository detection even when working in subdirectories

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd hg-mcp

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in editable mode
pip install -e .

# Optional: Install with performance enhancements
pip install uvloop  # On Unix/macOS
pip install winloop  # On Windows
```

## Usage

```bash
# Activate your virtual environment first
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
hg-mcp
```

This starts the MCP server that can be used with MCP clients like Claude for Desktop, Qwen-Coder, Gemini-CLI, and OpenCode.

## Tools

### Core Commands

- `hg_status`: Show working directory status with JSON output (like `git status`)
- `hg_log`: Show commit history with JSON output (like `git log`)
- `hg_diff`: Show uncommitted changes (like `git diff`)
- `hg_commit`: Commit changes with a message (like `git commit`)
- `hg_add`: Add files to version control (like `git add`)
- `hg_remove`: Remove files (like `git rm`)

### Branch & Navigation

- `hg_update`: Update to a revision (like `git checkout`/`git switch`)
- `hg_branch`: Show or create branches
- `hg_bookmarks`: List bookmarks with JSON output (lightweight branches, like Git branches in hg-git)
- `hg_topic`: Create a topic (lightweight branch)
- `hg_topics`: List all topics with JSON output
- `hg_topic_current`: Show current topic (JSON-parsed)

### Remote Sync

- `hg_push`: Push changes to remote (like `git push`)
- `hg_pull`: Pull changes from remote (like `git fetch`)

### History Rewriting (Extensions Required)

- `hg_rebase`: Rebase changesets (like `git rebase`, requires 'rebase' extension)
- `hg_strip`: Remove changesets (like `git reset --hard`, requires 'strip' extension)
- `hg_histedit`: Interactive history editing (like `git rebase -i`, requires 'histedit')
- `hg_evolve`: Show evolution history (requires 'evolve' extension)
- `hg_transplant`: Cherry-pick changesets (like `git cherry-pick`, requires 'transplant')

### Merge & Conflict Resolution

- `hg_merge`: Merge branches (like `git merge`)
- `hg_resolve`: List merge conflicts with JSON output
- `hg_revert`: Discard uncommitted changes (like `git checkout --` / `git restore`)

### Large Files

- `hg_largefiles`: List large files (requires 'largefiles' extension)

### Configuration & Help

- `hg_config`: Show Mercurial configuration with JSON output (check for hg-git extension)
- `hg_extensions`: List enabled extensions
- `hg_git`: Check hg-git extension status and Git remote configuration
- `hg_help`: Get help on Mercurial commands and concepts
- `hg_paths`: List configured paths/remotes with JSON output
- `hg_tags`: List tags with JSON output
- `hg_heads`: List heads with JSON output
- `hg_id`: Show current revision ID with JSON output
- `hg_parents`: Show parent revisions with JSON output
- `hg_children`: Show child revisions with JSON output

## Integration with AI Assistants

To use this MCP server with your AI coding assistant, you need to configure it in your assistant's MCP settings. The key is pointing to the correct executable path in your virtual environment.

### Step 1: Find Your Virtual Environment Path

First, determine where your virtual environment is located:

**If using Poetry:**

```bash
# Get the virtual environment path
poetry env info --path
# Example output: /home/user/.cache/pypoetry/virtualenvs/hg-mcp-xxxxx-py3.10
```

**If using pip/venv:**

```bash
# The path is typically: /path/to/hg-mcp/.venv
# Or if created elsewhere: echo $VIRTUAL_ENV
```

### Step 2: Configure Your AI Assistant

The executable will be located at:

- **Unix/macOS:** `<venv-path>/bin/hg-mcp`
- **Windows:** `<venv-path>\Scripts\hg-mcp.exe`

Replace `<venv-path>` with your actual virtual environment path from Step 1.

---

### Qwen-Coder & Gemini-CLI

Both use identical configuration format:

**Configuration files:**

- Qwen-Coder: `~/.qwen/settings.json`
- Gemini-CLI: `~/.gemini/settings.json`

```json
{
  "mcpServers": {
    "hg-mcp": {
      "command": "/path/to/your/venv/bin/hg-mcp"
    }
  }
}
```

---

### OpenCode

Configuration file: `~/.config/opencode/opencode.json`

```json
{
  "mcp": {
    "hg-mcp": {
      "type": "local",
      "command": ["/path/to/your/venv/bin/hg-mcp"],
      "enabled": true
    }
  }
}
```

**Note:** When you use `repo_path="."` (default), it resolves to OpenCode's current working directory, so the tools will work in whatever project directory you're currently in.

---

### Claude Desktop

Configuration file location:

- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "hg-mcp": {
      "command": "/path/to/your/venv/bin/hg-mcp"
    }
  }
}
```

---

### Other MCP-Compatible Clients

```
Command: /path/to/your/venv/bin/hg-mcp
```

### Verifying Your Setup

After configuration, restart your AI assistant and verify the MCP server is connected. You can test by asking your assistant to run a Mercurial command like "show the status of this repository" or "list recent commits".

## Requirements

- Python 3.10+
- Mercurial installed and available in PATH
- MCP-compatible client

## Acknowledgments

This project is inspired by [mcp-server-mercurial](https://github.com/Metal-Shark-Sharktech/mcp-server-mercurial).
