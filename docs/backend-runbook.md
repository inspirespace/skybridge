# Backend Runbook (Dev/Beta)

## Purpose
Provide the minimal operational steps to run a migration job and validate outcomes.

## Workflow
1. Confirm API and worker health checks pass.
2. Sign in via the dev OIDC provider (Keycloak) to obtain a JWT (default dev user: `demo` / `demo-password`).
3. Create a job with CloudAhoy credentials (and optional date range/max flights).
4. Monitor job state transitions:
   - `review_queued` → `review_running` → `review_ready` → `import_queued` → `import_running` → `completed` (or `failed`).
5. Approve review by posting FlySto credentials to trigger import.
6. Review artifacts:
   - `review.json` (full manifest)
   - `review-summary.json`
   - `import-report.json`
   - export artifacts (GPX/CSV)
7. Validate job completion and artifact availability.
8. Confirm job artifacts are retained and then expire per TTL policy.

## Troubleshooting
- **Job stuck in review:** verify CloudAhoy access, check worker logs for export failures.
- **Job stuck in import:** verify FlySto access and upload queue, check retry counters.
- **Artifacts missing:** confirm S3/local storage permissions and artifact writer output.
- **HTTPS login fails:** ensure `./scripts/setup-dev-https.sh` was run and Caddy is up (https://auth.skybridge.localhost).
- **Auth provider not ready:** wait for Keycloak health to pass; the API returns `503` with `Retry-After` until JWKS is reachable.
- **Safari login fails:** enable the `/auth/token` proxy (`AUTH_TOKEN_PROXY=true`) to avoid CORS/ITP issues.

## Escalation
- Capture job id, user id, and correlation id.
- Export relevant logs and artifact metadata before cleanup.
