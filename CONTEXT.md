# Project Context

## Goal
Build a Dockerized CLI to migrate flights from CloudAhoy to FlySto with minimal local dependencies. Long-term goal is a hosted SaaS offering with billing.

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
- Guided CLI (`--guided`) orchestrates review → import → verify/reconcile and stores a `guided.json` summary.
- Guided CLI exits cleanly on Ctrl+C without a traceback.
- CI now uses Python 3.12 and `uv sync --frozen --extra dev` to run pytest.
- Devcontainer Node feature targets the latest LTS release.
- Devcontainer post-start installs the Codex CLI via npm using the Node feature toolchain and npm-global prefix.
- Devcontainer setup now scrubs `~/.npmrc` `prefix` entries to avoid nvm prefix warnings on shell startup.
- Devcontainer post-start removes Copilot/Copilot Chat to avoid invalid-extension warnings and keep the container extension set minimal.
- CLI now prompts for missing API credentials in-memory when `.env` is absent.

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
