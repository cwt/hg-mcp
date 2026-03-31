"""MCP server entry point.

This module serves as the main entry point for the hg-mcp MCP server.
All tools are imported from their respective module files.
"""

# Import the MCP server instance
from hg_mcp.server import mcp

# Import all tools to register them with the MCP server
# This must happen after mcp is imported, and before mcp.run()
from hg_mcp.tools import (  # noqa: F401
    hg_add,
    hg_annotate,
    hg_backout,
    hg_bookmarks,
    hg_branch,
    hg_commit,
    hg_config,
    hg_diff,
    hg_evolve,
    hg_export,
    hg_extensions,
    hg_files,
    hg_git,
    hg_heads,
    hg_help,
    hg_histedit,
    hg_identify,
    hg_import,
    hg_incoming,
    hg_log,
    hg_merge,
    hg_outgoing,
    hg_paths,
    hg_pull,
    hg_push,
    hg_rebase,
    hg_remove,
    hg_resolve,
    hg_revert,
    hg_status,
    hg_strip,
    hg_summary,
    hg_tag,
    hg_tags,
    hg_topic,
    hg_topic_current,
    hg_topics,
    hg_transplant,
    hg_update,
    hg_verify,
)


def main() -> None:
    """Main entry point for the MCP server."""
    from hg_mcp.helpers import setup_event_loop

    setup_event_loop()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
