"""Constants and command execution for hg-mcp server."""

# Maximum log limit for hg_log command
MAX_LOG_LIMIT = 1000

# Mapping of command names to their required extensions for error hints
EXTENSION_HINTS = {
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
JSON_SUPPORTED_COMMANDS = {
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
    "resolve",
    "status",
    "tags",
    "topics",
    "verify",
}

# Patterns to identify Git remotes
GIT_REMOTE_PATTERNS = [
    ".git",
    "github.com",
    "gitlab.com",
    "bitbucket.org",
    "git://",
    "ssh://git@",
    "https://github.com",
]
