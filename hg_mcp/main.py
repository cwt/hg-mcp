"""MCP server for Mercurial repository interaction."""

# Import tools module to register all tools with the MCP server
import hg_mcp.tools  # noqa: F401
from hg_mcp.helpers import setup_event_loop
from hg_mcp.server import mcp


def main() -> None:
    """Run the MCP server."""
    setup_event_loop()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
