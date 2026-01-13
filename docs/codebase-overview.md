# Codebase Overview

This is the quickest onboarding map: where things live, how to run the stack, and the main entry points.

## Repository layout
- `src/` — application code
- `src/core/` — core migration logic + CLI
- `src/backend/` — Lambda handlers + job/queue orchestration
- `src/frontend/` — Vite SPA + static pages
- `tests/` — backend tests
- `infra/terraform/` — AWS infrastructure
- `docker/` — local infra configs (Keycloak realm)
- `tools/inspector/` — dev-only inspection/probing scripts

## Local dev (fast path)
Requirements:
- Docker + Docker Compose
- VS Code (optional) + Dev Containers extension (optional)
- `mkcert` for local HTTPS certificates

1) `docker compose up --build` (starts API, worker, Keycloak, DynamoDB, SQS, MinIO)
2) Open https://skybridge.localhost
3) Sign in with `demo` / `demo-password`
4) If the domains do not resolve, add hosts entries for `skybridge.localhost`, `auth.skybridge.localhost`, and `storage.skybridge.localhost` → `127.0.0.1` (macOS already resolves `*.localhost`).
5) Generate local HTTPS certs with `mkcert` (see README).

## Key entrypoints
- CLI entrypoint: `./cloudahoy2flysto` (interactive, guided migration flow).
- Lambda API: `src/backend/lambda_handlers.py`
- Lambda local API emulator: `src/backend/lambda_api_local.py`
- Lambda worker: `src/backend/worker_lambda.py`
