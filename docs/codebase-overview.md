# Codebase Overview

Skybridge is split into three major parts:

- `src/core/`: Python CLI + migration logic (CloudAhoy → FlySto), shared by backend/worker.
- `src/backend/`: FastAPI API + worker orchestration and storage adapters.
- `src/frontend/`: React/Vite UI implementing the wireframe.

## High-level flow
1. User signs in (OIDC or dev header).
2. UI posts `/jobs` with credentials + filters.
3. Backend stores job + credentials, queues work (SQS) or runs locally.
4. Worker generates review summary + artifacts.
5. User accepts import → `/jobs/{id}/review/accept`.
6. Worker imports to FlySto, writes reports + artifacts.
7. UI streams job updates via SSE `/jobs/{id}/events` (poll fallback).

## Data storage & retention
- Local dev: JSON files under `data/backend/jobs/<job_id>/`.
- Prod: S3 for artifacts (user-scoped prefix), DynamoDB for job metadata.
- Retention: 7-day TTL (S3 lifecycle in prod; TTL column in DynamoDB).

## Documentation index
- `docs/backend-architecture.md` – backend architecture overview.
- `docs/backend-runbook.md` – operational guide.
- `docs/production.md` – production deployment notes.
- `docs/cloudahoy-api.md` / `docs/flysto-api.md` – API notes.
- `docs/core-cli.md` (added) – CLI and core logic.
- `docs/frontend.md` (added) – UI architecture.
- `docs/backend.md` (added) – API/worker/store details.
- `docs/testing.md` (added) – test strategy and commands.
