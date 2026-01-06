# Migrations

## 2026-01-04: CloudAhoy flight IDs use `fdID`

Skybridge now uses CloudAhoy `fdID` (UUID) as `flight_id` throughout the pipeline.
Previously, some flows relied on the CloudAhoy `key` field. Any cached review or
import artifacts that referenced the old IDs should be regenerated.

Impacted areas:
- Review/import JSON fixtures and reports
- Export paths and FlySto upload signatures
- Any custom tooling that assumes CloudAhoy `key` values

If you maintain internal datasets, re-run discovery or review generation to refresh
IDs and metadata.
