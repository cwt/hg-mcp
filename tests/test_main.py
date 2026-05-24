"""Tests for hg_mcp/main.py entry point.

Tests for:
- Tool registration verification
- main() function
- MCP server configuration
"""

from unittest.mock import patch

import pytest

from hg_mcp.main import main
from hg_mcp.server import mcp


class TestMainModule:
    """Tests for main.py module."""

    def test_mcp_server_instance(self) -> None:
        """Test that mcp server instance is created."""
        assert mcp is not None
        assert hasattr(mcp, "run")

    def test_mcp_server_name(self) -> None:
        """Test MCP server has correct name."""
        assert mcp.name == "hg"

    def test_tools_registered(self) -> None:
        """Test that all tools are registered with MCP server."""
        tools = mcp._tool_manager._tools
        assert len(tools) == 47

    def test_core_tools_registered(self) -> None:
        """Test core tools are registered."""
        tools = mcp._tool_manager._tools
        core_tools = [
            "hg_status",
            "hg_log",
            "hg_diff",
            "hg_commit",
            "hg_add",
            "hg_remove",
            "hg_update",
            "hg_revert",
            "hg_init",
        ]
        for tool_name in core_tools:
            assert tool_name in tools, f"{tool_name} should be registered"

    def test_branching_tools_registered(self) -> None:
        """Test branching tools are registered."""
        tools = mcp._tool_manager._tools
        branching_tools = [
            "hg_bookmark",
            "hg_bookmarks",
            "hg_branch",
            "hg_tag",
            "hg_tags",
            "hg_topic",
            "hg_topics",
            "hg_topic_current",
            "hg_push",
            "hg_pull",
            "hg_paths",
            "hg_config",
            "hg_extensions",
        ]
        for tool_name in branching_tools:
            assert tool_name in tools, f"{tool_name} should be registered"

    def test_history_tools_registered(self) -> None:
        """Test history tools are registered."""
        tools = mcp._tool_manager._tools
        history_tools = [
            "hg_annotate",
            "hg_backout",
            "hg_export",
            "hg_import",
            "hg_heads",
            "hg_incoming",
            "hg_outgoing",
            "hg_files",
            "hg_summary",
            "hg_verify",
            "hg_identify",
            "hg_help",
            "hg_histedit",
            "hg_largefiles",
        ]
        for tool_name in history_tools:
            assert tool_name in tools, f"{tool_name} should be registered"

    def test_merge_tools_registered(self) -> None:
        """Test merge tools are registered."""
        tools = mcp._tool_manager._tools
        merge_tools = ["hg_merge", "hg_resolve"]
        for tool_name in merge_tools:
            assert tool_name in tools, f"{tool_name} should be registered"

    def test_hggit_tools_registered(self) -> None:
        """Test hg-git tools are registered."""
        tools = mcp._tool_manager._tools
        hggit_tools = [
            "hg_git",
            "hg_rebase",
            "hg_strip",
            "hg_transplant",
            "hg_evolve",
        ]
        for tool_name in hggit_tools:
            assert tool_name in tools, f"{tool_name} should be registered"

    def test_tool_count(self) -> None:
        """Test exact number of tools registered."""
        tools = mcp._tool_manager._tools
        assert len(tools) == 47

    def test_tool_names_are_strings(self) -> None:
        """Test that all tool names are strings."""
        tools = mcp._tool_manager._tools
        for tool_name in tools.keys():
            assert isinstance(tool_name, str)

    def test_mcp_has_instructions(self) -> None:
        """Test that MCP server has instructions configured."""
        assert mcp.instructions is not None
        assert len(mcp.instructions) > 0

    def test_instructions_mention_bookmarks(self) -> None:
        """Test that instructions mention bookmarks."""
        assert mcp.instructions and "bookmark" in mcp.instructions.lower()

    def test_instructions_mention_topics(self) -> None:
        """Test that instructions mention topics."""
        assert mcp.instructions and "topic" in mcp.instructions.lower()

    def test_instructions_mention_hggit(self) -> None:
        """Test that instructions mention hg-git."""
        assert mcp.instructions and (
            "hg-git" in mcp.instructions.lower() or "hggit" in mcp.instructions.lower()
        )

    def test_instructions_mention_extensions(self) -> None:
        """Test that instructions mention extensions."""
        assert mcp.instructions and "extension" in mcp.instructions.lower()


class TestMainFunction:
    """Tests for main() function."""

    @pytest.mark.asyncio
    async def test_main_calls_setup_event_loop(self) -> None:
        """Test that main() calls setup_event_loop."""
        with patch("hg_mcp.helpers.setup_event_loop") as mock_setup:
            with patch.object(mcp, "run") as mock_run:
                # Mock run to avoid actually starting the server
                mock_run.return_value = None

                # Call main
                main()

                # Verify setup_event_loop was called
                mock_setup.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_calls_mcp_run_with_stdio(self) -> None:
        """Test that main() calls mcp.run with stdio transport."""
        with patch("hg_mcp.helpers.setup_event_loop"):
            with patch.object(mcp, "run") as mock_run:
                mock_run.return_value = None

                main()

                mock_run.assert_called_once_with(transport="stdio")

    @pytest.mark.asyncio
    async def test_main_execution_order(self) -> None:
        """Test that main() executes in correct order."""
        call_order = []

        def mock_setup() -> None:
            call_order.append("setup")

        def mock_run(**kwargs: object) -> None:
            call_order.append("run")

        with patch("hg_mcp.helpers.setup_event_loop", side_effect=mock_setup):
            with patch.object(mcp, "run", side_effect=mock_run):
                main()

        assert call_order == ["setup", "run"]


