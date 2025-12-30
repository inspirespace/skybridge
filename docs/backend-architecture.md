# Backend Architecture Plan

## Goal
Deliver a single-cloud (AWS) web application that lets any user migrate CloudAhoy flights into FlySto. The service must be secure, privacy-focused (no credential storage), maintainable, and cost-friendly for early free-tier usage. Production uses API-only workflows (no Playwright).

## Milestones

### Milestone 1: Architecture Baseline (complete)
**Outcome:** Core architecture, data privacy model, job lifecycle, API/UI shape, observability, security posture, cost controls, and operational checklists defined.

### Milestone 2: Infrastructure Scaffolding (in progress)
**Outcome:** IaC skeleton (CDK or Terraform), environment config, CI hooks, and staging environment with non-prod resources.
**Status:** Terraform scaffold added in `infra/terraform/` with a GitHub Actions fmt check.

### Milestone 3: Dev Workflow (in progress)
**Outcome:** Auth + job orchestration wired end-to-end with a limited migration flow; artifacts downloadable; operational logs and metrics available.
**Status:** Dev API scaffold added in `src/backend/` with local artifact storage under `data/backend/jobs`.

### Milestone 4: Public Beta Readiness (in progress)
**Outcome:** Guardrails, quotas, and readiness checklist satisfied; runbook and maintenance checklist validated.
**Status:** Runbook + maintenance + readiness checklists added under `docs/`.

## Architecture Overview (AWS Single-Region)
- **Region:** Single region (early-stage) with multi-AZ by default services.
- **API Layer:** API Gateway (REST or HTTP) → Lambda (or Step Functions + Lambda workers).
- **Execution model:** Serverless-first (Lambda + Step Functions). Container workloads are optional only for local dev or future heavy compute, not required for the dev workflow.
- **Auth:** Cognito User Pools + Hosted UI for sign-in; short-lived JWTs for API access.
- **Job Orchestration:** Step Functions to coordinate the migration pipeline (create job, run migration, post-process, finalize).
- **Data Storage:**
  - **DynamoDB** for job metadata, state machine transitions, and job result index.
  - **S3** for job artifacts (review manifests, logs, exports, import report).
- **Observability:** CloudWatch Logs + Metrics, optional X-Ray for tracing.

## Data Privacy Model
- **No credential storage:** CloudAhoy/FlySto credentials are provided per job and used transiently in-memory by worker Lambdas.
- **In-transit encryption:** TLS everywhere; optional client-side encryption for sensitive payload fields (future enhancement).
- **At-rest encryption:** DynamoDB and S3 encrypted with AWS-managed KMS keys by default.
- **Retention policy:**
  - Job artifacts in S3 expire via lifecycle rules (e.g., 30 days).
  - DynamoDB items have TTL fields (e.g., 30–90 days depending on billing tier).

## Job Orchestration & Data Lifecycle
**Job states:** `created → queued → running → post_processing → completed` or `failed`.

**DynamoDB schema (example):**
- Partition key: `user_id`
- Sort key: `job_id`
- Attributes: `status`, `created_at`, `updated_at`, `artifact_prefix`, `error_summary`, `ttl_epoch`.

**S3 layout:**
- `s3://<bucket>/jobs/<user_id>/<job_id>/review/`
- `s3://<bucket>/jobs/<user_id>/<job_id>/exports/`
- `s3://<bucket>/jobs/<user_id>/<job_id>/reports/`
- `s3://<bucket>/jobs/<user_id>/<job_id>/logs/`

## API Design
**Minimal endpoints:**
- `POST /jobs` → create a job (includes credentials in request body; never stored).
- `GET /jobs` → list user jobs.
- `GET /jobs/{job_id}` → job status and metadata.
- `GET /jobs/{job_id}/artifacts` → list artifact keys.
- `GET /jobs/{job_id}/artifacts/{artifact_key}` → presigned URL to download.
- `POST /jobs/{job_id}/review/accept` → user approves review and triggers import.

