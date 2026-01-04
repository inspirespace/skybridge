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

## Retention
- DynamoDB TTL and S3 lifecycle delete after 7 days.
- Local dev cleanup happens when listing jobs.

## Production requirements
See `docs/production.md` and `docs/backend-runbook.md`.
