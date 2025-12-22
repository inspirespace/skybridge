# Project Plan

## Status Snapshot
- Review flow works for all flights; exports CSV from `flt.points`; metadata captured.
- Upload to FlySto uses API (`/api/login`, `/api/log-upload`).
- `migration.db` now stores file/metadata hashes for idempotent skips.
- Review manifests include `review_id` and approve-import requires it.
- FlySto API base URL defaults to `https://www.flysto.net`; API version inferred from JS bundle.
- MODE defaults to `auto` and no longer falls back to web.

## Next Implementation Steps
1) Run API upload end-to-end for all flights (start with a small batch).
2) Confirm metadata mapping with FlySto (pilot, crew, remarks, tags, tail number).
3) Output format mapping
   - Confirm FlySto’s preferred structured format.
   - Map `flt.points` to that format and add tests.
4) Hardening & tests
   - Add unit tests for pagination, parsing, and mapping.
   - Add integration tests for a small flight sample (if allowed).

## Backlog / Ideas
- Replace FlySto UI automation with API client.
- Add pricing/billing scaffolding for SaaS.
