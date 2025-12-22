# Project Plan

## Status Snapshot
- Review flow works for all flights; exports CSV from `flt.points`; metadata captured.
- Upload to FlySto uses web UI; API still unknown.
- `migration.db` exists but needs stronger dedupe/retry behavior.

## Next Implementation Steps
1) Make `migration.db` authoritative
   - Store per-flight upload status, file hashes, and metadata digests.
   - Skip already uploaded flights unless `--force`.
   - Add retry/backoff for failed uploads and resumable runs.
2) Attach metadata to uploads
   - If FlySto supports metadata fields, map and send them.
   - Otherwise store a local sidecar for later API mapping.
3) Output format mapping
   - Confirm FlySto’s preferred structured format.
   - Map `flt.points` to that format and add tests.
4) CLI workflow polish
   - Enforce review manifest gating with explicit `--review-path`.
   - Provide a safer “approved import” wrapper that logs the review ID used.
5) Hardening & tests
   - Add unit tests for pagination, parsing, and mapping.
   - Add integration tests for a small flight sample (if allowed).

## Backlog / Ideas
- Replace FlySto UI automation with API client.
- Add pricing/billing scaffolding for SaaS.
