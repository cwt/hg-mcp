"""Extended tests for hg_mcp/main.py entry point."""

from unittest.mock import MagicMock, patch

from hg_mcp.main import main
from hg_mcp.server import mcp


class TestMainExtended:
    """Extended tests for main.py."""

    def setup_method(self) -> None:
        """Reset mcp state before each test."""
        mcp._jail_path = None

    @patch("argparse.ArgumentParser.parse_args")
    @patch("hg_mcp.server.mcp.run")
    @patch("hg_mcp.helpers.setup_event_loop")
    def test_main_stdio_no_jail(
        self,
        mock_setup: MagicMock,
        mock_run: MagicMock,
        mock_parse_args: MagicMock,
    ) -> None:
        """Test main with default stdio and no jail."""
        mock_parse_args.return_value = MagicMock(
            transport=["stdio"],
            jail=None,
            port=8000,
            host="0.0.0.0",
            api_key=None,
        )
        main()
        mock_run.assert_called_once_with(transport="stdio")

    @patch("argparse.ArgumentParser.parse_args")
    @patch("hg_mcp.server.mcp.run")
    def test_main_stdio_with_jail(
        self, mock_run: MagicMock, mock_parse_args: MagicMock
    ) -> None:
        """Test main with stdio and jail."""
        mock_parse_args.return_value = MagicMock(
            transport=["stdio"],
            jail="/tmp/jail",
            port=8000,
            host="0.0.0.0",
            api_key=None,
        )
        main()
        assert mcp.jail_path is not None

    @patch("argparse.ArgumentParser.parse_args")
    @patch("hg_mcp.server.mcp.sse_app")
    @patch("uvicorn.run")
    def test_main_sse_with_jail(
        self,
        mock_uvicorn: MagicMock,
        mock_sse_app: MagicMock,
        mock_parse_args: MagicMock,
    ) -> None:
        """Test main with SSE transport and jail."""
        mock_parse_args.return_value = MagicMock(
            transport=["sse"],
            jail="/tmp/jail",
            port=8000,
            host="0.0.0.0",
            api_key=None,
        )
        main()
        mock_uvicorn.assert_called_once()

    @patch("argparse.ArgumentParser.parse_args")
    @patch("hg_mcp.server.mcp.streamable_http_app")
    @patch("uvicorn.run")
    def test_main_streamable_http_with_jail(
        self,
        mock_uvicorn: MagicMock,
        mock_http_app: MagicMock,
        mock_parse_args: MagicMock,
    ) -> None:
        """Test main with streamable-http transport and jail."""
        mock_parse_args.return_value = MagicMock(
            transport=["streamable-http"],
            jail="/tmp/jail",
            port=8001,
            host="127.0.0.1",
            api_key=None,
        )
        main()
        mock_uvicorn.assert_called_once()

    @patch("argparse.ArgumentParser.parse_args")
    @patch("starlette.applications.Starlette")
    @patch("hg_mcp.server.mcp.sse_app")
    @patch("hg_mcp.server.mcp.streamable_http_app")
    @patch("uvicorn.run")
    def test_main_combined_transports(
        self,
        mock_uvicorn: MagicMock,
        mock_http_app: MagicMock,
        mock_sse_app: MagicMock,
        mock_starlette: MagicMock,
        mock_parse_args: MagicMock,
    ) -> None:
        """Test main with both SSE and streamable-http transports."""
        mock_parse_args.return_value = MagicMock(
            transport=["sse", "streamable-http"],
            jail="/tmp/jail",
            port=8000,
            host="0.0.0.0",
            api_key=None,
        )
        http_app = MagicMock()
        http_app.router.lifespan_context = MagicMock()
        mock_http_app.return_value = http_app
        main()
        mock_uvicorn.assert_called_once()

    @patch("argparse.ArgumentParser.parse_args")
    @patch("hg_mcp.server.mcp.sse_app")
    @patch("uvicorn.run")
    def test_main_with_api_key(
        self,
        mock_uvicorn: MagicMock,
        mock_sse_app: MagicMock,
        mock_parse_args: MagicMock,
    ) -> None:
        """Test main with API key authentication enabled."""
        mock_parse_args.return_value = MagicMock(
            transport=["sse"],
            jail="/tmp/jail",
            port=8000,
            host="0.0.0.0",
            api_key="secret-key",
        )
        mock_app = MagicMock()
        mock_sse_app.return_value = mock_app
        main()
        mock_uvicorn.assert_called_once()

    @patch("argparse.ArgumentParser.parse_args")
    @patch("hg_mcp.server.mcp.run", side_effect=KeyboardInterrupt)
    @patch("sys.exit")
    def test_main_keyboard_interrupt(
        self,
        mock_exit: MagicMock,
        mock_run: MagicMock,
        mock_parse_args: MagicMock,
    ) -> None:
        """Test main handles KeyboardInterrupt gracefully."""
        mock_parse_args.return_value = MagicMock(
            transport=["stdio"],
            jail=None,
            port=8000,
            host="0.0.0.0",
            api_key=None,
        )
        main()
        mock_exit.assert_called_once_with(0)


class TestServerMain:
    """Tests for server.py main function."""

    @patch("hg_mcp.server.mcp.run")
    @patch("hg_mcp.helpers.setup_event_loop")
    def test_server_main(
        self, mock_setup: MagicMock, mock_run: MagicMock
    ) -> None:
        """Test server.main calls setup and run."""
        from hg_mcp.server import main as server_main

        server_main()
        mock_run.assert_called_once_with(transport="stdio")
