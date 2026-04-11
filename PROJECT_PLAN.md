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
- [x] 9.2.3 Remove backend mode flags; use a shared fixed Firebase queue/worker configuration.

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
- [x] Local Firebase emulator stack re-verified after moving emulator access behind configurable domain subdomains to avoid host port conflicts.

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
- [x] Fix devcontainer startup failure caused by `HISTFILE` expansion in `.devcontainer/setup-history.sh` under `set -u`.
- [x] Fix devcontainer post-start cache permissions by using user-owned npm/uv caches (`$HOME/.cache/*`) and suppress non-fatal ownership warnings from mounted volumes.
- [x] Harden devcontainer Python 3.11 detection in post-start (`python3.11`/absolute path/python3-version fallback) and include Python feature bin paths in remote `PATH`.
- [x] Silence devcontainer npm update-notifier notices during startup (`NPM_CONFIG_UPDATE_NOTIFIER=false`) for cleaner rebuild logs.
- [x] Make devcontainer VNC setup/start best-effort in post-start so optional noVNC failures do not abort container startup.
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
- [x] Align app footer markup to landing footer design (logo chip, spacing, link treatment, and GitHub icon link) for consistent shared presentation.
- [x] Add automated logo asset generation from `design/logo/skybridge-logo-2048x2048.webp` and wire generated assets into shared headers/footers plus favicon/manifest metadata across app + static pages.
- [x] Remove duplicate storage of the full original logo in generated assets; keep `design/logo/skybridge-logo-2048x2048.webp` as the single source-of-truth.
- [x] Standardize visual PR screenshot workflow (before=`main`, deterministic app-state captures, light+dark sets, PR-context hosting, no screenshot binaries in git history).
- [x] De-duplicate screenshot workflow docs: keep detailed procedure in `CONTRIBUTING.md` and reference it from `AGENTS.md`.
- [x] Add a VS Code task (`Git: Cleanup Merged Branches`) for `scripts/cleanup-merged-branches.sh` to make branch cleanup accessible from the editor.
- [x] Add `scripts/clean-workspace.sh` plus a VS Code task (`Workspace: Clean`) that removes local dependency/build artifacts (`venv`, `node_modules`, caches, coverage/test outputs, pyc files) and ignored `*.log` files without reinstall/rebuild steps.
- [x] Add `scripts/firebase-clear-project.sh` plus a VS Code task (`Firebase: Clear Project`) to clear Functions/Firestore/RTDB/Hosting with zero-config defaults from `.firebaserc` while keeping the Firebase project itself.
- [x] Gate Firebase deploy workflow with a preflight secrets check so CI exits successfully with a skip notice when deploy prerequisites are not configured.
- [x] Add `scripts/firebase-deploy.sh` as the shared Firebase deploy implementation, used by both VS Code task (`Firebase: Deploy`) and `.github/workflows/firebase-deploy.yml`.
- [x] Pin devcontainer Python toolchain to `3.11` and enforce `uv sync --python 3.11` in post-start setup so local devcontainer runtime matches Firebase Functions `python311`.
- [x] Remove the obsolete root install/uninstall build file and clean repository references so command workflows live in scripts/VS Code tasks/GitHub Actions only.
- [x] Align Firebase project-id references to `skybridge-inspirespace` (`.firebaserc` default, emulator compose env/command, proxy rewrite path, frontend auth-client fallback, and functions env example).
- [x] Remove Terraform devcontainer feature and align VS Code Vitest settings with current `vitest.explorer` configuration keys.
- [x] Fix merged-remote cleanup to include nested remote branch names (e.g., `feature/foo`) instead of only single-segment names.
- [x] Remove devcontainer Copilot-uninstall hook/scripts to prevent noisy VS Code extension uninstall errors on container start.
- [x] Fix Step 2 "Edit import filters" transient review error flash by resetting to Connect state optimistically before async job deletion completes.
- [x] Extend privacy policy wording with explicit Firebase hosting/processing details and Google Analytics disclosure (consent, cookies, transfer safeguards).
- [x] Extend `logo:generate` to also create a repeatable 1280x640 social preview image (`src/frontend/public/social-preview.png`) and wire landing-page social meta tags to that asset.
- [x] Add devcontainer image tooling for asset generation (ImageMagick binaries) so logo/social generation commands work in-container.
- [x] Pre-create `/opt/venv` in the devcontainer image (`uv venv`) so VS Code can resolve `/opt/venv/bin/python` during startup (before post-start sync).
- [x] Fix devcontainer `uv sync` `/opt/venv` permission error by refreshing venv contents in-place for Python 3.11 and hardening `/opt/venv` ownership setup.
- [x] Add Firebase deploy auth preflight to fail fast before frontend/functions build, with local support for `firebase login`, `GOOGLE_APPLICATION_CREDENTIALS`, or `FIREBASE_SERVICE_ACCOUNT`.
- [x] Auto-trigger Firebase interactive login from the shared deploy script when launched from VS Code task terminals, with `--no-localhost` fallback.
- [x] Make Firebase deploy fully zero-config in VS Code tasks (no project prompt; default `.firebaserc` project + auto auth) and add one automatic retry for first-run API propagation failures.
- [x] Consolidate Functions/Object storage region to EU (`europe-west1`) across production deploy and local emulator/proxy routing.
- [x] Centralize essential Firebase defaults in `.firebaserc` (`projects.default`, `config.region`) consumed by deploy script and compose wiring.
- [x] Remove remaining hardcoded compose/frontend Firebase project settings and source project id from `.firebaserc` (`projects.default`) so local stack + deploy + CI share one zero-config default.
- [x] Normalize project-id resolution to a single canonical value (`FIREBASE_PROJECT_ID`) with runtime metadata auto-detection fallback for deployed Functions.
- [x] Remove split config by deleting `.firebase.defaults`; keep both project id and region in `.firebaserc`, deriving aliases at runtime in scripts/code.
- [x] Prune unused keys from `.env.example` files (`GCS_LOCATION`, `GCP_PROJECT_ID`, `BACKEND_QUEUE_PROVIDER`) after code-level usage audit.
- [x] Remove project-derived env duplication: stop exporting `GOOGLE_CLOUD_PROJECT`/`GCLOUD_PROJECT`, derive Firebase auth issuer/audience defaults from project id, and make frontend auth-domain/project-id defaults come from `.firebaserc`.
- [x] Fix Cloud Run startup failure for Firebase Functions by staging shared `src/backend` + `src/core` modules into `functions/src` during deploy packaging.
- [x] Remove redundant frontend `VITE_*` env duplication by deriving defaults from global backend vars in `vite.config.ts` and trimming duplicate entries from `.env.example`/compose wiring.
- [x] Centralize Firebase region derivation in shared resolvers (`src/backend/env.py`, `scripts/firebase-config.sh`) and remove duplicated inline region fallback patterns from backend/deploy callsites.
- [x] Fix VS Code Pytest discovery fallback to `/bin/python` by pinning workspace interpreter/test runner paths to `/opt/venv`.
- [x] Harden VS Code Pytest discovery by avoiding destructive `/opt/venv` wipes in post-start, validating pytest within `/opt/venv` (not global PATH), and wiring `/bin/python` + `.venv` fallbacks to `/opt/venv`.
- [x] Fix local emulator API routing by aligning Hosting `/api/**` rewrite to `europe-west1` and ensuring Functions emulator can discover Python deps via `functions/venv` symlink to container-local venv.
- [x] Fix Functions emulator startup mismatch on Alpine by adding `python3.11` alias inside container-local `functions-venv`, so Firebase Functions SDK discovery succeeds and `/api/**` rewrites resolve.
- [x] Fix Firebase emulator container healthcheck instability by moving emulator runtime state to a dedicated `/firebase-emulator` volume path (instead of nested `/workspace/.firebase-emulator`), disabling Gunicorn control sockets in local compose, adding Python 3.11 compatibility links (`bin/python3.11`, `lib/python3.11`) for Firebase Functions SDK discovery on Alpine Python 3.12, and auto-rebuilding stale persisted venvs whose activation scripts still reference the old mount path.
- [x] Fix devcontainer post-start `/opt/venv` refresh failure on rebuild by retrying Python 3.11 venv refresh with `sudo` and restoring `/opt/venv` ownership to `vscode`.
- [x] Fix CI pytest regression (270 passed / 3 failed) by restoring `user_id_from_request()` token-verify call signature to pass `mode`, while keeping `_verify_token(mode=None)` backward compatible for existing callers.
- [x] Add optional Firebase App Check protection for API requests (frontend `X-Firebase-AppCheck` header injection + backend token verification with `APP_CHECK_ENFORCE`).
- [x] Add Firebase deploy preflight for App Check so CI fails early when `APP_CHECK_ENFORCE=1` is set without required frontend App Check env (`VITE_FIREBASE_APP_CHECK_ENABLED=1`, `VITE_FIREBASE_APP_CHECK_SITE_KEY`).
- [x] Initialize theme from host system preference when no saved theme exists, including first paint and toggle state across SPA + static pages.
- [x] Simplify runtime to Firebase-only auth/storage/queue behavior by removing legacy auth/storage/version toggles, keeping the fixed Firebase worker queue path (`skybridge-job-queue`), reusing Firebase Hosting runtime config for App Check initialization, and keeping the theme synced with live system appearance changes when no explicit override is stored.
- [x] Fix production Firebase job API initialization by deriving the Storage bucket from Firebase runtime config (`FIREBASE_CONFIG.storageBucket`) instead of requiring explicit `GCS_BUCKET` in deployed Functions.
- [x] Remove local `GCS_BUCKET` wiring and unify Firebase Storage bucket resolution across emulator and production: explicit override, then `FIREBASE_CONFIG.storageBucket`, then the default bucket derived from the active Firebase project id.
- [x] Fix local Firebase Functions emulator source loading by ignoring stale `functions/_deploy_src` staging during emulator/dev runs and only preferring that path in deployed Cloud Functions runtime.
- [x] Tighten local Firebase emulator healthcheck so dev/proxy startup waits for both Auth and `/api/jobs` rewrite availability instead of exposing the app before Functions is ready.
- [x] Increase the Firebase worker timeout budget and emit incremental review progress during CloudAhoy export generation so long real-data reviews do not die silently at `Preparing review`.
- [x] Fix streamed artifact ZIP fallback so a missing remote object no longer replaces a valid local export with an empty entry.
- [x] Reduce false stale-worker alarms by lengthening the running-job stale timeout and softening delayed-heartbeat UI messaging during long imports.
- [x] Streamline Firebase email-link sign-in UX: use inline auth card on `/app` (no duplicate modal) and prefill email-link completion from redirect email hint.
- [x] Improve sign-in email field UX by submitting on Enter and enabling native browser email autofill/suggestions without wrapping the field in a login form that triggers Safari password-manager takeover.
- [x] Reduce password-manager save prompts on CloudAhoy/FlySto credential fields by adding `autocomplete` suppression plus manager-specific ignore attributes (`data-lpignore`, `data-1p-ignore`, `data-bwignore`).
- [x] Further harden credential fields against password-manager prompts by adding decoy hidden login inputs for CloudAhoy/FlySto forms.
- [x] Restore Playwright e2e compatibility for Connect credentials by removing the readOnly arming gate from password inputs while keeping decoy fields plus password-manager ignore attributes.
- [x] Replace the hidden CloudAhoy/FlySto login decoys with less login-like field semantics (`new-password`, no form names) and clear temporary import credentials on delete/sign-out/token-expiry so Safari stops prompting to save them on close.
- [x] Fix deployed Firebase email-link auth on the custom Hosting domain by allowing Firebase Auth helper iframe/script origins in Hosting CSP (`*.firebaseapp.com`, `*.web.app`, `apis.google.com`, `www.google.com`, `www.gstatic.com`) and lock that into regression coverage.
- [x] Restore frontend deploy builds after adding the CSP regression test by exposing Node typings to frontend test files during `tsc -b` typechecking.
- [x] Extend the Firebase clear-project task to empty the resolved Firebase Storage bucket objects as well, while clarifying the remaining limits (Auth users not deleted; Storage metrics can lag under retention/soft-delete).
- [x] Harden Firebase Storage cleanup auth in the clear-project task: use `gcloud auth application-default print-access-token` as an extra token source, isolate gcloud in a temp config dir, and prompt for ADC login in interactive local runs when needed.
- [x] Replace guessed Firebase bucket names in the clear-project task with Storage API project-bucket discovery so Storage cleanup clears the project’s real buckets instead of reporting false “no matching bucket” results.
- [x] Disable Docker Compose's attached shortcut menu by default inside the devcontainer wrapper so VS Code launch terminals stop advertising unusable host-only Docker Desktop actions.
- [x] Add Firebase deploy preflight for the default Firestore database and clarify that local `docker compose --profile prod` stays emulator-backed, so missing production Firebase resources are caught by deploy checks rather than local compose alone.
- [x] Extend Firebase deploy/clear scripts to manage the default Firestore database lifecycle directly: auto-create `(default)` on deploy when missing and delete it during project clear, with configurable first-create location via `FIRESTORE_DATABASE_LOCATION`.
- [x] Harden Firestore database auto-create after clear by waiting through Firebase's database-id cooldown window and retrying recreation automatically during deploy.
- [x] Fix Firebase clear-project storage cleanup exit handling so empty buckets no longer abort the task under `set -e`; empty buckets now report as already empty and the script continues through the remaining buckets.
- [x] Upgrade Firebase clear-project storage cleanup from object-only cleanup to full bucket removal: delete each project bucket after clearing remaining object versions, with explicit warnings when bucket protection settings block deletion.
- [x] Fix production artifact downloads for Firebase Functions by propagating the Firebase Web SDK `storageBucket` into managed Functions env and teaching backend bucket resolution to prefer discovered real project buckets before guessing a default name.
- [x] Harden Firebase deploy storage setup so deploy verifies/discovers the actual project bucket via the Storage API, writes managed `GCS_BUCKET`, and fails early when Firebase Storage is not provisioned instead of shipping a worker that 404s artifact uploads at runtime.
- [x] Extend deploy storage preflight to auto-create the missing Firebase default artifact bucket (`<project>.firebasestorage.app` or `<project>.appspot.com`) in the configured region instead of requiring a manual Firebase Console Storage setup step.
- [x] Harden deploy storage auto-provisioning for globally unavailable Firebase-style bucket names by falling back to a normal project-owned artifact bucket name and pinning managed `GCS_BUCKET` to it.
- [x] Fix production import handoff across Cloud Functions instances by loading `review.json` from object storage during the import phase instead of assuming the review manifest still exists on the worker’s local filesystem.
- [x] Remove two more instance-local artifact assumptions: failed-import retry gating now checks remote `review.json`, and artifact listing now merges local + object-store results instead of letting a local `job_dir` hide remote artifacts.
- [x] Persist `migration.db` through object storage so review/import retries on different Cloud Functions instances keep migration state instead of starting from an empty local SQLite file.
- [x] Fix deploy storage preflight for later redeploys by reusing an already-created fallback artifact bucket when Firebase Web SDK config still points at an unavailable default `*.firebasestorage.app` name.
- [x] Remove unused `FirebaseAuthDialog` component file to prevent accidental reintroduction of auth modal behavior on `/app`.
- [x] Remove deploy-time Firebase Auth branding auto-patching and switch deploy preflight to manual setup guidance (email-link mode, template naming, authorized domains) plus verification-only checks.
- [x] Document Firebase Console prerequisite that Auth template "Public-facing name" is editable only when Google sign-in provider is enabled (deploy overview + docs).
- [x] Document manual Firebase Console setup for Auth email custom sender domains, including DNS verification and the distinction from Hosting domains / Auth authorized domains.
- [x] Fix deploy authorized-domain setup overview to merge/dedupe `FIREBASE_AUTHORIZED_DOMAINS` across env sources so all configured domains (for example `.app` and `.co`) are shown and validated.
- [x] Reduce deploy-time Git noise by staging shared backend modules under ignored `functions/_deploy_src/src` (instead of tracked `functions/src`) and updating Functions import path fallback accordingly.
- [x] Harden deploy authorized-domain config parsing to merge all `FIREBASE_AUTHORIZED_DOMAINS` entries (including repeated keys) across env sources, and label setup output as merged-source values.
- [x] Fix deploy authorized-domain parser dropping the final value without trailing newline (for comma-separated env values), so `.app,.co` entries both render in setup output and verification.
- [x] Add deploy preflight toolchain check to fail fast with explicit missing-command list when required CLI utilities are not present in the devcontainer/runtime.
- [x] Add repository EOL normalization for shell/python files (`.gitattributes`) to prevent CRLF-related shell execution artifacts in deploy scripts.
- [x] Fix Cloud Functions startup path resolution in `functions/main.py` for deployed runtime (`/workspace` source root), so staged modules under `functions/_deploy_src/src` are importable and containers start on `PORT=8080`.
- [x] Fix production API base fallback to same-origin `/api` (instead of fixed local-domain API URLs) to prevent CSP `connect-src` failures on deployed domains.
- [x] Simplify backend runtime paths by removing unused local/Cloud Run HTTP adapters (`src/backend/lambda_api_local.py`, `src/backend/http_api.py`, `src/backend/http_worker.py`), keeping Firebase Functions as the only backend runtime while retaining compose-based dev mock services.
- [x] Disable automatic Firebase deploys on merges to `main` by making `.github/workflows/firebase-deploy.yml` manual-only (`workflow_dispatch`), while keeping the shared local/manual deploy path intact.

## 10. Security Hardening (In Progress)
- [x] Require encrypted storage for credential payloads when Firestore is enabled.
- [x] Remove token persistence from job storage (in-memory only).
- [x] Lock Firestore/Storage rules to authenticated reads and server-only writes.
- [x] Gate emulator token trust behind explicit local-only flag.
- [x] Replace persistent auth token storage with in-memory/session-only handling.
- [x] Add security regression tests (crypto roundtrip, token persistence guard, emulator trust).
- [ ] Validate production environment variables include encryption key + strict CORS allowlist.
