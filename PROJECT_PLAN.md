# Project Plan (Web App)

Goal: ship the production web UI for CloudAhoy → FlySto imports, using the wireframe as the single UI reference and default component styling.

## 0. Foundation (Done)
- [x] 0.1 Docs trimmed to essentials (README + production requirements).
- [x] 0.2 CLI import workflow stabilized (review → approve → import; manifests + reports).
- [x] 0.3 Auth/dev stack wired (Firebase Auth + emulator suite; devcontainer + local HTTPS).
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
- [x] 5.1 Auth integration (Firebase).
- [x] 5.2 Review start + progress polling.
- [x] 5.2.a Frontend wired to `/jobs` create + poll (dev header auth).
- [x] 5.3 Import approval + progress polling.
- [x] 5.3.a Frontend wired to `/jobs/{id}/review/accept` (dev header auth).
- [x] 5.4 Report download + retention actions.
- [x] 5.4.a Frontend wired to `/jobs/{id}/artifacts` download (dev header auth).
- [x] 5.4.b Frontend wired to `/jobs/{id}` delete (retention action).
- [x] 5.5 Error handling + retry UX for each step.
- [x] 5.6 Firebase Auth configuration and social providers (Google/Apple/Facebook).

## 6. QA + Release (Done)
- [x] 6.1 Accessibility pass (focus order, ARIA, keyboard nav).
- [x] 6.2 Responsive QA on mobile/tablet/desktop.
- [x] 6.3 Visual QA against wireframe states (default component styling only).

## 7. SEO Landing (Done)
- [x] 7.1 Split static landing page from SPA app for better crawlability.
- [x] 7.2 Add static imprint/privacy pages outside the SPA.


## 9. Firebase-Only Migration (Planned)
Objective: migrate production stack to Firebase-only (Functions 2nd gen + Hosting + Firestore + Storage + Auth) with social sign-in.

### 9.1 Architecture + Provider Mapping
- [x] 9.1.1 Define Firebase service mapping (Functions 2nd gen, Hosting rewrites, Firestore, Storage, Auth).
- [x] 9.1.2 Decide trigger strategy for worker (Pub/Sub vs HTTPS callable).
- [x] 9.1.3 Define artifact delivery strategy (Storage signed URLs vs proxy).
- [x] 9.1.4 Document all prod env vars for Firebase in `docs/production.md`.

### 9.2 Backend Port
- [x] 9.2.1 Add Firebase Functions 2nd gen entrypoints (HTTP API + Pub/Sub worker).
- [x] 9.2.2 Wire Firebase emulators for local dev (Auth/Firestore/Pub/Sub/Storage/Functions).
- [x] 9.2.3 Update backend config flags for Firebase-only runtime.

### 9.3 Frontend + Auth
- [x] 9.3.1 Update auth mode to Firebase and ensure social sign-in buttons route to Firebase Auth providers.
- [x] 9.3.2 Add Firebase Hosting rewrites for the SPA and API.

### 9.4 Infrastructure as Code
- [x] 9.4.1 Add Firebase config (firebase.json + functions runtime config).
- [x] 9.4.2 Add CI deploy pipeline using Firebase CLI.

### 9.5 Testing + Validation
- [x] 9.5.1 Validate local dev via Firebase emulators.
- [x] 9.5.2 Ensure frontend tests pass unchanged in devcontainer.
- [x] 9.5.3 Add production smoke test checklist for Firebase.

## Acceptance Criteria (Firebase-Only Migration)
- [x] Local Docker Compose runs Firebase emulators (Auth/Firestore/Pub/Sub/Storage/Functions) and the app runs end-to-end.
- [x] Firebase Hosting serves the SPA and rewrites `/api/**` to the Functions API.
- [x] API Function accepts requests and validates Firebase Auth JWTs.
- [x] Worker Function processes queued jobs and updates Firestore state.
- [x] Artifacts stored in Firebase Storage and expire via lifecycle rules.
- [ ] Frontend can complete review → import flow end-to-end via Firebase hosting.
- [x] CI tests pass (backend + frontend) using existing devcontainer commands.
- [x] `docs/production.md` reflects Firebase env vars and deployment steps.

