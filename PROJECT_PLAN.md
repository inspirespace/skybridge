# Project Plan (Web App)

Goal: ship the production web UI for CloudAhoy → FlySto imports, using the wireframe as the single UI reference and default component styling.

## 0. Foundation (Done)
- [x] 0.1 Backend architecture and workflow docs exist (review/import/report flow, artifacts, runbook).
- [x] 0.2 CLI import workflow stabilized (review → approve → import; manifests + reports).
- [x] 0.3 Auth/dev stack wired (OIDC/Keycloak in dev; devcontainer + local HTTPS).
- [x] 0.4 CI and tooling set up (pytest in CI, uv deps, devcontainer toolchain).
- [x] 0.5 Wireframe finalized as the single UI reference (`design/final/skybridge-import-flow-wireframe.html`).
- [x] 0.6 Review step layout simplified (helper line in progress card + summary chips).
- [x] 0.7 Copy clarified (review/import labels, CTA wording, helper text, status pills).
- [x] 0.8 Layout rules captured (sticky left nav, accordion steps, progress cards, tables, footer; mobile top bar + bottom stepper).
- [x] 0.9 Confirmed: use default component library styling wherever possible.
- [x] 0.10 Confirmed: light/dark mode toggle required.

## 1. UI Inventory + State Model (Done)
- [x] 1.0 Prerequisite: complete section 1 before moving to sections 2–4.
- [x] 1.1 Define component inventory (accordion, stepper, progress card, chips, tables, CTA bar, info panels).
- [x] 1.2 Define state machine for the flow (signed‑out → signed‑in → connected → review running → review complete → import running → import complete).
- [x] 1.3 Document action rules (when CTAs are enabled, when steps are locked/readonly).

## 2. App Skeleton + Theming (Done)
- [x] 2.1 Set up React + Vite + shadcn/ui with IBM Plex Sans (use the wireframe as the structure reference: `design/final/skybridge-import-flow-wireframe.html`).
- [x] 2.2 Implement light/dark theme toggle (choose tokens strategy: CSS vars vs Tailwind config).
- [x] 2.3 Build layout shell (header, sticky left nav, accordion stack, footer) using default components; avoid custom UI hacks to mimic the wireframe.

## 3. Step Components (Done)
- [x] 3.1 Sign‑in step UI (trust/info panel + sign‑in buttons).
- [x] 3.2 Connect step UI (credentials + import filters + connect CTA).
- [x] 3.3 Review step UI (progress card, summary chips, table, actions).
- [x] 3.4 Import step UI (progress card, results summary, conclusion).

## 4. State + Mocked Data (Done)
- [x] 4.1 Wire state model to components (locked/readonly behavior, CTA enablement).
- [x] 4.2 Add mocked API layer and polling hooks for review/import progress.
- [x] 4.3 Wire transitions between steps based on state.

## 5. API Integration (In Progress)
- [x] 5.1 Auth integration (OIDC).
- [x] 5.1.a Background refresh for OIDC access tokens.
- [x] 5.2 Review start + progress polling.
- [x] 5.2.a Frontend wired to `/jobs` create + poll (dev header auth).
- [x] 5.3 Import approval + progress polling.
- [x] 5.3.a Frontend wired to `/jobs/{id}/review/accept` (dev header auth).
- [x] 5.4 Report download + retention actions.
- [x] 5.4.a Frontend wired to `/jobs/{id}/artifacts` download (dev header auth).
- [x] 5.4.b Frontend wired to `/jobs/{id}` delete (retention action).
- [x] 5.5 Error handling + retry UX for each step.
- [ ] 5.6 Define dual‑issuer auth strategy (Keycloak for local dev, Cognito for prod) with env‑based config.
  - [x] 5.6.1 Local: configure Keycloak realm + client for SPA (OIDC + PKCE).
  - [x] 5.6.2 Local: configure Keycloak IdP brokers (Google, Apple, Facebook) with dev/test credentials.
  - [x] 5.6.3 Prod: create Cognito User Pool + App Client (SPA) with Hosted UI.
  - [x] 5.6.4 Prod: configure social IdPs (Google, Apple, Facebook) in Cognito.
  - [ ] 5.6.5 Optional: configure enterprise SSO (OIDC/SAML) in both Keycloak and Cognito.
  - [x] 5.6.6 Set callback/logout URLs for dev + prod environments.
  - [x] 5.6.7 Frontend: implement provider buttons using `idp_hint` (Keycloak) and Cognito IdP routing.
  - [x] 5.6.8 Backend: validate JWTs against env‑selected issuer/JWKS (Keycloak vs Cognito).
  - [x] 5.6.9 Document env vars, secrets, and setup steps for dev + prod.

