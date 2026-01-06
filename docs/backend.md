# Backend Architecture

Location: `src/backend/`

## Runtime modes
- **Dev/local**: writes JSON artifacts under `data/backend/jobs/`.
- **Prod**: uses DynamoDB for job metadata + S3 for artifacts; work is queued in SQS.

## Key modules
- `app.py`: FastAPI API (jobs, artifacts, SSE events, auth exchange).
- `service.py`: Job orchestration – review generation and import execution.
- `worker.py`: SQS-driven worker entrypoint.
- `store.py`: Job persistence layer (filesystem + DynamoDB + S3).
- `credential_store.py`: Short-lived encrypted credentials (memory or DynamoDB).
- `object_store.py`: S3 object storage adapter.

## API surface
- `POST /auth/token` – OIDC code exchange (PKCE flow).
- `GET /jobs` – list jobs for current user.
- `POST /jobs` – create job and enqueue review.
- `GET /jobs/{id}` – fetch job status + summary.
- `DELETE /jobs/{id}` – delete a specific job (and artifacts).
- `DELETE /jobs` – delete all jobs for user (single-run cleanup).
- `GET /jobs/{id}/events` – SSE updates.
- `POST /jobs/{id}/review/accept` – accept review, enqueue import.
- `GET /jobs/{id}/artifacts.zip` – download all artifacts.

## Job lifecycle
1. `POST /jobs`
   - Stores job metadata
   - Stores credentials with TTL
   - Queues review job in SQS
2. Review runs
   - CloudAhoy data pulled
   - Summary generated and stored as `review.json`
   - Status: `review_ready`
3. `POST /jobs/{id}/review/accept`
   - Validates review state
   - Queues import job
4. Import runs
   - FlySto API writes
   - Import report stored as `import_report.json`
   - Status: `completed`

## SSE progress
- `GET /jobs/{id}/events` streams job updates.
- UI subscribes while job is running; polling is fallback.

## Auth & user isolation
- Requests are authenticated via OIDC in prod or a dev header in local mode.
- All job data is scoped by `user_id` derived from the access token.
- S3 object keys are prefixed by user id for defense in depth.

## Rate limits / concurrency
- `BACKEND_MAX_ACTIVE_JOBS` limits per-user concurrent jobs.
- Optional rate limits on `/jobs` and `/jobs/{id}/review/accept`.

## Retention
- DynamoDB TTL and S3 lifecycle delete after 7 days.
- Local dev cleanup happens when listing jobs.

## Production requirements
See `docs/production.md` and `docs/backend-runbook.md`.
