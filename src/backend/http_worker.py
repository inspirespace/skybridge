"""HTTP worker for Cloud Run Pub/Sub push."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from . import lambda_handlers

app = FastAPI(title="Skybridge Worker")


@app.post("/pubsub")
async def pubsub_push(request: Request) -> JSONResponse:
    payload = await request.json()
    result = lambda_handlers.pubsub_worker_handler(payload)
    return JSONResponse(result)
