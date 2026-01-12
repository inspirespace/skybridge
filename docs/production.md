# Production checklist

This checklist captures the minimum configuration required for a multi-tenant production deployment.

## Core infrastructure
- **S3 bucket** for job artifacts (reports, exports, review summaries) with lifecycle rule to delete objects after 7 days.
- **DynamoDB** tables:
  - Jobs table (partition key `user_id`, sort key `job_id`, plus GSI on `job_id`).
  - Credentials table (partition key `token`, TTL enabled).
- **SQS** queue for review/import jobs.
- **OIDC provider** (Cognito or equivalent) for auth.

## Required environment variables
- `ENV=prod`
- `AUTH_MODE=oidc`
- `AUTH_ISSUER_URL=<issuer>`
- `AUTH_BROWSER_ISSUER_URL=<issuer>` (optional, for browser-facing issuer)
- `AUTH_CLIENT_ID=<client_id>`
- `AUTH_AUDIENCE=<audience>` (optional if issuer uses `azp`, recommended)
- `AUTH_TOKEN_URL=<token_url>` (required for SPA auth token exchange)
- `BACKEND_USE_WORKER=1`
- `BACKEND_SQS_ENABLED=1`
- `SQS_QUEUE_URL=<queue_url>`
- `BACKEND_WORKER_TOKEN=<shared_token>`
- `BACKEND_DYNAMO_ENABLED=1`
- `DYNAMO_JOBS_TABLE=<jobs_table>`
- `DYNAMO_CREDENTIALS_TABLE=<credentials_table>`
- `BACKEND_S3_ENABLED=1`
- `S3_BUCKET=<bucket>`
- `S3_PREFIX=jobs`
- `S3_REGION=<region>`
- `S3_SSE=true`
- `AWS_REGION=<region>` (EU region recommended; e.g. `eu-central-1`)

## Security & retention
- S3 lifecycle rule to delete objects after 7 days (retention requirement).
- DynamoDB TTL on credentials table (`ttl_epoch`) to auto-expire tokens.
- `BACKEND_MAX_ACTIVE_JOBS` to limit per-user concurrency (default `1`).
- Optional: rate limits via `BACKEND_RATE_JOBS_PER_MIN` and `BACKEND_RATE_ACCEPT_PER_MIN`.
- S3 object keys are prefixed with user id for defense in depth.

## Workers
- API and workers must share the same `BACKEND_WORKER_TOKEN` so credentials can be claimed.
- Scale workers horizontally for parallel imports.

## Deployment notes
- Ensure API and worker share the same `AUTH_ISSUER_URL` and signing keys.
- `BACKEND_USE_WORKER=1` and `BACKEND_SQS_ENABLED=1` are required in production.
- Use HTTPS for all ingress; route `/api` to the backend and `/` to the frontend.

## Frontend build configuration
- `VITE_API_BASE_URL` should point at the API Gateway base URL (e.g. `https://<api-id>.execute-api.<region>.amazonaws.com`).
- `VITE_AUTH_MODE=oidc`
- `VITE_AUTH_ISSUER_URL` should match `AUTH_ISSUER_URL`.
- `VITE_AUTH_CLIENT_ID` should match the Cognito app client id.
- `VITE_AUTH_PROVIDER_PARAM=identity_provider` for Cognito social IdPs.
- `VITE_AUTH_REDIRECT_PATH=/app/auth/callback`
- `VITE_AUTH_LOGOUT_URL=https://<cognito-domain>.auth.<region>.amazoncognito.com/logout`
