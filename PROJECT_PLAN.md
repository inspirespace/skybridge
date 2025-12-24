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
- Imported logs now get `cloudahoy` + `cloudahoy:<timestamp>` tags; CloudAhoy tags are ignored.
- Import flow now writes `data/import_report.json` for verification (per-flight status + FlySto log resolution).
- FlySto log annotations updates are write-only; tags are sent as-is.

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
   - Confirm `cloudahoy:<flight_id>` tag appears and supports duplicate detection.

## Backlog / Ideas
- Replace FlySto UI automation with API client.
- Add pricing/billing scaffolding for SaaS.
