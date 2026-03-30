"""Decorators for MCP tool output handling."""

import functools
import logging
from collections.abc import Awaitable, Callable
from typing import ParamSpec, TypeVar

from mcp.types import Annotations, TextContent

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R", bound=str | list[TextContent])


def json_tool(
    func: Callable[P, Awaitable[list[TextContent] | str]],
) -> Callable[P, Awaitable[list[TextContent]]]:
    """Decorator for tools that return JSON output.

    Wraps the returned JSON string in TextContent with audience: ["assistant"]
    annotation to indicate this content is intended for AI agents (minified,
    machine-readable) rather than human users.

    The decorated function should return a string (JSON output) or list[TextContent].
    """

    @functools.wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> list[TextContent]:
        result = await func(*args, **kwargs)

        # If result is an error (str type), return as plain text in TextContent
        # (users should see errors)
        if isinstance(result, str) and result.startswith("Error:"):
            return [
                TextContent(
                    type="text",
                    text=result,
                    annotations=Annotations(audience=["user"], priority=1.0),
                )
            ]

        # If result is already list[TextContent], return as-is
        if isinstance(result, list):
            return result

        # Wrap JSON output (str) in TextContent with assistant-only annotation
        return [
            TextContent(
                type="text",
                text=result,
                annotations=Annotations(audience=["assistant"], priority=0.5),
            )
        ]

    wrapper._is_json_tool = True  # type: ignore[attr-defined]
    return wrapper


def handle_repo_errors(
    func: Callable[P, Awaitable[str | list[TextContent]]],
) -> Callable[P, Awaitable[str | list[TextContent]]]:
    """Decorator to handle common repository validation errors.

    For functions decorated with @json_tool, returns errors as list[TextContent]
    with audience=['user'] to ensure errors are visible to users.
    For other functions, returns errors as plain str.
    """
    from mcp.types import Annotations as AnnotationsType

    @functools.wraps(func)
    async def wrapper(
        *args: P.args, **kwargs: P.kwargs
    ) -> str | list[TextContent]:
        # We assume the first argument or 'repo_path' kwarg is the path
        # But since we invoke validate_repo_path inside the tools,
        # we essentially use this to catch the ValueErrors raised there.
        try:
            return await func(*args, **kwargs)
        except ValueError as e:
            msg = str(e)
            if "Not a Mercurial repository" in msg:
                error_msg = (
                    f"Error: {msg}\n\n"
                    "To verify if this is a Mercurial repository:\n"
                    "1. Check if a .hg directory exists\n"
                    "2. Try running hg_log to see commit history"
                )
            else:
                error_msg = f"Error: {msg}"

            # Check if the wrapped function is decorated with @json_tool
            # using the marker attribute set by the decorator
            is_json_tool = getattr(func, "_is_json_tool", False)

            if is_json_tool:
                return [
                    TextContent(
                        type="text",
                        text=error_msg,
                        annotations=AnnotationsType(
                            audience=["user"], priority=1.0
                        ),
                    )
                ]
            return error_msg

    return wrapper
