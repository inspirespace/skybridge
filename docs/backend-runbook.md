# Backend Runbook (Dev/Beta)

## Purpose
Provide the minimal operational steps to run a migration job and validate outcomes.

## Workflow
1. Confirm API and worker health checks pass.
2. Create a job with CloudAhoy and FlySto credentials.
3. Monitor job state transitions:
   - `review_running` → `review_ready` → `import_running` → `completed` (or `failed`).
4. Review artifacts:
   - `review-summary.json`
   - `import-report.json`
   - export artifacts (GPX/CSV)
5. Validate job completion and artifact availability.
6. Confirm job artifacts are retained and then expire per TTL policy.

## Troubleshooting
- **Job stuck in review:** verify CloudAhoy access, check worker logs for export failures.
- **Job stuck in import:** verify FlySto access and upload queue, check retry counters.
- **Artifacts missing:** confirm S3/local storage permissions and artifact writer output.

## Escalation
- Capture job id, user id, and correlation id.
- Export relevant logs and artifact metadata before cleanup.
