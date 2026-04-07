"""MCP server entry point.

This module serves as the main entry point for the hg-mcp MCP server.
All tools are imported from their respective module files.
"""

import argparse
import sys

# Import the MCP server instance
from hg_mcp.server import mcp

# Import all tools to register them with the MCP server
# This must happen after mcp is imported, and before mcp.run()
from hg_mcp.tools import (  # noqa: F401
    hg_add,
    hg_amend,
    hg_annotate,
    hg_backout,
    hg_bookmark,
    hg_bookmarks,
    hg_branch,
    hg_cat,
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
    hg_rename,
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

    parser = argparse.ArgumentParser(description="HG MCP Server")
    parser.add_argument(
        "--transport",
        nargs="+",
        choices=["stdio", "sse", "streamable-http"],
        default=["stdio"],
        help="Transport protocol(s) to use (default: stdio). "
        "Can specify multiple: --transport sse streamable-http",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to listen on for HTTP transports (default: 8000)",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to for HTTP transports (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="Require API key authentication. Clients must send "
        "'X-API-Key' or 'API-Key' header with this value.",
    )
    parser.add_argument(
        "--jail",
        default=None,
        required=False,
        help="Restrict repository access to this directory tree. "
        "Required for HTTP transports. Optional for stdio. "
        "Example: --jail /home/user/projects",
    )

    args = parser.parse_args()

    transports = set(args.transport)

    # Jail is required for HTTP transports
    if transports != {"stdio"} and not args.jail:
        print(
            "Error: --jail is required for HTTP transports (sse, streamable-http).\n"
            "This restricts repository access to a specific directory tree for security.\n"
            "Example: --jail /home/user/projects",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        if transports == {"stdio"}:
            if args.jail:
                from hg_mcp.helpers import set_jail_path

                set_jail_path(args.jail)
                print(f"Jail path set to: {args.jail}")
            mcp.run(transport="stdio")
        elif "stdio" in transports:
            print(
                "Error: Cannot mix stdio with HTTP transports", file=sys.stderr
            )
            sys.exit(1)
        elif transports.issubset({"sse", "streamable-http"}):
            import uvicorn
            from starlette.applications import Starlette
            from starlette.middleware.cors import CORSMiddleware

            from hg_mcp.helpers import APIKeyMiddleware, set_jail_path

            set_jail_path(args.jail)

            def add_cors(app: Starlette) -> Starlette:
                """Add CORS middleware to allow browser-based clients."""
                app.add_middleware(
                    CORSMiddleware,
                    allow_origins=["*"],
                    allow_credentials=True,
                    allow_methods=["*"],
                    allow_headers=["*"],
                    expose_headers=["Mcp-Session-Id"],
                )
                return app

            def add_api_key_auth(app: Starlette, api_key: str) -> Starlette:
                """Add API key validation middleware."""
                app.add_middleware(APIKeyMiddleware, api_key=api_key)
                return app

            if len(transports) == 1:
                # Single transport
                transport = transports.pop()
                print(f"Starting HG MCP Server with {transport} transport")

                if transport == "sse":
                    print(f"SSE endpoint: http://{args.host}:{args.port}/sse")
                    app = mcp.sse_app()
                    add_cors(app)
                    if args.api_key:
                        add_api_key_auth(app, args.api_key)
                        print("API key authentication enabled")
                    uvicorn.run(app, host=args.host, port=args.port)
                elif transport == "streamable-http":
                    print(
                        f"Streamable HTTP endpoint: http://{args.host}:{args.port}/mcp"
                    )
                    app = mcp.streamable_http_app()
                    add_cors(app)
                    if args.api_key:
                        add_api_key_auth(app, args.api_key)
                        print("API key authentication enabled")
                    uvicorn.run(app, host=args.host, port=args.port)
            else:
                # Both transports - need custom combined app
                # SSE creates routes at /sse and /messages
                # Streamable HTTP creates route at /mcp
                sse_app = mcp.sse_app()
                http_app = mcp.streamable_http_app()

                # Combine all routes from both apps
                combined_routes = list(sse_app.routes) + list(http_app.routes)

                app = Starlette(
                    routes=combined_routes,
                    # Use HTTP app's lifespan which initializes the session manager
                    lifespan=http_app.router.lifespan_context,
                )

                add_cors(app)
                if args.api_key:
                    add_api_key_auth(app, args.api_key)
                    print("API key authentication enabled")

                print(
                    "Starting HG MCP Server with sse and streamable-http transport"
                )
                print(f"SSE endpoint: http://{args.host}:{args.port}/sse")
                print(
                    f"Streamable HTTP endpoint: http://{args.host}:{args.port}/mcp"
                )

                uvicorn.run(app, host=args.host, port=args.port)
        else:
            print(
                f"Error: Invalid transport combination: {transports}",
                file=sys.stderr,
            )
            sys.exit(1)
    except KeyboardInterrupt:
        print("\nServer stopped")
        sys.exit(0)


if __name__ == "__main__":
    main()
