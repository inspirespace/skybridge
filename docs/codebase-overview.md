# Codebase Overview

This is the quickest onboarding map: where things live, how to run the stack, and the main entry points.

## Repository layout
- `src/` — application code
- `src/core/` — core migration logic + CLI
- `src/backend/` — core backend handlers + job/queue orchestration
- `src/frontend/` — Vite SPA + static pages
- `tests/` — backend tests
- `docker/` — local infra configs (HTTPS proxy, dev tooling)
- `functions/` — Firebase Functions entrypoints (2nd gen)
- `tools/inspector/` — dev-only inspection/probing scripts

## Local dev (fast path)
Requirements:
- Docker + Docker Compose
- VS Code (optional) + Dev Containers extension (optional)
- `mkcert` for local HTTPS certificates

1) `docker compose up --build` (starts Firebase emulators, API, worker, frontend, HTTPS proxy, mocks)
2) Open https://skybridge.localhost
3) Sign in using the Firebase Auth emulator popup (Google/Apple/Facebook buttons).
4) (Optional) open the Firebase emulator UI at https://emulator.skybridge.localhost.
5) If the domain does not resolve, add a hosts entry for `skybridge.localhost` and `*.skybridge.localhost` → `127.0.0.1` (macOS already resolves `*.localhost`).
6) Generate local HTTPS certs with `mkcert` (see README).

## Key entrypoints
- CLI entrypoint: `./cloudahoy2flysto` (interactive, guided migration flow).
- API handlers: `src/backend/lambda_handlers.py`
- Firebase Functions: `functions/main.py`
