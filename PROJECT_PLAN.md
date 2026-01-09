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

## Open Questions
- [ ] Q1 Confirm API contracts for progress polling and report download.
- [ ] Q2 Confirm theme token source (global CSS vs design‑system config).

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
- [x] Auto-open noVNC auto-connect URL when running Playwright from VS Code (now opt-in).
- [x] Exclude discovery modules from coverage targets and remove discovery-specific tests.
