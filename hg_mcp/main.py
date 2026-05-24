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
    hg_absorb,
    hg_add,
    hg_amend,
    hg_annotate,
    hg_backout,
    hg_bisect,
    hg_bookmark,
    hg_bookmarks,
    hg_branch,
    hg_cat,
    hg_clone,
    hg_commit,
    hg_config,
    hg_diff,
    hg_evolve,
    hg_export,
    hg_extensions,
    hg_files,
    hg_fold,
    hg_git,
    hg_graft,
    hg_heads,
    hg_help,
    hg_histedit,
    hg_identify,
    hg_import,
    hg_incoming,
    hg_log,
    hg_merge,
    hg_metaedit,
    hg_next,
    hg_outgoing,
    hg_paths,
    hg_phases,
    hg_previous,
    hg_prune,
    hg_pull,
    hg_push,
    hg_rebase,
    hg_remove,
    hg_rename,
    hg_resolve,
    hg_revert,
    hg_rewind,
    hg_split,
    hg_stack,
    hg_status,
    hg_strip,
    hg_summary,
    hg_tag,
    hg_tags,
    hg_topic,
    hg_topic_current,
    hg_topics,
    hg_transplant,
    hg_uncommit,
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
                mcp.jail_path = args.jail
                print(f"Jail path set to: {args.jail}")
            mcp.run(transport="stdio")
        elif "stdio" in transports:
            print("Error: Cannot mix stdio with HTTP transports", file=sys.stderr)
            sys.exit(1)
        elif transports.issubset({"sse", "streamable-http"}):
            import uvicorn
            from starlette.applications import Starlette
            from starlette.middleware.cors import CORSMiddleware
            from starlette.routing import BaseRoute, Route

            from hg_mcp.helpers import APIKeyMiddleware

            mcp.jail_path = args.jail
            mcp.settings.json_response = True

            # SSE and Streamable HTTP app setup
            # We must create these apps before Starlette() to use their routes
            sse_app = mcp.sse_app()
            http_app = mcp.streamable_http_app()

            # Find the streamable_http_app handler (needed for POST /sse compatibility)
            http_handler = None
            for route in http_app.routes:
                if (
                    isinstance(route, Route)
                    and route.path == mcp.settings.streamable_http_path
                ):
                    http_handler = route.endpoint
                    break

            # Create a combined routes list
            combined_routes: list[BaseRoute] = []

            # 1. Compatibility route: POST /sse -> StreamableHTTP
            if http_handler:
                combined_routes.append(
                    Route(mcp.settings.sse_path, http_handler, methods=["POST"])
                )
                print(
                    f"Added POST support to {mcp.settings.sse_path} for Streamable HTTP compatibility"
                )

            # 2. Regular routes
            if "sse" in transports:
                combined_routes.extend(sse_app.routes)

            if "streamable-http" in transports:
                # Only add if path doesn't already exist or it's a different path
                for route in http_app.routes:
                    if isinstance(route, Route):
                        if not any(
                            isinstance(r, Route) and r.path == route.path
                            for r in combined_routes
                        ):
                            combined_routes.append(route)
                    else:
                        combined_routes.append(route)

            # Create the Starlette app with combined routes
            app = Starlette(
                routes=combined_routes,
                # Use http_app's lifespan which initializes the session manager
                lifespan=http_app.router.lifespan_context,
            )

            # Add CORS middleware
            app.add_middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
                expose_headers=["Mcp-Session-Id"],
            )

            # Add API key middleware if needed
            if args.api_key:
                # Middleware applied in reverse order of addition
                # Request -> APIKeyMiddleware -> CORSMiddleware -> App
                app.add_middleware(APIKeyMiddleware, api_key=args.api_key)
                print("API key authentication enabled")

            print(f"Starting HG MCP Server with {' and '.join(transports)} transport")
            if "sse" in transports:
                print(
                    f"SSE endpoint: http://{args.host}:{args.port}{mcp.settings.sse_path}"
                )
            if "streamable-http" in transports:
                print(
                    f"Streamable HTTP endpoint: http://{args.host}:{args.port}{mcp.settings.streamable_http_path}"
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
