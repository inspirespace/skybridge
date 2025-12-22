# Project Context

## Goal
Build a Dockerized CLI to migrate flights from CloudAhoy to FlySto with minimal local dependencies. Long-term goal is a hosted SaaS offering with billing.

## Current Status
- CLI wiring and migration flow exist with CloudAhoy API + FlySto web upload (hybrid mode).
- Docker image runs the CLI (`python -m src.cli`).
- Config uses env vars and `.env` via Docker `--env-file`.
- Web automation mode (Playwright) is implemented for login/export/upload when APIs are unknown.
- Discovery mode writes endpoint hints to `data/discovery/discovery.json`.
- CloudAhoy JSON APIs discovered: `t-flights.cgi` and `t-debrief.cgi` (full flight data incl. KML).
- FlySto upload UI: `/logs` → `Load logs` → `Browse files`.
- Review gating: non-dry-run uploads require a review manifest (`--review` or auto) and `--approve-import`.
- Review manifests now include `flt.points` schema + preview and exports are CSV by default.
- Hybrid mode uses the web UI to page through CloudAhoy flights (`Load more`) and uses API for flight detail fetch.

## Required API Details
These are needed to complete the adapters:
- CloudAhoy: auth method, flight list endpoint, pagination, flight detail export format, rate limits.
- FlySto: auth method, flight upload endpoint, accepted payload formats (e.g., GPX/IGC/CSV/JSON), rate limits, dedupe keys.
See placeholder contracts in `docs/cloudahoy-api.md` and `docs/flysto-api.md`.

## Assumptions (until docs arrive)
- Auth uses API keys in headers.
- Listing returns a unique flight id and timestamp.
- Upload accepts a single flight payload per request.

## State Tracking
- A local SQLite DB (default `data/migration.db`) tracks per-flight migration status to avoid duplicates.
- Successful migrations are skipped unless `--force` is provided.
- Browser storage state is persisted under `data/` to reuse sessions.

## Next Steps
1) Replace FlySto UI upload with API client if available.
2) Add a conversion step from CloudAhoy points to GPX/CSV/IGC for richer trajectories.
3) Add SaaS multi-tenant auth, billing, and per-user job tracking.
