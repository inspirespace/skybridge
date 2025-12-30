# Project Plan

## Status Snapshot
- Added per-file aircraft assignment using FlySto log-list/log-summary to map filename to signature.
- FlySto field ingestion experiment pending: CSV-only accepted, GPX+CSV/GPX+JSON failed; need log list endpoint to verify field visibility.
- Review flow works for all flights; exports GPX from `flt.points` (CSV retained); metadata captured; 46 flights imported on 2025-12-22.
- Upload to FlySto uses API (`/api/login`, `/api/log-upload`).
- `migration.db` now stores file/metadata hashes for idempotent skips.
- Review manifests include `review_id` and approve-import requires it.
- FlySto API base URL defaults to `https://www.flysto.net`; API version inferred from JS bundle.
- MODE defaults to `auto` and no longer falls back to web.
- Blocker: FlySto "Other" aircraft model creation — UI reaches manual profile step but no create-aircraft request captured; direct /api/create-aircraft attempts return 500.
- Crew import wiring added (create crew via `/api/new-crew`, assign via `/api/assign-crew`, map roles from `/api/user-crew-roles`) but requires validation against live API.
- FlySto client adds basic rate limiting + retry to reduce request bursts and handle transient outages.
- Crew extraction now forces PIC when CloudAhoy marks PIC or uses PIC role strings; FlySto role resolution prioritizes PIC candidates.
- Crew mapping updated: CloudAhoy "safety pilot" maps to FlySto "copilot"; if CloudAhoy provides only "pilot" without PIC, it becomes PIC.
- FlySto aircraft lookup now tolerates `tail-number` vs `tailNumber` keys for assignment.
- Local 5-flight import via direct Python succeeded (review-id gating), pending UI verification of crew roles/aircraft assignment.
- Aircraft assignment now retries longer and refreshes log summaries before giving up.
- Regression: uploads using `@@@<tail>` in URL/zip entry do not appear as flights; legacy `@@@0` with plain filename does. Reverted to legacy upload while focusing on assignment API.
- Playwright capture blocked on macOS due to Crashpad permission errors; need manual network capture or alternate environment.
- Align assign-aircraft request with UI (text/plain JSON body + x-version).
- Group uploads by tail number and assign unknown GPX groups per tail after uploads.
- Prevent caching of unknown-group assignments (systemId=None) so each tail can be assigned.
- Added offline unit tests for tail grouping and assign-aircraft caching behavior.
- CloudAhoy remarks map to FlySto log annotations (with mojibake repair).
- Imported logs now get `cloudahoy` + `cloudahoy:<timestamp>` tags using the import-run timestamp; CloudAhoy tags are ignored.
- Import flow now writes `data/import_report.json` for verification (per-flight status + FlySto log resolution).
- Verify-only mode and timestamped logging added to improve long-run visibility.
- FlySto log annotations updates are write-only; tags are sent as-is.
- FlySto log resolution now caches per filename within a run to avoid repeating long polling waits for crew/metadata after aircraft assignment.
- Resolve FlySto log details once per flight after upload and reuse for aircraft/crew/metadata assignment to avoid extra polling.
- Report FlySto processing queue size and pending log count to explain why UI may be empty during ingestion.
- Add wait-for-processing option to block until FlySto ingestion finishes, then verify and reconcile aircraft.
- Reconcile crew assignments after ingestion using stored report data or review metadata.
- Run Docker detached in `scripts/run.sh` and stream logs to avoid truncated output for long runs.
- Added `scripts/run-discovery.sh`/`src.discovery_cli` to keep discovery separate from the main CLI.
- Added a VS Code devcontainer with Playwright + Python deps and Docker socket access for local development/testing.
- Avoid duplicate exports during crew reconciliation by fetching CloudAhoy metadata only.
- Use review manifests as the source of truth for import flight lists to keep runs deterministic.
- Fix approve-import guard so matching review IDs proceed with imports.
- Latest full import run (RUN_ID 20251225T111510Z) still reports pending=1/resolved=45 after verification; investigate FlySto log resolution mismatch.
- FlySto log resolution now falls back to `type=all` log listings to eliminate missing file matches.
- CLI now writes logs to `docker.log` directly for each run.
- Added run checklist and verification script for consistent post-run validation.
- Added GitHub Actions CI workflow to run pytest on pushes to main and pull requests.
- CI now uses Python 3.12 and `uv sync --frozen --extra dev` before running pytest.
- Implemented guided CLI flow with preflight checks, prompts, and rich progress output.
- Added `cloudahoy2flysto` wrapper script as the primary user-facing guided command.
- Added Makefile install/uninstall targets for the guided wrapper.
- Devcontainer improvements: persistent shell history in a named volume, and permission fix on start.
- Devcontainer updates: starship config to avoid prompt scan timeouts; VS Code pytest discovery settings added.
- Migrated dependency management to `uv` with `pyproject.toml` and `uv.lock` (dev deps via `--extra dev`).
- Devcontainer now uses the `base` Dockerfile stage (features handle extra tooling).
- Devcontainer now points VS Code to `/opt/venv/bin/python` and enables pytest discovery.
- Devcontainer mounts a named volume for Codex login persistence at `/home/vscode/.codex`.
- Devcontainer PATH now includes `/home/vscode/.npm-global/bin` for the Codex CLI.
- Added optional ForeFlight-style CSV export for CloudAhoy (`CLOUD_AHOY_EXPORT_FORMAT=foreflight`).
- Added optional FlightRadar24 CSV export for CloudAhoy (`CLOUD_AHOY_EXPORT_FORMAT=flightradar24`).
- Added optional MVP-50 CSV export for CloudAhoy (`CLOUD_AHOY_EXPORT_FORMAT=mvp50`).
- Added optional Garmin G3X/G1000 CSV exports for CloudAhoy (`CLOUD_AHOY_EXPORT_FORMAT=g3x` / `g1000`).
- Added multi-export support via `CLOUD_AHOY_EXPORT_FORMATS` (comma-separated, default `g3x,gpx`), with G3X preferred for upload.
- CLI now prompts for missing API credentials in-memory when `.env` is absent.
- Experiment: `CLOUD_AHOY_G3X_INCLUDE_HDG=1` opt-in to include heading in G3X exports; TRK is always included and HDG defaults off for block-time compatibility.
- Use FlySto log-upload response signature hash/log id for aircraft assignment (stored in a dedicated upload cache and reported separately) before falling back to log-list resolution (helps G3X UnknownGarmin cases without poisoning resolution).
- Default G3X/G1000 assignment to `UnknownGarmin` when FlySto does not report a format, keeping signature grouping consistent for aircraft assignment.
- Reconcile aircraft using filename-based resolution when report signatures/formats are missing.
- Add a dedicated TRK column to G3X exports while keeping HDG optional.
- Align G3X `#airframe_info` header with Garmin format and set `system_id` from tail to help FlySto avoid UnknownGarmin grouping.
- Fall back to `/api/log-metadata` to capture the UnknownGarmin `systemId` for aircraft assignment when log summaries don’t expose it.
- Add a metadata reconciliation pass (tags/remarks) and run reconciliation in aircraft → crew → metadata order.
- Ensure FlySto API requests include the `X-Version` header (parsed from the JS bundle) so crew assignments don’t 404.
- Align FlySto crew assignment payloads to the web UI (text/plain JSON + numeric role IDs) and fall back to `/api/crew?type=all` when `/api/user-crew` returns empty.
- Re-resolve FlySto log ids by filename during crew reconciliation to handle post-processing log id swaps.
- Verify crew annotations after reconciliation and retry once if FlySto doesn’t persist crew immediately.
- Reapply crew after guided reconciliation once FlySto processing drains to avoid late FlySto processing clearing crew.
- Added tests for crew payload formatting/fallback, G3X HDG/TRK behavior, and reconciliation retry with log-id refresh.
- Added tests for FlySto signature parsing/decoding, log-list resolution, log-metadata source extraction, and migration flow signature/system-id assignment.
- Added tests for FlySto resolve update flows, log-source cache reuse, and import-report verify/reconcile paths.

