"""hg-mcp tools package.

Exports all Mercurial MCP tools organized by category.
"""

# Import mcp server first to avoid circular imports
from hg_mcp.server import mcp  # noqa: F401

# Import all tools to register them with the MCP server
# Tools are automatically registered when their modules are imported
from hg_mcp.tools.branching import (
    hg_bookmark,
    hg_bookmarks,
    hg_branch,
    hg_config,
    hg_extensions,
    hg_paths,
    hg_pull,
    hg_push,
    hg_tag,
    hg_tags,
    hg_topic,
    hg_topic_current,
    hg_topics,
)
from hg_mcp.tools.core import (
    hg_add,
    hg_amend,
    hg_cat,
    hg_clone,
    hg_commit,
    hg_diff,
    hg_init,
    hg_log,
    hg_remove,
    hg_rename,
    hg_revert,
    hg_status,
    hg_update,
)
from hg_mcp.tools.hggit import (
    hg_evolve,
    hg_git,
    hg_rebase,
    hg_strip,
    hg_transplant,
)
from hg_mcp.tools.history import (
    hg_annotate,
    hg_backout,
    hg_export,
    hg_files,
    hg_heads,
    hg_help,
    hg_histedit,
    hg_identify,
    hg_import,
    hg_incoming,
    hg_largefiles,
    hg_outgoing,
    hg_summary,
    hg_verify,
)
from hg_mcp.tools.merge import hg_merge, hg_resolve

__all__ = [
    # Core tools
    "hg_add",
    "hg_amend",
    "hg_backout",
    "hg_cat",
    "hg_clone",
    "hg_commit",
    "hg_config",
    "hg_diff",
    "hg_export",
    "hg_files",
    "hg_git",
    "hg_init",
    "hg_help",
    "hg_histedit",
    "hg_import",
    "hg_incoming",
    "hg_largefiles",
    "hg_log",
    "hg_outgoing",
    "hg_remove",
    "hg_rebase",
    "hg_rename",
    "hg_revert",
    "hg_status",
    "hg_summary",
    "hg_strip",
    "hg_transplant",
    "hg_evolve",
    "hg_update",
    "hg_verify",
    # History tools
    "hg_annotate",
    "hg_backout",
    "hg_evolve",
    "hg_export",
    "hg_files",
    "hg_help",
    "hg_histedit",
    "hg_import",
    "hg_incoming",
    "hg_largefiles",
    "hg_outgoing",
    "hg_heads",
    "hg_verify",
    "hg_identify",
    "hg_cat",
    # Branching tools
    "hg_branch",
    "hg_bookmark",
    "hg_bookmarks",
    "hg_config",
    "hg_extensions",
    "hg_paths",
    "hg_push",
    "hg_pull",
    "hg_tag",
    "hg_tags",
    "hg_topic",
    "hg_topics",
    "hg_topic_current",
    # Merge tools
    "hg_merge",
    "hg_resolve",
    # hg-git tool
    "hg_git",
    # File operations
    "hg_rename",
    # Amend tool
    "hg_amend",
]
