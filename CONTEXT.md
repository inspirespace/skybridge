# Project Context

## Goal
Build a Dockerized CLI to migrate flights from CloudAhoy to FlySto with minimal local dependencies. Long-term goal is a hosted backend offering with billing.

## Current Status
- Migration uses CloudAhoy JSON APIs and FlySto API upload as the default path (web automation available but not used in auto mode).
- Review gating: uploads require a review manifest (`--review`) and `--approve-import`.
- GPX exports (with CSV sidecar) are generated from `flt.points`.
- Uploads are grouped by tail number; each tail triggers a FlySto unknown-aircraft assignment call after its batch.
- FlySto log resolution falls back to `type=all` listings when `type=flight` misses a file.
- Crew import and reconciliation use `/api/user-crew` + `/api/assign-crew`, tolerating duplicates.
- Logs receive CloudAhoy remarks with basic UTF-8 mojibake repair.
- Imported logs receive compact tags: `cloudahoy` and `cloudahoy:<timestamp>` (UTC ISO minute of the import run).
- Imports write an `import_report.json`, support a verify-only pass, and can wait for FlySto processing.
- `./scripts/run.sh` streams logs to `docker.log` per run to avoid truncation.
- Added `./scripts/run-discovery.sh`/`src.discovery_cli` to keep endpoint discovery separate from the main CLI.
- Guided CLI (`--guided`) orchestrates review → import → verify/reconcile and stores a `guided.json` summary.
- Guided CLI exits cleanly on Ctrl+C without a traceback.
- CI now uses Python 3.12 and `uv sync --frozen --extra dev` to run pytest.
- Devcontainer Node feature targets the latest LTS release.
- Devcontainer post-start installs the Codex CLI via npm using the Node feature toolchain and npm-global prefix.
- Devcontainer setup now scrubs `~/.npmrc` `prefix` entries to avoid nvm prefix warnings on shell startup.
- Devcontainer post-start removes Copilot/Copilot Chat to avoid invalid-extension warnings and keep the container extension set minimal.
- Devcontainer adds the GitHub CLI feature for authenticated GitHub actions from the container.
- Devcontainer exports the nvm Node bin path and installs Codex zsh completions automatically.
- Devcontainer installs the Oh My Zsh `zsh-autosuggestions` plugin for inline shell suggestions.
- Devcontainer mounts `/home/vscode/.config/gh` to a named volume so GitHub CLI auth persists across container restarts.
- Devcontainer disables zsh-autosuggestions to avoid duplicated paste input in the terminal.
- CLI now prompts for missing API credentials in-memory when `.env` is absent.
- Added a detailed backend architecture planning checklist to `PROJECT_PLAN.md` (Playwright excluded for production).
- Added Terraform scaffolding under `infra/terraform/` with a CI `terraform fmt` check; Milestone 2 in progress.
- Added dev backend API scaffold under `src/backend/` with local job storage in `data/backend/jobs` for Milestone 3.
- Added backend runbook, maintenance, and release readiness checklists under `docs/` for Milestone 4.
- Added a minimal dev web UI served at `/` to drive job creation, review, and approval locally with OIDC auth.
- Added optional HTTPS dev proxy via Caddy + mkcert for trusted local TLS on `https://skybridge.localhost`.
- Dev backend now executes real review/import flows using API clients (no credential storage), writes `review.json` and `import-report.json` under `data/backend/jobs/<job_id>/`, and the UI polls job status while background tasks run.
- Added Docker Compose stack for the backend dev web (API + worker + DynamoDB Local + MinIO).
- Added Lambda handler scaffolding in `src/backend/lambda_handlers.py` with build script output under `infra/terraform/lambda/backend-handlers.zip`.
- CloudAhoy exports can now produce ForeFlight-style CSVs via `CLOUD_AHOY_EXPORT_FORMAT=foreflight`, FlightRadar24 CSV via `CLOUD_AHOY_EXPORT_FORMAT=flightradar24`, MVP-50 CSV via `CLOUD_AHOY_EXPORT_FORMAT=mvp50`, or Garmin G3X/G1000 CSV via `CLOUD_AHOY_EXPORT_FORMAT=g3x` / `g1000`. Multiple formats can be exported via `CLOUD_AHOY_EXPORT_FORMATS` (comma-separated, defaults to `g3x,gpx`) with G3X prioritized for upload when available.
- Experimental: `CLOUD_AHOY_G3X_INCLUDE_HDG=1` opt-in to include heading in G3X exports; TRK is always included and HDG defaults off for block-time compatibility.
- FlySto uploads now capture the log-upload response (including the per-file signature hash) in a dedicated upload cache, use the hash for aircraft assignment, and keep log-list resolution separate to avoid mixing upload signatures with resolved log summaries.
- When FlySto format is missing for G3X/G1000 uploads, the assignment step now defaults the log format to `UnknownGarmin` to avoid signature-group mismatches.
- Aircraft reconciliation now prefers upload signatures (when present) and re-resolves missing signatures/formats from filenames in the import report before assigning.
- G3X exports now include a dedicated GPS ground track (TRK) column in the header while keeping HDG optional.
- G3X exports now emit a Garmin-style `#airframe_info` header and set `system_id` to the tail number to help FlySto treat each tail as a distinct log source.
- Aircraft assignment now falls back to FlySto log-metadata to resolve the log source systemId (used for UnknownGarmin grouping) when per-file signatures don't map.
- Reconcile flows now apply aircraft first, then crew, then metadata tags/remarks from the import report.
- FlySto client now auto-applies the `X-Version` header (parsed from the web bundle when needed) to avoid 404s on crew assignment endpoints.
- FlySto crew assignment now mirrors the web UI payload format (text/plain JSON) with numeric role IDs and falls back to `/api/crew?type=all` if `/api/user-crew` is empty.
- Crew reconciliation now re-resolves the current FlySto log id from the exported filename before assigning, so late log-id swaps after processing don’t drop crew.
- Crew reconciliation now verifies log metadata after assignment and retries once (with a short delay) if FlySto doesn’t persist crew immediately.
- Guided imports now reapply crew after reconciliation once the FlySto processing queue drains to defend against late post-processing clearing crew.
- Added unit tests covering G3X HDG/TRK behavior, FlySto crew payload formatting/fallback, and crew reconciliation retry with log-id refresh.
- Added tests for FlySto upload signature parsing/decoding, log-list resolution, log-metadata source extraction, and migration flow signature/system-id assignment.
- Added tests for FlySto resolve update flows, log-source cache reuse, and import-report verify/reconcile paths.

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
3) Add backend multi-tenant auth, billing, and per-user job tracking.