## Open Questions
- [ ] Q1 Confirm API contracts for progress polling and report download.
- [ ] Q2 Confirm theme token source (global CSS vs design‑system config).
- [ ] Q3 Confirm whether CloudAhoy/FlySto require fixed egress IP allowlisting (may require NAT).

## Blockers
- [x] Local Firebase emulator stack re-verified after moving emulator access behind `*.skybridge.localhost` subdomains to avoid host port conflicts.

## Maintenance Notes
- [x] Show download preparation progress and lock download actions while artifacts are fetched.
- [x] Treat duplicate uploads as skipped in import reports.
- [x] Block import approval when review failed without a ready manifest; align UI state with backend review-ready checks.
- [x] Add credential validation endpoint, SSE heartbeats, and surface job failure errors in the UI to avoid stalled flows.
- [x] Expand automated test coverage across backend helpers, storage enrichment, auth, and frontend API/state/UI flows.
- [x] Add Python and frontend coverage reporting commands/config.
- [x] Add backend API/service tests plus frontend App/hook tests to raise coverage.
- [x] Extend coverage for auth helpers, CLI run flows, and artifacts zip/auth token routes.
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
- [x] Align frontend app shell and landing page visuals with finalized mockups (`design/final/skybridge-visual-design.html`, `design/final/skybridge-landing-page.html`) while preserving the existing state/API flow.
- [x] Add macOS devcontainer headed e2e helper for XQuartz black-window mitigation.
- [x] Add devcontainer-only Xvfb/VNC/noVNC helper scripts for headed e2e without host config.
- [x] Allow auto-install of VNC deps at devcontainer start via `DEVCONTAINER_E2E_VNC`.
- [x] Auto-start Xvfb/VNC/noVNC on devcontainer start for VS Code Testing compatibility.
- [x] Ensure Playwright global setup starts VNC server when launched from VS Code Testing UI.
- [x] Fix noVNC web UI serving (use novnc_proxy/websockify --web).
- [x] Auto-open noVNC auto-connect URL when running Playwright from VS Code.
- [x] Exclude discovery modules from coverage targets and remove discovery-specific tests.
- [x] Refactor App shell auth UI into dedicated components/config helpers to keep `App.tsx` maintainable.
- [x] Refresh visual polish for landing/app (route-oriented hero + denser review table styling) while keeping existing flow behavior.
- [x] Simplify sidebar copy/layout (remove `Preflight`/`CHK-*` wording, reduce visual clutter, improve readability on narrower widths).
- [x] Refine step status indicator to plain text + animated dot (no status pills) for cleaner web-app UI.
- [x] Fix landing hero floating "block time" chip overlap by repositioning it inside the hero card and raising text-column stacking.
- [x] Remove floating "block time" overlay and convert it to an in-card chip to eliminate hero-content overlap across breakpoints.
- [x] Replace misleading "How it works" play icon with a steps/checklist icon to reflect guidance content (not video).
- [x] Upgrade "How it works" CTA icon to a route/flow motif with subtle hover motion for better visual engagement.
- [x] Fine-tune "How it works" route icon dashed-path stroke weight for a lighter appearance.
- [x] Make "How it works" route icon dots fully solid and non-animated to reduce visual distraction against the animated dashed path.

## 10. Security Hardening (In Progress)
- [x] Require encrypted storage for credential payloads when Firestore is enabled.
- [x] Remove token persistence from job storage (in-memory only).
- [x] Lock Firestore/Storage rules to authenticated reads and server-only writes.
- [x] Gate emulator token trust behind explicit local-only flag.
- [x] Replace persistent auth token storage with in-memory/session-only handling.
- [x] Add security regression tests (crypto roundtrip, token persistence guard, emulator trust).
- [ ] Validate production environment variables include encryption key + strict CORS allowlist.
