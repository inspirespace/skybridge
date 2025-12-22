# Project Plan

## Status Snapshot
- Review flow works for all flights; exports CSV from `flt.points`; metadata captured.
- Upload to FlySto uses web UI; API still unknown.
- `migration.db` now stores file/metadata hashes for idempotent skips.
- Review manifests include `review_id` and approve-import requires it.
- FlySto API investigation blocked by intermittent 503/server-error responses.

## Next Implementation Steps
1) Attach metadata to uploads
   - If FlySto supports metadata fields, map and send them.
   - Otherwise store a local sidecar for later API mapping.
2) Output format mapping
   - Confirm FlySto’s preferred structured format.
   - Map `flt.points` to that format and add tests.
3) CLI workflow polish
   - Add a safer “approved import” wrapper that logs the review ID used.
4) Hardening & tests
   - Add unit tests for pagination, parsing, and mapping.
   - Add integration tests for a small flight sample (if allowed).

## Backlog / Ideas
- Replace FlySto UI automation with API client.
- Add pricing/billing scaffolding for SaaS.
