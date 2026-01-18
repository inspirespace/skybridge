"""HTTP API for Cloud Run (maps requests to Lambda handlers)."""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from . import lambda_handlers
from .rate_limit import RateLimiter

_logger = logging.getLogger(__name__)

app = FastAPI(title="Skybridge API")

# Rate limiters for sensitive endpoints (10 requests per 60 seconds per IP)
_auth_rate_limiter = RateLimiter(window_seconds=60, max_events=10)
_credentials_rate_limiter = RateLimiter(window_seconds=60, max_events=10)


def _cors_config() -> list[str]:
    raw = os.getenv("CORS_ALLOW_ORIGINS") or "https://skybridge.localhost"
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    if not origins:
        origins = ["https://skybridge.localhost"]
    if "*" in origins:
        # Log warning if wildcard CORS is configured
        if os.getenv("BACKEND_PRODUCTION", "").lower() in {"1", "true", "yes", "on"}:
            _logger.warning(
                "SECURITY WARNING: CORS_ALLOW_ORIGINS contains '*' in production. "
                "This allows requests from any origin. Configure explicit origins instead."
            )
        return ["*"]
    return origins


def _get_client_ip(request: Request) -> str:
    """Extract client IP for rate limiting, considering proxies."""
    # Check X-Forwarded-For header (set by proxies/load balancers)
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # First IP in the chain is the original client
        return forwarded.split(",")[0].strip()
    # Fall back to direct client IP
    return request.client.host if request.client else "unknown"


_cors_origins = _cors_config()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-User-Id"],
)


async def _invoke(handler: Callable[[dict[str, Any], Any], dict[str, Any]], request: Request, path_params: dict[str, str] | None = None) -> Response:
    body_bytes = await request.body()
    body = body_bytes.decode("utf-8") if body_bytes else ""
    event = {
        "headers": {k: v for k, v in request.headers.items()},
        "pathParameters": path_params or {},
        "body": body,
        "rawPath": request.url.path,
        "requestContext": {"http": {"method": request.method, "path": request.url.path}},
    }
    payload = handler(event, None)
    status = int(payload.get("statusCode", 200))
    headers = payload.get("headers") or {}
    is_b64 = payload.get("isBase64Encoded", False)
    data = payload.get("body", "")
    if isinstance(data, dict):
        data = json.dumps(data)
    if is_b64:
        import base64

        raw = base64.b64decode(data)
        return Response(content=raw, status_code=status, headers=headers)
    return Response(content=data, status_code=status, headers=headers, media_type=headers.get("Content-Type"))


@app.post("/credentials/validate")
async def validate_credentials(request: Request) -> Response:
    client_ip = _get_client_ip(request)
    if not _credentials_rate_limiter.allow(client_ip):
        return Response(
            content='{"detail":"Too many requests. Please try again later."}',
            status_code=429,
            media_type="application/json",
            headers={"Retry-After": "60"},
        )
    return await _invoke(lambda_handlers.validate_credentials_handler, request)


@app.post("/jobs")
async def create_job(request: Request) -> Response:
    return await _invoke(lambda_handlers.create_job_handler, request)


@app.get("/jobs")
async def list_jobs(request: Request) -> Response:
    return await _invoke(lambda_handlers.list_jobs_handler, request)


@app.get("/jobs/{job_id}")
async def get_job(job_id: str, request: Request) -> Response:
    return await _invoke(lambda_handlers.get_job_handler, request, {"job_id": job_id})


@app.post("/jobs/{job_id}/review/accept")
async def accept_review(job_id: str, request: Request) -> Response:
    return await _invoke(lambda_handlers.accept_review_handler, request, {"job_id": job_id})


@app.get("/jobs/{job_id}/artifacts")
async def list_artifacts(job_id: str, request: Request) -> Response:
    return await _invoke(lambda_handlers.list_artifacts_handler, request, {"job_id": job_id})


@app.get("/jobs/{job_id}/artifacts.zip")
async def download_artifacts_zip(job_id: str, request: Request) -> Response:
    return await _invoke(lambda_handlers.download_artifacts_zip_handler, request, {"job_id": job_id})


@app.get("/jobs/{job_id}/artifacts/{artifact_name}")
async def read_artifact(job_id: str, artifact_name: str, request: Request) -> Response:
    return await _invoke(
        lambda_handlers.read_artifact_handler,
        request,
        {"job_id": job_id, "artifact_name": artifact_name},
    )


@app.delete("/jobs/{job_id}")
async def delete_job(job_id: str, request: Request) -> Response:
    return await _invoke(lambda_handlers.delete_job_handler, request, {"job_id": job_id})
@app.post("/auth/token")
async def auth_token(request: Request) -> Response:
    client_ip = _get_client_ip(request)
    if not _auth_rate_limiter.allow(client_ip):
        return Response(
            content='{"detail":"Too many requests. Please try again later."}',
            status_code=429,
            media_type="application/json",
            headers={"Retry-After": "60"},
        )
    return await _invoke(lambda_handlers.auth_token_handler, request)
