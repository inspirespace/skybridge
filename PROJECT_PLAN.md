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

## 1. UI Inventory + State Model (To Do)
- [ ] 1.1 Define component inventory (accordion, stepper, progress card, chips, tables, CTA bar, info panels).
- [ ] 1.2 Define state machine for the flow (signed‑out → signed‑in → connected → review running → review complete → import running → import complete).
- [ ] 1.3 Document action rules (when CTAs are enabled, when steps are locked/readonly).

## 2. App Skeleton + Theming (To Do)
- [x] 2.1 Set up React + Vite + shadcn/ui with IBM Plex Sans (use the wireframe as the structure reference: `design/final/skybridge-import-flow-wireframe.html`).
- [x] 2.2 Implement light/dark theme toggle (choose tokens strategy: CSS vars vs Tailwind config).
- [x] 2.3 Build layout shell (header, sticky left nav, accordion stack, footer) using default components; avoid custom UI hacks to mimic the wireframe.

## 3. Step Components (To Do)
- [ ] 3.1 Sign‑in step UI (trust/info panel + sign‑in buttons).
- [ ] 3.2 Connect step UI (credentials + import filters + connect CTA).
- [ ] 3.3 Review step UI (progress card, summary chips, table, actions).
- [ ] 3.4 Import step UI (progress card, results summary, conclusion).

## 4. State + Mocked Data (To Do)
- [ ] 4.1 Wire state model to components (locked/readonly behavior, CTA enablement).
- [ ] 4.2 Add mocked API layer and polling hooks for review/import progress.
- [ ] 4.3 Wire transitions between steps based on state.

## 5. API Integration (To Do)
- [ ] 5.1 Auth integration (OIDC).
- [ ] 5.2 Review start + progress polling.
- [ ] 5.3 Import approval + progress polling.
- [ ] 5.4 Report download + retention actions.
- [ ] 5.5 Error handling + retry UX for each step.

## 5.6 SSO (Local Keycloak + Prod Cognito) (To Do)
- [ ] 5.6.1 Define dual‑issuer auth strategy (Keycloak for local dev, Cognito for prod) with env‑based config.
- [ ] 5.6.2 Local: configure Keycloak realm + client for SPA (OIDC + PKCE).
- [ ] 5.6.3 Local: configure Keycloak IdP brokers (Google, Apple, Facebook) with dev/test credentials.
- [ ] 5.6.4 Prod: create Cognito User Pool + App Client (SPA) with Hosted UI.
- [ ] 5.6.5 Prod: configure social IdPs (Google, Apple, Facebook) in Cognito.
- [ ] 5.6.6 Optional: configure enterprise SSO (OIDC/SAML) in both Keycloak and Cognito.
- [ ] 5.6.7 Set callback/logout URLs for dev + prod environments.
- [ ] 5.6.8 Frontend: implement provider buttons using `idp_hint` (Keycloak) and Cognito IdP routing.
- [ ] 5.6.9 Backend: validate JWTs against env‑selected issuer/JWKS (Keycloak vs Cognito).
- [ ] 5.6.10 Document env vars, secrets, and setup steps for dev + prod.

## 6. QA + Release (To Do)
- [ ] 6.1 Accessibility pass (focus order, ARIA, keyboard nav).
- [ ] 6.2 Responsive QA on mobile/tablet/desktop.
- [ ] 6.3 Visual QA against wireframe states (default component styling only).

## Open Questions
- [ ] Q1 Confirm API contracts for progress polling and report download.
- [ ] Q2 Confirm theme token source (global CSS vs design‑system config).