## Next Implementation Steps
1) Capture FlySto create-aircraft request for "Other" model (complete UI wizard to final submit; identify endpoint/payload).
2) Validate crew role mapping coverage (PIC/Student/Instructor/etc.) and verify crew assignment shows on logs.
3) Confirm metadata mapping coverage (remarks/tail number) and aircraft assignment.
4) Decide whether to persist raw CloudAhoy payloads for audit/replay.
5) Output format mapping
   - Confirm FlySto’s preferred structured format.
   - Map `flt.points` to that format and add tests.
6) Hardening & tests
   - Add unit tests for pagination, parsing, and mapping.
   - Add integration tests for a small flight sample (if allowed).
   - Extend tests to cover crew mapping and metadata extraction edge cases.
7) Remarks + import tagging
   - Validate in UI that remarks/tags are visible on logs.

## Backend Architecture Planning (in progress)
Goal: Deliver a fully functional web application where any user can migrate CloudAhoy flights into FlySto. The architecture must be single-cloud, secure, maintainable, privacy-focused (no credential storage), and cost-friendly for early free-tier usage. The production path excludes Playwright.

Reference doc: `docs/backend-architecture.md` (authoritative architecture + milestone definitions).

- [x] 1) Define the target single-cloud baseline (AWS by default)
  - [x] Confirm region strategy (single region for early stage).
  - [x] Document core managed services (API Gateway, Lambda, Step Functions, DynamoDB, S3, CloudWatch, Cognito).
  - [x] Decide if any container runtime is needed for API-only migrations (goal: Lambda-only).
