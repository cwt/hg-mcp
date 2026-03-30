"""MCP tools for hg-mcp server."""

from hg_mcp.tools.branching import (
    hg_bookmark_create,
    hg_bookmarks,
    hg_branch,
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
    hg_commit,
    hg_diff,
    hg_log,
    hg_remove,
    hg_rename,
    hg_revert,
    hg_status,
    hg_update,
)
from hg_mcp.tools.hggit import hg_git
from hg_mcp.tools.history import (
    hg_annotate,
    hg_backout,
    hg_evolve,
    hg_export,
    hg_heads,
    hg_histedit,
    hg_import,
    hg_rebase,
    hg_strip,
    hg_transplant,
)
from hg_mcp.tools.inspect import (
    hg_config,
    hg_extensions,
    hg_files,
    hg_help,
    hg_identify,
    hg_largefiles,
    hg_summary,
    hg_verify,
)
from hg_mcp.tools.merge import (
    hg_merge,
    hg_resolve,
)
from hg_mcp.tools.remote import (
    hg_incoming,
    hg_outgoing,
    hg_paths,
    hg_pull,
    hg_push,
)

__all__ = [
    # Branching tools
    "hg_bookmarks",
    "hg_bookmark_create",
    "hg_branch",
    "hg_tags",
    "hg_tag",
    "hg_topic",
    "hg_topics",
    "hg_topic_current",
    # Core tools
    "hg_status",
    "hg_log",
    "hg_diff",
    "hg_commit",
    "hg_amend",
    "hg_add",
    "hg_remove",
    "hg_update",
    "hg_revert",
    "hg_rename",
    "hg_cat",
    # hg-git tools
    "hg_git",
    # History tools
    "hg_annotate",
    "hg_backout",
    "hg_evolve",
    "hg_export",
    "hg_heads",
    "hg_histedit",
    "hg_import",
    "hg_rebase",
    "hg_strip",
    "hg_transplant",
    # Inspect tools
    "hg_config",
    "hg_extensions",
    "hg_files",
    "hg_help",
    "hg_identify",
    "hg_largefiles",
    "hg_summary",
    "hg_verify",
    # Merge tools
    "hg_merge",
    "hg_resolve",
    # Remote tools
    "hg_incoming",
    "hg_outgoing",
    "hg_paths",
    "hg_pull",
    "hg_push",
]
