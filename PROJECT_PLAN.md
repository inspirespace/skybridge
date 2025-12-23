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
- FlySto aircraft lookup now tolerates `tail-number` vs `tailNumber` keys for assignment.

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

## Backlog / Ideas
- Replace FlySto UI automation with API client.
- Add pricing/billing scaffolding for SaaS.
