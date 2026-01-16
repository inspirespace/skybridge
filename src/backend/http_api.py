"""HTTP API for Cloud Run (maps requests to Lambda handlers)."""
from __future__ import annotations

import json
import os
from typing import Any, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from . import lambda_handlers

app = FastAPI(title="Skybridge API")

origins = [origin.strip() for origin in (os.getenv("CORS_ALLOW_ORIGINS") or "*").split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins != ["*"] else ["*"],
    allow_credentials=True,
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
    return await _invoke(lambda_handlers.auth_token_handler, request)

