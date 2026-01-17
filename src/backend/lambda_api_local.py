"""Local API Gateway-style server for Lambda handlers."""
from __future__ import annotations

import json
import os
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Callable
from urllib.parse import urlparse

from . import lambda_handlers


def _allowed_origins() -> list[str]:
    raw = os.getenv("CORS_ALLOW_ORIGINS") or "https://skybridge.localhost"
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    return origins or ["https://skybridge.localhost"]

_ROUTES: list[tuple[str, re.Pattern[str], Callable]] = []


def _route(method: str, pattern: str, handler: Callable) -> None:
    """Register a route pattern."""
    compiled = re.compile(pattern)
    _ROUTES.append((method.upper(), compiled, handler))


def _register_routes() -> None:
    """Register route mappings to Lambda handlers."""
    _route("POST", r"^/credentials/validate$", lambda_handlers.validate_credentials_handler)
    _route("POST", r"^/jobs$", lambda_handlers.create_job_handler)
    _route("GET", r"^/jobs$", lambda_handlers.list_jobs_handler)
    _route("GET", r"^/jobs/(?P<job_id>[^/]+)$", lambda_handlers.get_job_handler)
    _route(
        "POST",
        r"^/jobs/(?P<job_id>[^/]+)/review/accept$",
        lambda_handlers.accept_review_handler,
    )
    _route(
        "GET",
        r"^/jobs/(?P<job_id>[^/]+)/artifacts$",
        lambda_handlers.list_artifacts_handler,
    )
    _route(
        "GET",
        r"^/jobs/(?P<job_id>[^/]+)/artifacts\.zip$",
        lambda_handlers.download_artifacts_zip_handler,
    )
    _route(
        "GET",
        r"^/jobs/(?P<job_id>[^/]+)/artifacts/(?P<artifact_name>[^/]+)$",
        lambda_handlers.read_artifact_handler,
    )
    _route("DELETE", r"^/jobs/(?P<job_id>[^/]+)$", lambda_handlers.delete_job_handler)


class LambdaLocalHandler(BaseHTTPRequestHandler):
    """HTTP handler that maps requests to Lambda handlers."""

    server_version = "SkybridgeLambdaLocal/1.0"

    def do_GET(self) -> None:  # noqa: N802
        self._handle()

    def do_POST(self) -> None:  # noqa: N802
        self._handle()

    def do_DELETE(self) -> None:  # noqa: N802
        self._handle()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def _handle(self) -> None:
        method = self.command.upper()
        parsed = urlparse(self.path)
        path = parsed.path
        body = None
        if "Content-Length" in self.headers:
            length = int(self.headers.get("Content-Length", "0"))
            if length:
                body = self.rfile.read(length).decode("utf-8")

        for route_method, pattern, handler in _ROUTES:
            if route_method != method:
                continue
            match = pattern.match(path)
            if not match:
                continue
            event = {
                "headers": {k: v for k, v in self.headers.items()},
                "pathParameters": match.groupdict(),
                "body": body or "",
                "rawPath": path,
                "requestContext": {"http": {"method": method, "path": path}},
            }
            response = handler(event, None)
            status = int(response.get("statusCode", 200))
            headers = response.get("headers") or {}
            payload = response.get("body", "")
            is_b64 = response.get("isBase64Encoded", False)

            self.send_response(status)
            self._send_cors_headers()
            for key, value in headers.items():
                self.send_header(key, value)
            if not headers.get("Content-Type"):
                self.send_header("Content-Type", "application/json")
            self.end_headers()

            if isinstance(payload, dict):
                payload = json.dumps(payload)
            if is_b64:
                import base64

                self.wfile.write(base64.b64decode(payload))
            else:
                if isinstance(payload, str):
                    payload = payload.encode("utf-8")
                self.wfile.write(payload)
            return

        self.send_response(404)
        self._send_cors_headers()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"detail":"Not found"}')

    def _send_cors_headers(self) -> None:
        """Apply CORS headers for local dev."""
        origin = self.headers.get("Origin") or ""
        origins = _allowed_origins()
        if "*" in origins:
            allow_origin = "*"
        elif origin in origins:
            allow_origin = origin
        else:
            allow_origin = origins[0]
        self.send_header("Access-Control-Allow-Origin", allow_origin)
        self.send_header("Access-Control-Allow-Methods", "GET,POST,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization,Content-Type,X-User-Id")


def run(host: str = "0.0.0.0", port: int = 8000) -> None:
    """Run the local API Gateway emulator."""
    _register_routes()
    server = HTTPServer((host, port), LambdaLocalHandler)
    print(f"[lambda-local] listening on {host}:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    run()
    _route("POST", r"^/auth/token$", lambda_handlers.auth_token_handler)