## 6. QA + Release (Done)
- [x] 6.1 Accessibility pass (focus order, ARIA, keyboard nav).
- [x] 6.2 Responsive QA on mobile/tablet/desktop.
- [x] 6.3 Visual QA against wireframe states (default component styling only).

## 7. SEO Landing (Done)
- [x] 7.1 Split static landing page from SPA app for better crawlability.
- [x] 7.2 Add static imprint/privacy pages outside the SPA.

## 8. AWS Free-Tier Launch (Planned)
Objective: ship a production-ready, EU-hosted, serverless deployment on AWS free-tier where possible, with Cognito + social IdPs and Lambda-based workers.

### 8.1 Target Architecture + Region
- [ ] 8.1.1 Confirm EU region for launch (prefer eu-central-1 for DE data residency; eu-west-1 for broader AWS service parity).
- [ ] 8.1.2 Confirm DNS + TLS strategy for `skybridge.inspirespace.co` (Route 53 vs external DNS).
- [ ] 8.1.3 Confirm Cognito Hosted UI + social IdPs (Google/Apple/Facebook) as primary auth.

### 8.2 Terraform: Production Wiring
- [x] 8.2.1 Add API Gateway stage + deployment outputs (API base URL).
- [x] 8.2.2 Add JWT authorizer (Cognito User Pool) + attach to routes.
- [x] 8.2.3 Add CORS config for SPA origin(s).
- [x] 8.2.4 Add Lambda invoke permissions for API Gateway.
- [x] 8.2.5 Add Lambda environment variables from Terraform outputs.
- [x] 8.2.6 Add IAM policies for Lambda: DynamoDB, S3, SQS, CloudWatch Logs.
- [x] 8.2.7 Add CloudWatch log groups with retention.
- [x] 8.2.8 Add SQS trigger for worker Lambda (review/import job execution).

### 8.3 Backend Runtime: Lambda + SQS Worker
- [x] 8.3.1 Update `src/backend/lambda_handlers.py` to use DynamoDB + S3 + SQS (no local filesystem).
- [x] 8.3.2 Add Lambda SQS worker handler (single-message processing) and wire to JobService.
- [x] 8.3.3 Ensure `BACKEND_WORKER_TOKEN` and credential-claim flow work in Lambda mode.
- [x] 8.3.4 Remove long-running FastAPI/worker code paths; use Lambda API emulator + local SQS in dev.
- [ ] 8.3.4 Ensure rate limits, TTL, and artifact retention are enforced in prod mode.

### 8.4 Frontend Hosting + Auth
- [ ] 8.4.1 Deploy SPA + static pages to S3.
- [x] 8.4.2 Add CloudFront + ACM cert for `skybridge.inspirespace.co`.
- [ ] 8.4.3 Configure Cognito callback/logout URLs for production domain.
- [ ] 8.4.4 Update frontend env config for prod (OIDC issuer/client id, API base URL).

### 8.5 Operations + Cost Controls
- [ ] 8.5.1 Configure AWS Budgets + SNS alerts (low thresholds).
- [ ] 8.5.2 Validate S3 lifecycle + DynamoDB TTL in prod.
- [ ] 8.5.3 Add API Gateway throttling / quotas aligned with BACKEND limits.
- [x] 8.5.4 Add deploy automation (script + GitHub Actions workflow).
- [ ] 8.5.5 Run runbook + readiness checklist using production stack.