- [x] 2) Specify the data privacy model (no credential storage)
  - [x] Describe in-memory credential handling (credentials accepted per job, used transiently, never stored).
  - [x] Define encrypted-in-transit requirements (TLS, optional client-side encryption).
  - [x] Clarify retention windows for job artifacts and logs (TTL policy).
- [x] 3) Define job orchestration and data lifecycle
  - [x] Document job states and transitions (created → running → completed/failed).
  - [x] Define artifact storage paths and metadata schema (S3 keys, DynamoDB tables).
  - [x] Add S3 lifecycle/TTL cleanup policy and DynamoDB TTL field usage.
- [x] 4) API design and frontend integration
  - [x] Draft minimal REST endpoints (create job, list jobs, job status, download artifacts).
  - [x] Define authentication flow and session handling (Cognito).
  - [x] Sketch the minimal UI pages (sign-in, job creation, job status).
- [x] 5) Observability & auditability
  - [x] Define structured logging format and correlation IDs.
  - [x] List required metrics (job duration, failures, volume).
  - [x] Document audit log retention policy.
- [x] 6) Security posture & threat model
  - [x] Enumerate threats (credential exposure, data leakage, unauthorized access).
  - [x] Define mitigations (least privilege IAM, encryption at rest/in transit, short TTL).
  - [x] Document incident response basics (revocation, log review).
- [x] 7) Cost controls and free-tier strategy
  - [x] Set quotas/limits per account (jobs/day, max flights).
  - [x] Add guardrails for API usage and storage growth.
  - [x] Define alerting thresholds for budget overages.
- [x] 8) Implementation milestones (non-code planning)
  - [x] Prepare an infra diagram description (single-cloud layout).
  - [x] Produce a minimal runbook (how to run a job end-to-end).
  - [x] Draft a maintenance checklist (dependencies, security updates).
  - [x] Define a readiness checklist for a public web release (UX flow, auth, migrations working for any user).
- [x] 9) Local development experience
  - [x] Define a Docker Compose-based stack for local dev (UI + API + worker + local data stores).
  - [x] Document local auth approach (Cognito emulator or dev-only JWT bypass).

### Milestones & Review Cadence
- Milestone 1: Backend architecture baseline documented (complete).
  - Deliverables: architecture overview, data privacy model, job lifecycle, API + UI shape, observability, security, cost controls, runbook, maintenance, readiness checklist.
  - Review/feedback: **Approved** — proceeding to Milestone 2.
- Milestone 2: Infra-as-code scaffolding (in progress).
  - Deliverables: CDK/Terraform skeleton with core services, CI hook, environment config.
  - Status: Terraform scaffold under `infra/terraform/` + GitHub Actions fmt check added, API Gateway → Lambda routes wired to handler zip.
  - Review/feedback: to be scheduled once scaffolding exists.
- Milestone 3: Dev workflow (in progress).
  - Deliverables: basic auth, job orchestration, review → import flow, artifacts downloadable.
  - Status: Dev FastAPI scaffold in `src/backend/` with local job storage in `data/backend/jobs`, minimal web UI, and Docker Compose stack.
- Milestone 4: Public beta readiness (in progress).
  - Deliverables: runbook, maintenance checklist, readiness checklist, guardrails validated.
  - Status: added `docs/backend-runbook.md`, `docs/backend-maintenance.md`, `docs/backend-release-readiness.md`.

## Backlog / Ideas
- Replace FlySto UI automation with API client.
- Add pricing/billing scaffolding for the backend.