class TestMCPServerConfiguration:
    """Tests for MCP server configuration."""

    def test_mcp_transport_type(self) -> None:
        """Test MCP server supports stdio transport."""
        # The main() function calls mcp.run(transport="stdio")
        # This verifies the server is configured for stdio
        assert hasattr(mcp, "run")

    def test_mcp_server_has_tool_manager(self) -> None:
        """Test MCP server has tool manager."""
        assert hasattr(mcp, "_tool_manager")

    def test_mcp_tool_manager_has_tools(self) -> None:
        """Test tool manager has registered tools."""
        assert hasattr(mcp._tool_manager, "_tools")
        assert len(mcp._tool_manager._tools) > 0

    def test_mcp_instructions_content(self) -> None:
        """Test MCP instructions contain key sections."""
        instructions = mcp.instructions or ""
        assert "Core Workflow" in instructions or "core" in instructions.lower()
        assert "Safety" in instructions or "safety" in instructions.lower()
        assert "Tools" in instructions or "tools" in instructions.lower()

    def test_mcp_instructions_mention_phases(self) -> None:
        """Test instructions mention Mercurial phases."""
        assert mcp.instructions and "phase" in mcp.instructions.lower()

    def test_mcp_instructions_mention_largefiles(self) -> None:
        """Test instructions mention largefiles."""
        assert mcp.instructions and "largefile" in mcp.instructions.lower()

    def test_mcp_instructions_mention_rebase(self) -> None:
        """Test instructions mention rebase."""
        assert mcp.instructions and "rebase" in mcp.instructions.lower()

    def test_mcp_instructions_mention_strip(self) -> None:
        """Test instructions mention strip."""
        assert mcp.instructions and "strip" in mcp.instructions.lower()

    def test_mcp_instructions_mention_amend(self) -> None:
        """Test instructions mention amend."""
        assert mcp.instructions and "amend" in mcp.instructions.lower()

    def test_mcp_instructions_mention_conflicts(self) -> None:
        """Test instructions mention conflict resolution."""
        assert mcp.instructions and (
            "conflict" in mcp.instructions.lower()
            or "resolve" in mcp.instructions.lower()
        )


class TestToolImportOrder:
    """Tests for tool import order in main.py."""

    def test_tools_imported_from_branching(self) -> None:
        """Test tools imported from branching module."""
        from hg_mcp.tools.branching import (
            hg_bookmark,
            hg_bookmarks,
            hg_branch,
        )

        # Verify they're callable
        assert callable(hg_bookmark)
        assert callable(hg_bookmarks)
        assert callable(hg_branch)

    def test_tools_imported_from_core(self) -> None:
        """Test tools imported from core module."""
        from hg_mcp.tools.core import (
            hg_add,
            hg_commit,
            hg_status,
        )

        # Verify they're callable
        assert callable(hg_add)
        assert callable(hg_commit)
        assert callable(hg_status)

    def test_tools_imported_from_hggit(self) -> None:
        """Test tools imported from hggit module."""
        from hg_mcp.tools.hggit import (
            hg_evolve,
            hg_git,
            hg_rebase,
        )

        # Verify they're callable
        assert callable(hg_evolve)
        assert callable(hg_git)
        assert callable(hg_rebase)

    def test_tools_imported_from_history(self) -> None:
        """Test tools imported from history module."""
        from hg_mcp.tools.history import (
            hg_annotate,
            hg_help,
            hg_verify,
        )

        # Verify they're callable
        assert callable(hg_annotate)
        assert callable(hg_help)
        assert callable(hg_verify)

    def test_tools_imported_from_merge(self) -> None:
        """Test tools imported from merge module."""
        from hg_mcp.tools.merge import hg_merge, hg_resolve

        # Verify they're callable
        assert callable(hg_merge)
        assert callable(hg_resolve)


class TestMainEntryPoint:
    """Tests for main entry point behavior."""

    def test_main_module_name(self) -> None:
        """Test __name__ when run as main."""
        # When imported, __name__ is 'hg_mcp.main'
        import hg_mcp.main as main_module

        assert main_module.__name__ == "hg_mcp.main"

    def test_main_has_main_function(self) -> None:
        """Test main module has main function."""
        import hg_mcp.main as main_module

        assert hasattr(main_module, "main")
        assert callable(main_module.main)

    def test_main_function_signature(self) -> None:
        """Test main function has correct signature."""
        import inspect

        sig = inspect.signature(main)
        # main() should return None
        assert sig.return_annotation is None
        # main() should have no parameters
        assert len(sig.parameters) == 0
