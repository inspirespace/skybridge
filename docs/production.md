# Production essentials

This is a checklist of what production needs, not a step-by-step deployment guide.

## Required AWS resources
- **S3 bucket** for job artifacts (add a lifecycle rule; 7 days suggested).
- **DynamoDB** tables:
  - Jobs table: partition key `user_id`, sort key `job_id`, GSI on `job_id`.
  - Credentials table: partition key `token` with TTL enabled.
- **SQS** queue for review/import jobs.
- **OIDC provider** (Cognito or equivalent) for auth.

## Required backend environment
- `ENV=prod`
- `AUTH_MODE=oidc`
- `AUTH_ISSUER_URL=<issuer>`
- `AUTH_BROWSER_ISSUER_URL=<issuer>` (optional)
- `AUTH_CLIENT_ID=<client_id>`
- `AUTH_TOKEN_URL=<token_url>`
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
- `AWS_REGION=<region>`

## Frontend build configuration
- `VITE_API_BASE_URL` points at the API Gateway base URL.
- `VITE_AUTH_MODE=oidc`
- `VITE_AUTH_ISSUER_URL` matches `AUTH_ISSUER_URL`.
- `VITE_AUTH_CLIENT_ID` matches the OIDC client id.
- `VITE_AUTH_REDIRECT_PATH=/app/auth/callback`
- `VITE_AUTH_LOGOUT_URL` points at the IdP logout endpoint.
