# HG MCP Server

[![PyPI Version](https://img.shields.io/pypi/v/hg-mcp.svg)](https://pypi.org/project/hg-mcp/)
[![MCP Badge](https://lobehub.com/badge/mcp/cwt-hg-mcp)](https://lobehub.com/mcp/cwt-hg-mcp)

A Model Context Protocol (MCP) server for Mercurial repository interaction, written in Python 3.10+ with AsyncIO.

## Features

### Core Version Control

- **Initialization**: Create new repositories (`hg_init`)
- **Status & Diff**: View working directory status (`hg_status`) and line-by-line changes (`hg_diff`)
- **Commit Management**: Add files (`hg_add`), commit changes (`hg_commit`), remove files (`hg_remove`), and amend the last commit (`hg_amend`)
- **File Inspection**: View file content at any revision (`hg_cat`) and rename or move files (`hg_rename`)

### Branching & Navigation

- **Navigation**: Update to any revision, branch, or bookmark (`hg_update`)
- **Named Branches**: Create and list permanent Mercurial branches (`hg_branch`)
- **Bookmarks**: Manage lightweight, Git-like pointers (`hg_bookmark`, `hg_bookmarks`)
- **Advanced Topics**: WIP feature isolation with lightweight branches (`hg_topic`, `hg_topics`, `hg_topic_current`)
- **Tags**: Create, remove, and list repository tags (`hg_tag`, `hg_tags`)

### Remote Synchronization

- **Push/Pull**: Sync changes with remote repositories (`hg_push`, `hg_pull`)
- **Remote Insights**: Preview incoming or outgoing changesets (`hg_incoming`, `hg_outgoing`)
- **Path Management**: List and manage configured remote paths (`hg_paths`)
- **Branch Heads**: Identify branch heads across the repository (`hg_heads`)

### History Rewriting & Recovery

- **Rebase & Strip**: Move changesets (`hg_rebase`) or permanently remove them (`hg_strip`)
- **Interactive Editing**: Modify a linear series of changesets non-interactively (`hg_histedit`)
- **Transplant**: Cherry-pick changesets from other branches (`hg_transplant`)
- **Backout**: Reverse the effects of earlier changesets (`hg_backout`)
- **Evolve**: Track the evolution of rewritten changesets (`hg_evolve`)

### Merge & Conflict Resolution

- **Merging**: Combine changes from different branches (`hg_merge`)
- **Conflict Management**: List and track files with unresolved merge conflicts (`hg_resolve`)
- **Revert**: Discard uncommitted changes and restore files to their last committed state (`hg_revert`)

### Repository Inspection & Diagnostics

- **Blame/Annotate**: Show line-by-line changeset information (`hg_annotate`)
- **File Listing**: List all tracked files in the current revision (`hg_files`)
- **State Summary**: Get a concise summary of the working directory state (`hg_summary`)
- **Integrity & Identity**: Verify repository integrity (`hg_verify`) and identify the current revision (`hg_identify`)
- **Patch Management**: Export changesets as patches (`hg_export`) or import patch files (`hg_import`)

### Technical Features

- **Async I/O**: Asynchronous command execution for high-performance operations
- **Git Integration (hg-git)**: Automatic detection of Git-backed repos and branch mapping (`hg_git`)
- **HTTP Transports**: Streamable HTTP and SSE support for web-based clients (e.g., llama.cpp WebUI)
- **Security**: Jail path restriction (required for HTTP) and secure API key authentication
- **JSON Output**: Automatic JSON formatting for 20+ commands for easy machine parsing
- **Large File Support**: Management of binaries outside normal history (`hg_largefiles`)
- **Diagnostics & Help**: List extensions (`hg_extensions`), config (`hg_config`), and access built-in help (`hg_help`)
- **Reliability**: Comprehensive test suite using tmpfs on Linux for extremely fast verification

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

### Standard Input/Output (stdio) - Default Mode

```bash
# Activate your virtual environment first
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
hg-mcp
```

This starts the MCP server using stdio transport, which can be used with MCP clients like Claude for Desktop, Qwen-Coder, Gemini-CLI, and OpenCode.

### HTTP Transport (SSE and/or Streamable HTTP)

For web-based MCP clients like llama.cpp WebUI, you can run the server with HTTP transport:

```bash
# SSE only (compatible with llama.cpp WebUI)
hg-mcp --transport sse --port 8000

# Streamable HTTP only
hg-mcp --transport streamable-http --port 8000

# Both SSE and Streamable HTTP on the same server
hg-mcp --transport sse streamable-http --port 8000
```

**Endpoints:**

- SSE: `http://localhost:8000/sse`
- Streamable HTTP: `http://localhost:8000/mcp`

**Options:**

- `--transport`: One or more transport protocols (`stdio`, `sse`, `streamable-http`)
  - Default: `stdio`
  - Multiple values: `--transport sse streamable-http`
- `--port`: Port to listen on (default: 8000)
- `--host`: Host to bind to (default: 0.0.0.0)
- `--api-key`: **Optional.** Enable mandatory API key authentication. When set, clients must provide this key in their request headers.
- `--jail`: **Required for HTTP transports.** Restrict repository access to this directory tree for security.

### Security Features

When exposing the MCP server over TCP/IP, two security mechanisms are available:

#### 1. Jail Path Restriction (`--jail`)

**Required for all HTTP transports.** This restricts repository access to a specific directory tree, preventing unauthorized access to paths outside the jail:

```bash
# Restrict access to /home/user/projects and its subdirectories
hg-mcp --transport streamable-http --port 8000 --jail /home/user/projects
```

#### 2. API Key Authentication (`--api-key`)

**Optional.** You can require clients to authenticate by providing a valid API key. When this option is enabled, the server will reject any request that does not include a matching `X-API-Key` or `API-Key` header:

```bash
# Enable mandatory API key authentication
hg-mcp --transport streamable-http --port 8000 --jail /home/user/projects --api-key your-secret-key
```

## Integration with AI Assistants

To use this MCP server with your AI coding assistant, point to the correct executable path in your virtual environment.

### Configuration Examples

#### Claude Desktop / Qwen-Coder / Gemini-CLI

```json
{
  "mcpServers": {
    "hg-mcp": {
      "command": "/path/to/your/venv/bin/hg-mcp"
    }
  }
}
```

#### OpenCode

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

## Requirements

- Python 3.10+
- Mercurial installed and available in PATH
- MCP-compatible client

## Development

### Running Tests

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run all tests with coverage
./scripts/runtest.sh
```

### Code Quality

```bash
# Run linting
./scripts/lint-check-and-fix.sh

# Run type checking
./scripts/type-check.sh

# Run formatter
./scripts/code-format.sh
```

## Acknowledgments

This project is inspired by [mcp-server-mercurial](https://github.com/Metal-Shark-Sharktech/mcp-server-mercurial).
