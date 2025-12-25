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
- Added a VS Code devcontainer with Playwright + Python deps and Docker socket access for local development/testing.
- Avoid duplicate exports during crew reconciliation by fetching CloudAhoy metadata only.
- Use review manifests as the source of truth for import flight lists to keep runs deterministic.
- Fix approve-import guard so matching review IDs proceed with imports.
- Latest full import run (RUN_ID 20251225T111510Z) still reports pending=1/resolved=45 after verification; investigate FlySto log resolution mismatch.
- FlySto log resolution now falls back to `type=all` log listings to eliminate missing file matches.
- CLI now writes logs to `docker.log` directly for each run.
- Added run checklist and verification script for consistent post-run validation.
- Added GitHub Actions CI workflow to run pytest on pushes to main and pull requests.
- CI now installs pytest in the workflow and runs pytest with PYTHONPATH set to the workspace to resolve src imports.
- Devcontainer usage standardized: build/run `.devcontainer/Dockerfile` image (`skybridge-dev`) for tests and CLI runs.
- Plan: add a guided, modern CLI workflow for end-to-end migrations.
- Implemented guided CLI flow with preflight checks, prompts, and rich progress output.
- Added `cloudahoy2flysto` wrapper script as the primary user-facing guided command.
- Added Makefile install/uninstall targets for the guided wrapper.
- Devcontainer improvements: pip cache mount for faster rebuilds, persistent shell history in a named volume, and permission fix on start.

## Guided CLI (planned)
Goal: provide a step-by-step, user-friendly CLI that guides through review/import/verify with clear progress, prompts, and summaries.

Planned UX flow
1) Preflight checks
   - Validate `.env` presence and required vars.
   - Test CloudAhoy/FlySto connectivity (API ping/auth).
   - Offer to continue/abort on partial failures.
2) Choose run options
   - Max flights, force reimport, wait-for-processing, run-id.
   - Mode selection (api/web/hybrid) if needed.
3) Review step
   - Generate review manifest and show summary (count, date range, tail distribution).
   - Prompt to continue with the review ID.
4) Import step
   - Live progress per flight (upload, resolve, crew, metadata).
   - Aggregate progress bar + step durations.
5) Post-run verification
   - Verify report, show missing/pending.
   - Offer optional reconciliation (crew/aircraft).
6) Final summary + next steps
   - Artifact paths, verify instructions, and FlySto UI checklist.

Implementation plan
- Add a `--guided` mode (or `skybridge guided`) entry point.
- Use `rich` for progress bars, panels, and prompts (or `questionary` for prompts if needed).
- Reuse existing CLI logic (review/import/verify) behind a small orchestrator.
- Persist run config and summary in `data/runs/<RUN_ID>/guided.json`.
- Add unit tests for the orchestrator (no network; mock clients).
- Add `rich` as a dependency for modern prompts and progress UI.
- Devcontainer now includes Codex CLI + VS Code extension and a zsh/starship prompt.

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

## Backlog / Ideas
- Replace FlySto UI automation with API client.
- Add pricing/billing scaffolding for SaaS.
