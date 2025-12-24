# Project Context

## Goal
Build a Dockerized CLI to migrate flights from CloudAhoy to FlySto with minimal local dependencies. Long-term goal is a hosted SaaS offering with billing.

## Current Status
- Auto-assigns aircraft per uploaded file by matching FlySto log summary filename and using file signature as systemId.
- Auto-assigns FlySto aircraft to GenericGpx logs via /api/assign-aircraft after upload.
- Experiments: CSV-only zip upload returns 200; GPX+CSV and GPX+JSON zip uploads return 500; log list endpoints still unclear (no log IDs visible via API yet).
- All 46 flights imported into FlySto on 2025-12-22 via API upload (GPX zipped).
- CLI wiring and migration flow exist with CloudAhoy API + FlySto API upload (default).
- Docker image runs the CLI (`python -m src.cli`).
- Config uses env vars and `.env` via Docker `--env-file` (MODE defaults to `auto`).
- Web automation mode (Playwright) is available but not used in auto mode.
- Discovery mode writes endpoint hints to `data/discovery/discovery.json`.
- CloudAhoy JSON APIs discovered: `t-flights.cgi` and `t-debrief.cgi` (full flight data incl. `flt.points`).
- Review gating: non-dry-run uploads require a review manifest (`--review` or auto) and `--approve-import`.
- Review manifests now include `flt.points` schema + preview and exports are GPX by default (CSV sidecar retained) and creates FlySto aircraft by tail number.
- Hybrid mode uses the web UI to page through CloudAhoy flights (`Load more`) and uses API for flight detail fetch.
- FlySto API endpoints discovered via UI: `/api/login` (text/plain JSON body) and `/api/log-upload?id=<filename>@@@0` with `content-type: application/zip`. `x-version` is inferred from the JS bundle if not provided.
- Crew assignment endpoints discovered in FlySto bundle: `/api/assign-crew` (logIds + names + roles) and `/api/user-crew` + `/api/user-crew-roles`. Crew import wiring added in `src/migration.py` and `src/flysto/client.py` (creates crew via `/api/new-crew`, assigns per log after upload).
- Crew extraction now prefers PIC when CloudAhoy flags PIC or uses a PIC role string; FlySto role resolution now prioritizes PIC candidates for flagged pilots.
- FlySto API calls now include basic rate limiting and retry on transient 429/5xx to avoid request bursts.
- FlySto aircraft lookup now matches both `tail-number` and `tailNumber` payload keys for assignment.
- Aircraft assignment now waits longer for log processing and refreshes log summaries (`update=true`) before giving up.
- Playwright automation currently fails to launch Chromium/Chrome on macOS due to Crashpad permission errors; need manual capture or different environment.
- Regression investigation: uploads with `@@@<tail>` in URL or zip entry do not show up in `log-summary`/flights, while legacy `@@@0` with plain filename does. Reverted to legacy upload format while fixing assignment via log-summary.
- FlySto assign-aircraft now uses `text/plain;charset=UTF-8` JSON body and includes `x-version`, matching the UI request.
- Crew mapping updated: CloudAhoy "safety pilot" maps to FlySto "copilot"; if CloudAhoy provides only "pilot" without PIC, it becomes PIC.
- Latest local run (direct Python) succeeded: 5/5 flights imported with review-id gating on 2025-12-23.
- Aircraft model "Other": UI wizard reaches manual profile step (model name/engine/fuel etc.) but no create-aircraft API request observed; direct /api/create-aircraft attempts return 500. Need to capture final payload or determine endpoint.
- Discovery logs now redact credentials in stored request payloads.
- Uploads are now grouped by tail number and each tail triggers a FlySto unknown-aircraft assignment call after its batch (GenericGpx, systemId=None).
- FlySto assign-aircraft caching skips only known systemIds; unknown-group assignments are allowed per tail.
- Added offline tests for tail-grouped migration behavior and assign-aircraft caching rules.
- CloudAhoy remarks are applied to FlySto logs with UTF-8 mojibake repair for common cases.
- Imported logs receive compact tags: `cloudahoy` and `cloudahoy:<timestamp>` using the import run timestamp (UTC ISO minute). CloudAhoy tags are ignored.
- Imports now write `data/import_report.json` with per-flight status and FlySto log resolution details for verification.
- Added a verify-only mode to re-resolve FlySto log IDs and update the import report, plus timestamped logging with per-flight durations.
- FlySto log annotations updates use `PUT /api/log-annotations/{logIdString}` (write-only) without merging existing tags.

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
1) Confirm crew role mapping via `/api/user-crew-roles` (PIC/Student/Instructor/etc.) and validate assignments show up on FlySto logs.
2) Decide whether to persist raw CloudAhoy payloads for audit/replay.
3) Add SaaS multi-tenant auth, billing, and per-user job tracking.
