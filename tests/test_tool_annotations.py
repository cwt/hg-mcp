"""Tests for tool annotations and error handling across all tools.

Ensures that:
1. Every tool has all 4 hints declared: readOnlyHint, destructiveHint, idempotentHint, openWorldHint
2. All 4 hints are strict booleans (True or False)
3. Destructive tools are appropriately labelled with destructiveHint=True
4. All tool handlers handle invalid repo_path gracefully and return error responses
"""

import pytest

import hg_mcp.main  # noqa: F401
from hg_mcp.server import mcp

EXPECTED_DESTRUCTIVE_TOOLS = {
    "hg_absorb",
    "hg_amend",
    "hg_fold",
    "hg_histedit",
    "hg_metaedit",
    "hg_prune",
    "hg_rebase",
    "hg_remove",
    "hg_rename",
    "hg_revert",
    "hg_split",
    "hg_strip",
    "hg_tag",
    "hg_uncommit",
    "hg_unshelve",
}

EXPECTED_OPEN_WORLD_TOOLS = {
    "hg_clone",
    "hg_incoming",
    "hg_outgoing",
    "hg_pull",
    "hg_push",
}


def test_all_tools_have_all_four_hints_declared() -> None:
    """Verify all registered tools declare all 4 hints as booleans."""
    tools = mcp._tool_manager._tools
    assert len(tools) > 0, "No tools registered"

    for name, tool in tools.items():
        assert tool.annotations is not None, f"Tool {name} is missing annotations"
        ann = tool.annotations

        for hint_name in [
            "readOnlyHint",
            "destructiveHint",
            "idempotentHint",
            "openWorldHint",
        ]:
            val = getattr(ann, hint_name)
            assert val is not None, f"Tool {name} is missing hint: {hint_name}"
            assert isinstance(
                val, bool
            ), f"Tool {name} hint {hint_name} must be a bool, got {type(val)}"


def test_destructive_hints_labelled() -> None:
    """Verify that destructive tools are correctly annotated with destructiveHint=True."""
    tools = mcp._tool_manager._tools
    for name, tool in tools.items():
        ann = tool.annotations
        assert ann is not None
        if name in EXPECTED_DESTRUCTIVE_TOOLS:
            assert (
                ann.destructiveHint is True
            ), f"Expected destructiveHint=True for {name}"
            assert (
                ann.readOnlyHint is False
            ), f"Expected readOnlyHint=False for destructive tool {name}"
        else:
            assert (
                ann.destructiveHint is False
            ), f"Expected destructiveHint=False for non-destructive tool {name}"


def test_open_world_hints_labelled() -> None:
    """Verify open-world (network/remote) tools are correctly annotated."""
    tools = mcp._tool_manager._tools
    for name, tool in tools.items():
        ann = tool.annotations
        assert ann is not None
        if name in EXPECTED_OPEN_WORLD_TOOLS:
            assert (
                ann.openWorldHint is True
            ), f"Expected openWorldHint=True for remote tool {name}"
        else:
            assert (
                ann.openWorldHint is False
            ), f"Expected openWorldHint=False for local tool {name}"


@pytest.mark.asyncio
async def test_all_tools_catch_errors_on_invalid_repo() -> None:
    """Verify that invoking tools with an invalid repo returns a clean response without crashing."""
    import inspect

    tools = mcp._tool_manager._tools
    for name, tool in tools.items():
        fn = tool.fn
        sig = inspect.signature(fn)
        kwargs: dict[str, object] = {}
        for param_name, param in sig.parameters.items():
            if param_name == "repo_path":
                kwargs[param_name] = "/nonexistent/invalid/repo/path"
            elif param.default is inspect.Parameter.empty:
                # Required parameter, provide dummy string or list
                if (
                    "files" in param_name
                    or "revisions" in param_name
                    or "patches" in param_name
                ):
                    kwargs[param_name] = ["test"]
                else:
                    kwargs[param_name] = "test"

        # Call the tool function
        try:
            if inspect.iscoroutinefunction(fn):
                result = await fn(**kwargs)
            else:
                result = fn(**kwargs)

            # hg_help works without a repo by design
            if name == "hg_help":
                assert isinstance(result, str) and len(result) > 0
                continue

            # The result should be str or list of TextContent
            if isinstance(result, list):
                combined = " ".join(getattr(item, "text", str(item)) for item in result)
                assert (
                    "Error" in combined
                    or "error" in combined
                    or "not a mercurial repository" in combined.lower()
                    or "does not exist" in combined.lower()
                ), f"Tool {name} did not return structured error for invalid repo: {result}"
            elif isinstance(result, str):
                assert (
                    "Error" in result
                    or "error" in result
                    or "not a mercurial repository" in result.lower()
                    or "does not exist" in result.lower()
                ), f"Tool {name} did not return structured error for invalid repo: {result}"
        except Exception as e:
            pytest.fail(f"Tool {name} raised uncaught exception on invalid repo: {e}")