## Acceptance Criteria (AWS Launch Autonomy)
- [ ] Deployed stack in EU region with working HTTPS at `https://skybridge.inspirespace.co`.
- [ ] Cognito Hosted UI sign-in works with Google/Apple/Facebook and returns JWTs accepted by the API.
- [ ] Frontend can create a job, review completes, and import completes end-to-end against real providers.
- [ ] Artifacts stored in S3, listed via API, and expire automatically after 7 days.
- [ ] DynamoDB TTL cleans credential entries; no credentials persist beyond TTL.
- [ ] SQS-backed Lambda worker processes review/import jobs without manual intervention.
- [ ] CloudWatch logs available for API + worker; budgets/alerts configured.
- [ ] Runbook and release readiness checklists completed for the prod stack.

## Open Questions
- [ ] Q1 Confirm API contracts for progress polling and report download.
- [ ] Q2 Confirm theme token source (global CSS vs design‑system config).
- [ ] Q3 Confirm whether CloudAhoy/FlySto require fixed egress IP allowlisting (may require NAT).

## Maintenance Notes
- [x] Paginate DynamoDB job scans/queries in `JobStore` to avoid missing older jobs in dev worker mode.
- [x] Show download preparation progress and lock download actions while artifacts are fetched.
- [x] Treat duplicate uploads as skipped in import reports.
- [x] Block import approval when review failed without a ready manifest; align UI state with backend review-ready checks.
- [x] Add credential validation endpoint, SSE heartbeats, and surface job failure errors in the UI to avoid stalled flows.
- [x] Expand automated test coverage across backend helpers, storage enrichment, auth, and frontend API/state/UI flows.
- [x] Add Python and frontend coverage reporting commands/config.
- [x] Add backend API/service tests plus frontend App/hook tests to raise coverage.
- [x] Extend coverage for auth helpers, OIDC hook, CLI run flows, and artifacts zip/auth token routes.
- [x] Expand coverage for App UI flows, CLI reconcile path, and credential claim route.
- [x] Add coverage for worker/lambda handlers and browser session helpers.
- [x] Add coverage for CloudAhoy client helpers, backend dev web config, and web client helpers (CloudAhoy/FlySto).
- [x] Add coverage for backend mock CloudAhoy/FlySto services and state handling.
- [x] Expand coverage for backend auth/JWKS handling and credential stores.
- [x] Add extra web client coverage paths for CloudAhoy/FlySto uploads and navigation.
- [x] Add FlySto helper coverage for tag normalization, duplicate detection, and upload URL building.
- [x] Expand coverage for backend job store enrichment, artifact/object store paths, and worker credential handling.
- [x] Expand guided flow coverage with run orchestration and preflight paths.
- [x] Expand FlySto client coverage for prepare/upload flows and request retry handling.
- [x] Add CI test reporting with JUnit + coverage artifacts for backend and frontend (Vitest/Playwright).
- [x] Expand backend app coverage for SSE job events and failed-review import acceptance.
- [x] Add additional frontend e2e coverage (review running, review failure, download expiry).
- [x] Expand backend app coverage for rate limits, delete flows, and worker-queued review accept path.
- [x] Add e2e coverage for delete results success flow.
- [x] Add FlySto client tests for crew/roles/metadata error handling and log source parsing.
- [x] Add e2e coverage for successful download flow.
- [x] Add backend app coverage for auth token errors, credential claim errors, and rate-limit validation.
- [x] Add e2e coverage for review table expansion (show more flights).
- [x] Add e2e coverage for connect enablement, credential validation errors, and import confirmation.
- [x] Add macOS devcontainer headed e2e helper for XQuartz black-window mitigation.
- [x] Add devcontainer-only Xvfb/VNC/noVNC helper scripts for headed e2e without host config.
- [x] Allow auto-install of VNC deps at devcontainer start via `DEVCONTAINER_E2E_VNC`.
- [x] Auto-start Xvfb/VNC/noVNC on devcontainer start for VS Code Testing compatibility.
- [x] Ensure Playwright global setup starts VNC server when launched from VS Code Testing UI.
- [x] Fix noVNC web UI serving (use novnc_proxy/websockify --web).
- [x] Auto-open noVNC auto-connect URL when running Playwright from VS Code.
- [x] Exclude discovery modules from coverage targets and remove discovery-specific tests.