**Auth:**
- Cognito Hosted UI for sign-in.
- API Gateway authorizer validates JWTs.

## UI Pages
- **Sign-in** (Cognito Hosted UI).
- **Job Create** (credentials form + date range + options).
- **Review & Approve** (show review summary, per-flight table, approve CTA).
- **Job Status** (progress timeline, artifacts list, logs summary).

## User Journey (Experience-First)
1. **User visits skybridge website** and signs in.
2. **Create migration job:** user enters CloudAhoy + FlySto credentials, date range, and options.
3. **Review step:** service fetches CloudAhoy data and produces a review summary including:
   - Total flights, total hours, earliest/latest dates.
   - Per-flight list with tail number, origin, destination, flight time, date/time, and aircraft type if available.
   - Flags for missing metadata (e.g., tail number not present).
4. **User approves review** to start import.
5. **Import & reporting:** job runs migration, then shows a report with:
   - Imported count, skipped count, failed count.
   - Links to artifacts (GPX/CSV, import report, logs).
6. **Progress feedback:** UI polls job status and shows step-level progress (queued → running → post-processing → completed) plus per-step counters.

## Observability & Auditability
- **Structured logs:** include `request_id`, `job_id`, `user_id`, and `step` per event.
- **Metrics:** job duration, job failure rate, queue depth, artifact bytes.
- **Audit logs:** keep security-relevant logs for at least 30 days (or longer for paid tiers).

## Security & Threat Model
**Threats:** credential exposure, data leakage, unauthorized access, abuse of API.

**Mitigations:**
- Short-lived credentials via job request only; never persisted.
- Strict IAM least privilege for Lambdas/Step Functions.
- Scoped S3 access per job prefix; presigned URLs for downloads.
- Input validation and payload size limits.
- Rate limits and quotas per user.

**Incident response basics:**
- Revoke compromised accounts (Cognito).
- Analyze CloudWatch logs for scope of access.
- Invalidate active sessions.

## Cost Controls & Free-Tier Strategy
- **Quota defaults:** max jobs per day, max flights per job, max artifact size.
- **API rate limits:** API Gateway throttling per user.
- **Budget alerts:** AWS Budgets with low thresholds and SNS notifications.
- **S3 lifecycle:** automatic artifact expiration to cap storage costs.

## Runbook (Minimal)
See `docs/backend-runbook.md` for the operational steps and troubleshooting guide.

## Local Development Experience (Docker Compose)
Goal: enable contributors to run the full stack locally with minimal setup.
- **Compose stack:** web UI + API (local runtime) + worker emulator + local DynamoDB/S3 (e.g., DynamoDB Local + MinIO).
- **Local auth:** Keycloak (OIDC) dev realm with static credentials; mirrors production JWT validation.
- **Workflow:** `docker compose up` starts UI, API, worker, storage, and Keycloak; sample data can be seeded for review flows.
- **HTTPS dev:** optional Caddy + mkcert proxy for trusted local TLS on `https://skybridge.localhost`.
- **Parity:** local job flow mirrors production states so the UI can show real progress.

### Current Dev Local Stub
- **Web:** lightweight HTML UI served at `/` for job creation, review display, and import approval.
- **API:** `src/backend/` FastAPI server validating OIDC JWTs (Keycloak in dev) and extracting the user id from token claims.
- **Storage:** JSON artifacts written to `data/backend/jobs/<job_id>/`.
- **Compose:** `docker-compose.yml` runs API + worker + DynamoDB Local + MinIO + Keycloak.
- **Lambda wiring:** handlers in `src/backend/lambda_handlers.py` packaged via `scripts/build-lambda.sh`.

## Maintenance Checklist
See `docs/backend-maintenance.md` for the maintenance cadence.

## Readiness Checklist (Public Release)
See `docs/backend-release-readiness.md` for the release checklist.

## Review & Feedback
- **Milestone 1 approved.** Proceeding to Milestone 2 (infrastructure scaffolding).
