# Project Plan

## Status Snapshot
- Review flow works for all flights; exports GPX from `flt.points` (CSV retained); metadata captured; 46 flights imported on 2025-12-22.
- Upload to FlySto uses API (`/api/login`, `/api/log-upload`).
- `migration.db` now stores file/metadata hashes for idempotent skips.
- Review manifests include `review_id` and approve-import requires it.
- FlySto API base URL defaults to `https://www.flysto.net`; API version inferred from JS bundle.
- MODE defaults to `auto` and no longer falls back to web.

## Next Implementation Steps
1) Confirm metadata mapping coverage (pilot/crew/remarks/tail number).
2) Decide whether to persist raw CloudAhoy payloads for audit/replay.
3) Output format mapping
   - Confirm FlySto’s preferred structured format.
   - Map `flt.points` to that format and add tests.
4) Hardening & tests
   - Add unit tests for pagination, parsing, and mapping.
   - Add integration tests for a small flight sample (if allowed).

## Backlog / Ideas
- Replace FlySto UI automation with API client.
- Add pricing/billing scaffolding for SaaS.
