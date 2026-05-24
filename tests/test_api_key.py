"""Unit tests for API key authentication middleware.

Tests the --api-key feature that requires clients to provide a valid
API key in the X-API-Key or API-Key header.
"""

from starlette.applications import Starlette
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from hg_mcp.helpers import APIKeyMiddleware


def create_test_app() -> Starlette:
    """Create a simple test app with API key middleware."""

    async def homepage(request: object) -> PlainTextResponse:
        return PlainTextResponse("Hello, World!")

    async def protected_endpoint(request: object) -> JSONResponse:
        return JSONResponse({"message": "Success"})

    app = Starlette(
        routes=[
            Route("/", homepage),
            Route("/api", protected_endpoint, methods=["GET", "POST", "OPTIONS"]),
        ]
    )
    return app


class TestAPIKeyMiddleware:
    """Tests for APIKeyMiddleware."""

    def test_request_without_api_key_rejected(self) -> None:
        """Requests without API key should return 401."""
        app = create_test_app()
        app.add_middleware(APIKeyMiddleware, api_key="secret123")

        with TestClient(app) as client:
            response = client.get("/")
            assert response.status_code == 401
            assert "Unauthorized" in response.json()["error"]

    def test_request_with_wrong_api_key_rejected(self) -> None:
        """Requests with incorrect API key should return 401."""
        app = create_test_app()
        app.add_middleware(APIKeyMiddleware, api_key="secret123")

        with TestClient(app) as client:
            response = client.get("/", headers={"X-API-Key": "wrong_key"})
            assert response.status_code == 401
            assert "Unauthorized" in response.json()["error"]

    def test_request_with_correct_x_api_key_allowed(self) -> None:
        """Requests with correct X-API-Key header should pass."""
        app = create_test_app()
        app.add_middleware(APIKeyMiddleware, api_key="secret123")

        with TestClient(app) as client:
            response = client.get("/", headers={"X-API-Key": "secret123"})
            assert response.status_code == 200
            assert "Hello, World!" in response.text

    def test_request_with_correct_api_key_allowed(self) -> None:
        """Requests with correct API-Key header (no X- prefix) should pass."""
        app = create_test_app()
        app.add_middleware(APIKeyMiddleware, api_key="secret123")

        with TestClient(app) as client:
            response = client.get("/", headers={"API-Key": "secret123"})
            assert response.status_code == 200
            assert "Hello, World!" in response.text

    def test_options_request_bypasses_auth(self) -> None:
        """OPTIONS requests (CORS preflight) should bypass API key check."""
        app = create_test_app()
        app.add_middleware(APIKeyMiddleware, api_key="secret123")

        with TestClient(app) as client:
            response = client.options("/api")
            # OPTIONS should pass through (either 200 or method not allowed is OK)
            # The important thing is it doesn't return 401
            assert response.status_code != 401

    def test_post_request_without_key_rejected(self) -> None:
        """POST requests without API key should be rejected."""
        app = create_test_app()
        app.add_middleware(APIKeyMiddleware, api_key="secret123")

        with TestClient(app) as client:
            response = client.post("/api", json={"test": "data"})
            assert response.status_code == 401

    def test_post_request_with_correct_key_allowed(self) -> None:
        """POST requests with correct API key should pass."""
        app = create_test_app()
        app.add_middleware(APIKeyMiddleware, api_key="secret123")

        with TestClient(app) as client:
            response = client.post(
                "/api",
                json={"test": "data"},
                headers={"X-API-Key": "secret123"},
            )
            assert response.status_code == 200

    def test_empty_api_key_rejected(self) -> None:
        """Empty API key should be rejected."""
        app = create_test_app()
        app.add_middleware(APIKeyMiddleware, api_key="secret123")

        with TestClient(app) as client:
            response = client.get("/", headers={"X-API-Key": ""})
            assert response.status_code == 401

    def test_case_sensitive_key(self) -> None:
        """API key matching should be case-sensitive."""
        app = create_test_app()
        app.add_middleware(APIKeyMiddleware, api_key="Secret123")

        with TestClient(app) as client:
            # Wrong case should be rejected
            response = client.get("/", headers={"X-API-Key": "secret123"})
            assert response.status_code == 401

            # Correct case should pass
            response = client.get("/", headers={"X-API-Key": "Secret123"})
            assert response.status_code == 200

    def test_special_characters_in_key(self) -> None:
        """API keys with special characters should work."""
        special_key = "key-with-special-chars!@#$%^&*()"
        app = create_test_app()
        app.add_middleware(APIKeyMiddleware, api_key=special_key)

        with TestClient(app) as client:
            response = client.get("/", headers={"X-API-Key": special_key})
            assert response.status_code == 200

    def test_no_middleware_allows_all(self) -> None:
        """Without middleware, all requests should pass."""
        app = create_test_app()
        # No middleware added

        with TestClient(app) as client:
            response = client.get("/")
            assert response.status_code == 200

            # Even without API key
            response = client.get("/api")
            assert response.status_code == 200


class TestAPIKeyMiddlewareIntegration:
    """Integration tests with realistic scenarios."""

    def test_multiple_requests_with_session(self) -> None:
        """Multiple requests should all require API key."""

        async def endpoint(request: object) -> JSONResponse:
            return JSONResponse({"count": 1})

        app = Starlette(routes=[Route("/test", endpoint, methods=["GET"])])
        app.add_middleware(APIKeyMiddleware, api_key="test_key")

        with TestClient(app) as client:
            # All requests should require the key
            for _ in range(3):
                response = client.get("/test", headers={"X-API-Key": "test_key"})
                assert response.status_code == 200

    def test_different_endpoints_same_key(self) -> None:
        """All endpoints should be protected by the same key."""

        async def endpoint1(request: object) -> PlainTextResponse:
            return PlainTextResponse("Endpoint 1")

        async def endpoint2(request: object) -> PlainTextResponse:
            return PlainTextResponse("Endpoint 2")

        app = Starlette(
            routes=[
                Route("/e1", endpoint1),
                Route("/e2", endpoint2),
            ]
        )
        app.add_middleware(APIKeyMiddleware, api_key="global_key")

        with TestClient(app) as client:
            # Both endpoints require the key
            response = client.get("/e1", headers={"X-API-Key": "global_key"})
            assert response.status_code == 200

            response = client.get("/e2", headers={"X-API-Key": "global_key"})
            assert response.status_code == 200

            # Both reject without key
            response = client.get("/e1")
            assert response.status_code == 401

            response = client.get("/e2")
            assert response.status_code == 401
