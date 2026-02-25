"""Firebase Functions (2nd gen) entrypoints."""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable

from firebase_functions import https_fn, pubsub_fn, scheduler_fn, options
from flask import Request, Response

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from src.backend import lambda_handlers  # noqa: E402
from src.backend.env import resolve_project_id, resolve_region  # noqa: E402

options.set_global_options(
    region=resolve_region()
)

_ROUTES: list[tuple[str, re.Pattern[str], Callable]] = []


def _route(method: str, pattern: str, handler: Callable) -> None:
    compiled = re.compile(pattern)
    _ROUTES.append((method.upper(), compiled, handler))


def _register_routes() -> None:
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


def _cors_headers() -> dict[str, str]:
    raw = os.getenv("CORS_ALLOW_ORIGINS") or "https://skybridge.localhost"
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    if not origins:
        origins = ["https://skybridge.localhost"]
    allow_origin = "*" if "*" in origins else origins[0]
    return {
        "Access-Control-Allow-Origin": allow_origin,
        "Access-Control-Allow-Methods": "GET,POST,DELETE,OPTIONS",
        "Access-Control-Allow-Headers": "Authorization,Content-Type,X-User-Id",
    }


def _normalize_path(request: Request) -> str:
    path = request.path or "/"
    if path.startswith("/api/"):
        return path[len("/api") :]
    if path == "/api":
        return "/"
    return path


def _invoke(
    handler: Callable[[dict[str, Any], Any], dict[str, Any]],
    request: Request,
    path_params: dict[str, str] | None = None,
) -> Response:
    body = request.get_data(as_text=True) or ""
    event = {
        "headers": {k: v for k, v in request.headers.items()},
        "pathParameters": path_params or {},
        "body": body,
        "rawPath": request.path,
        "requestContext": {"http": {"method": request.method, "path": request.path}},
    }
    payload = handler(event, None)
    status = int(payload.get("statusCode", 200))
    headers = payload.get("headers") or {}
    is_b64 = payload.get("isBase64Encoded", False)
    data = payload.get("body", "")
    headers = {**headers, **_cors_headers()}
    if isinstance(data, dict):
        data = json.dumps(data)
    if is_b64:
        import base64

        raw = base64.b64decode(data)
        return Response(response=raw, status=status, headers=headers)
    return Response(response=data, status=status, headers=headers)


_register_routes()


@https_fn.on_request()
def api(request: Request) -> Response:
    if request.method == "OPTIONS":
        return Response(status=204, headers=_cors_headers())
    method = request.method.upper()
    path = _normalize_path(request)
    for route_method, pattern, handler in _ROUTES:
        if route_method != method:
            continue
        match = pattern.match(path)
        if not match:
            continue
        return _invoke(handler, request, match.groupdict())
    return Response(response=json.dumps({"detail": "Not found"}), status=404, headers=_cors_headers())


@pubsub_fn.on_message_published(topic=os.getenv("PUBSUB_TOPIC") or "skybridge-job-queue")
def worker(event: pubsub_fn.CloudEvent[pubsub_fn.MessagePublishedData]) -> None:
    message = event.data.message
    payload = message.data
    if not payload:
        return
    import base64

    try:
        decoded = base64.b64decode(payload).decode("utf-8")
        data = json.loads(decoded)
    except Exception:
        return
    lambda_handlers._process_queue_payload(data)
    _route("POST", r"^/auth/token$", lambda_handlers.auth_token_handler)


@scheduler_fn.on_schedule(schedule="every 24 hours")
def cleanup_expired(_event: scheduler_fn.ScheduledEvent) -> None:
    # Cleanup job records (Firestore or local).
    try:
        lambda_handlers.store.cleanup_expired()
    except Exception:
        pass
    if (os.getenv("BACKEND_FIRESTORE_ENABLED") or "false").lower() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return
    from google.cloud import firestore

    project_id = resolve_project_id()
    client = firestore.Client(project=project_id or None)
    now = int(time.time())
    collections = [
        os.getenv("FIRESTORE_JOBS_COLLECTION") or "skybridge-jobs",
        os.getenv("FIRESTORE_CREDENTIALS_COLLECTION") or "skybridge-credentials",
    ]
    for name in collections:
        for doc in client.collection(name).where("ttl_epoch", "<", now).stream():
            doc.reference.delete()
