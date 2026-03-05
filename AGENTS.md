# Repository Guidelines

This repository contains a Dockerized Python CLI with Playwright-based automation. Keep this file accurate as the project evolves; update it whenever new commands, layouts, or workflows are introduced.

## Project Structure & Module Organization
- Place application/source code under `src/`.
- Put tests under `tests/` or `test/` (match your framework).
- Keep assets in `assets/`, and config files at the repo root.
- Inspector scripts live in `tools/inspector/` (dev-only helpers).
- VNC helpers for Playwright live in `scripts/` (devcontainer use only).
- User-facing scripts: `scripts/cleanup-merged-branches.sh` (branch cleanup), `scripts/clean-workspace.sh` (local dependency/build/log cleanup), `scripts/firebase-deploy.sh` (shared local/CI Firebase deploy flow), `scripts/firebase-clear-project.sh` (clear Firebase resources while keeping the project), `scripts/repair-docker-socket-access.sh` (fix Docker socket permissions inside devcontainer sessions), and `scripts/docker-compose.sh` (Docker Compose wrapper that resolves host bind paths when run from inside the devcontainer).
- Shared install helper: `scripts/npm-ci-frontend.sh` (resilient frontend `npm ci` with nested strategy plus one automatic retry/cache cleanup).
- Firebase emulator container bootstrap script: `scripts/firebase-emulator-start.sh` (installs emulator deps, prepares venv, and starts emulators with shared import/export dir).
- Frontend entry points: landing page in `src/frontend/index.html`, SPA app in `src/frontend/app/index.html`, static legal pages in `src/frontend/privacy/index.html` and `src/frontend/imprint/index.html`.
- Infrastructure-as-code is not tracked in this repository (Firebase-only deployment).
- Firebase emulators are configured by `firebase.json` and `.firebaserc`.
- Firebase Functions entrypoints live in `functions/`.
- `docker-compose.yml` runs the Firebase emulators + Functions for local dev.
- If you adopt a different layout, document it here with concrete paths (example: `cmd/`, `internal/`, `pkg/` for Go).

## Build, Test, and Development Commands
- `docker compose --profile dev up --build` — run the local dev stack with Vite dev server (Firebase emulators, API, worker, frontend, HTTPS proxy, mocks).
- `docker compose --profile prod up --build` — run the local prod-like stack (app served via Firebase Hosting emulator from `src/frontend/dist`).
- `./scripts/docker-compose.sh --profile <dev|prod> up -d --build` — preferred in devcontainer terminals/tasks so bind mounts resolve to host paths on Docker Desktop.
- VS Code launch configs: `Stack: Start (Docker Compose)`, `Stack: Start (Docker Compose, prod-like)`, `Stack: Stop (Docker Compose)` in `.vscode/launch.json`.
- VS Code tasks: `Compose: Up (dev)`, `Compose: Up (prod)`, `Compose: Down`, `Firebase: Deploy`, `Firebase: Clear Project`, `Workspace: Clean`, `Devcontainer: Repair Docker Socket Access`, `Devcontainer: Repair Docker Socket Access (Restart VS Code Server)`, `Git: Cleanup Merged Branches` in `.vscode/tasks.json`.
- `Firebase: Deploy` is zero-config for local use: it reads the default project from `.firebaserc`, triggers login when needed, and does not prompt for project id.
- `Firebase: Clear Project` is zero-config for local use: it reads project/region defaults from `.firebaserc`, confirms interactively (unless `--force`), and clears functions/firestore/rtdb/hosting without deleting the Firebase project.
- Firebase project id and region defaults live in `.firebaserc` (`projects.default`, `config.region`).
- Backend code resolves project/region through shared helpers in `src/backend/env.py` (`resolve_project_id()`, `resolve_region()`); avoid per-callsite `os.getenv(...) or <default>` fallbacks for these values.
- Frontend Firebase project/auth-domain defaults are derived from `.firebaserc` in `src/frontend/vite.config.ts`, so `VITE_FIREBASE_PROJECT_ID` and `VITE_FIREBASE_AUTH_DOMAIN` are optional unless you need overrides.
- Frontend runtime env also derives from backend/global equivalents in `src/frontend/vite.config.ts` (`VITE_AUTH_MODE`←`AUTH_MODE` with safe default `firebase` for build/dev and `header` for Vitest, `VITE_FIRESTORE_JOBS_COLLECTION`←`FIRESTORE_JOBS_COLLECTION`, `VITE_RETENTION_DAYS`←`BACKEND_RETENTION_DAYS`, and `VITE_*` prefill credentials ← non-`VITE_` credentials).
- Devcontainer startup attempts to install Firebase CLI (`firebase-tools`) when missing; if npm is unreachable, setup continues and `firebase` remains unavailable until install succeeds.
- Devcontainer tooling is pinned to Python `3.11` to match Firebase Functions runtime `python311`.
- Devcontainer post-start uses user-owned caches (`$HOME/.cache/npm`, `$HOME/.cache/uv`) to avoid permission issues from shared `/tmp` cache directories.
- Devcontainer post-start auto-reconciles Docker socket group membership for the remote user (`vscode`) when `/var/run/docker.sock` GID changes, reducing intermittent `permission denied` failures for Docker CLI/VS Code Docker extension inside the devcontainer.
- Devcontainer startup disables npm update-notifier noise (`NPM_CONFIG_UPDATE_NOTIFIER=false`) for cleaner rebuild logs.
- Devcontainer frontend dependency reinstalls run through `scripts/npm-ci-frontend.sh` so npm unpack/install is more resilient against intermittent `ENOENT`/tarball failures.
- Devcontainer VNC/noVNC setup is best-effort during post-start; failures are logged as warnings and do not block startup.
- Devcontainer image includes ImageMagick binaries for frontend asset generation commands (`convert`, `identify`, etc.).
- Devcontainer image pre-creates `/opt/venv` (`uv venv`) so VS Code can resolve `python.defaultInterpreterPath` immediately during container startup.
- Devcontainer post-start refreshes `/opt/venv` in-place to Python `3.11` (without deleting `/opt/venv` itself) and automatically retries with `sudo` if `/opt/venv` ownership blocks the refresh.
- Workspace VS Code settings pin Python test discovery to `/opt/venv` (`python.defaultInterpreterPath`, `python.testing.pytestPath`) so Pytest discovery does not fall back to `/bin/python`.
- Devcontainer post-start also installs a `/bin/python` wrapper that execs `/opt/venv/bin/python` (plus a workspace `.venv` symlink to `/opt/venv`) so VS Code discovery remains stable even when extensions probe `/bin/python`.
- Firebase deploy workflow lives in `.github/workflows/firebase-deploy.yml` and requires `FIREBASE_SERVICE_ACCOUNT` secret.
- `scripts/firebase-deploy.sh` performs Firebase auth preflight before builds; in interactive terminals (for example VS Code tasks) it auto-runs `firebase login --reauth` when unauthenticated, with fallback `--no-localhost`, and still supports `GOOGLE_APPLICATION_CREDENTIALS` / `FIREBASE_SERVICE_ACCOUNT`.
- `scripts/firebase-deploy.sh` validates required CLI toolchain availability up-front (`firebase`, `npm`, `node`, `curl`, `awk`, `sed`, `grep`, `find`) so deploy fails fast with a clear message when the devcontainer/runtime is missing prerequisites.
- `scripts/firebase-deploy.sh` also runs an App Check preflight: when `APP_CHECK_ENFORCE=1`, CI fails if frontend App Check vars (`VITE_FIREBASE_APP_CHECK_ENABLED=1`, `VITE_FIREBASE_APP_CHECK_SITE_KEY`) are missing; local runs warn and continue.
- `scripts/firebase-deploy.sh` also preflights production Firebase web config and fails fast when frontend auth config is incomplete (`VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_APP_ID`, `VITE_FIREBASE_PROJECT_ID`), with best-effort auto-resolution from Firebase Web App SDK config via `firebase apps:sdkconfig`.
- `scripts/firebase-deploy.sh` supports optional `FIREBASE_WEB_APP_ID` to pin which Firebase Web App is used when resolving frontend SDK config during deploy preflight.
- `scripts/firebase-deploy.sh` now preflights Firebase Auth sign-in config for passwordless email-link mode (`signIn.email.enabled=true` and `signIn.email.passwordRequired=false`) when `FIREBASE_REQUIRE_EMAIL_LINK_SIGNIN=1` (default). Verification is manual-first (no auto-enable patching). Token resolution uses ADC (`GOOGLE_APPLICATION_CREDENTIALS`) and falls back to Firebase CLI login token cache.
- `scripts/firebase-deploy.sh` now prints a manual Firebase Auth setup overview during deploy (sign-in method, email template branding, authorized domains). `FIREBASE_AUTH_EMAIL_APP_NAME` (default `Skybridge`) is used as the friendly name hint in that overview only. Firebase Console currently requires Google sign-in provider enabled before "Public-facing name" can be edited in Auth templates.
- `scripts/firebase-deploy.sh` also preflights Firebase Auth `authorizedDomains` (used by email-link `continueUrl`) and supports explicit overrides via `FIREBASE_AUTHORIZED_DOMAINS` (comma-separated hostnames). Custom domains are enforced as required; default project domains are warning-only because Firebase can treat them as implicitly allowed.
- Authorized-domain preflight strictness is configurable via `FIREBASE_REQUIRE_AUTHORIZED_DOMAINS` and defaults to hard-fail (`1`) unless explicitly overridden.
- `scripts/firebase-deploy.sh` installs frontend dependencies via `scripts/npm-ci-frontend.sh` (nested npm strategy, cache isolation, one automatic retry) to reduce intermittent install failures.
- `scripts/firebase-deploy.sh` now gates deploy on `npm --prefix src/frontend run test:runtime-smoke` to fail fast on frontend runtime crashes (for example React update-depth loops) before remote deploy.
- `scripts/firebase-deploy.sh` stages `src/backend` and `src/core` into `functions/_deploy_src/src` during deploy so Cloud Functions runtime includes shared Python modules, then restores prior workspace state on exit.
- Functions region is consolidated through shared config (`FIREBASE_REGION`, default `europe-west1`) for both production deploys and local emulator/proxy routing; per-run overrides remain supported.
- Local emulator startup keeps `functions/venv` as a symlink to a container-local venv (`/firebase-emulator/functions-venv` volume path inside the container) so Firebase Functions discovery works even when host-created venv binaries are incompatible.
- Local emulator import/export state is consolidated in a single workspace folder: `.firebase-emulator/exports` (legacy root-level `firebase-export-*` artifacts are auto-moved to `.firebase-emulator/exports/legacy` on startup).
- Local emulator startup enforces email-link auth parity by writing Auth emulator config in `.firebase-emulator/exports/auth_export/config.json` (`signIn.email.enabled=true`, `passwordRequired=false`) when `FIREBASE_REQUIRE_EMAIL_LINK_SIGNIN=1` (default).
- Local emulator startup also adds `functions-venv/bin/python3.11 -> python` plus `functions-venv/lib/python3.11 -> lib/python3.12` compatibility links so Firebase Tools can resolve Python Functions SDK checks that expect Python 3.11 paths.
- Local emulator startup auto-rebuilds the container venv if `functions-venv/bin/activate` still points at an old path (for example `/workspace/.firebase-emulator/...`) to avoid Firebase Functions SDK discovery failures after mount-path migrations.
- Firebase Hosting custom-domain setup guidance is documented in `docs/production.md` under `Custom domain setup (Firebase Hosting)`.
- Local dev runs behind `http://skybridge.localhost` with emulator subdomains (`auth.skybridge.localhost`, `firestore.skybridge.localhost`, `ui.skybridge.localhost`) instead of localhost ports.
- `python -m src.core.cli --review` — run the CLI locally (requires Python deps).
- CLI supports `--start-date` / `--end-date` for targeted imports (YYYY-MM-DD or ISO8601).
- `pytest` — run backend tests (if installed).
- `devcontainer exec --workspace-folder . pytest` — run backend tests in the devcontainer.
- `devcontainer exec --workspace-folder . npm --prefix src/frontend run test` — run frontend unit tests in the devcontainer.
- `devcontainer exec --workspace-folder . npm --prefix src/frontend run test:e2e` — run frontend e2e tests in the devcontainer.
- `npm --prefix src/frontend run logo:generate` — regenerate logo-derived assets (header/footer logos, favicon set, web manifest icons, social preview `public/social-preview.png` at `1280x640`) from `design/logo/skybridge-logo-2048x2048.webp` (or pass a custom source path as an argument; requires ImageMagick: `magick` or `convert`).

## Coding Style & Naming Conventions
- Indentation: 2 spaces by default; follow language-specific conventions where standard (e.g., Python 4 spaces).
- Filenames: use `PascalCase` or `camelCase` for code modules per language norms.
- Add a formatter/linter config (`.editorconfig`, `prettier`, `ruff`, `gofmt`, etc.) and keep it enforced in CI.

## Testing Guidelines
- Prefer a dedicated test framework appropriate to the language (e.g., `pytest`, `jest`, `go test`).
- Name tests with a clear suffix/prefix (example: `*_test.py`, `*.spec.ts`).
- Keep unit tests close to modules or in `tests/` with mirrored structure.
- Always run frontend tests via the devcontainer (`devcontainer exec --workspace-folder . npm --prefix src/frontend run test`) before reporting changes.
- Bugs: add regression test when it fits.

## Commit & Pull Request Guidelines
- Use Conventional Commits (`feat:`, `fix:`, `chore:`).
- PRs should include: a concise description, linked issue (if applicable), test results, and screenshots for UI changes.
- Follow CONTRIBUTING.md PR format (Goal / Scope / Testing / Risk / Screenshots) when creating or editing PRs.
- Never use escaped newline sequences (`\n`) in PR bodies; always use real line breaks.
- Work in feature branches for non-trivial changes (e.g., `feature/...`, `fix/...`), then merge into `main`.
 - When asked to open a PR, prepare the full PR (title + body) without further prompts, using the CONTRIBUTING.md format and including tests/scope/risk as applicable.

## Code Review Handling
- When asked to incorporate PR feedback, fetch the exact review comment first (via `gh` API) and implement the requested change in code.
- Validate the change with the smallest relevant checks (for example syntax/lint/test command tied to the touched files).
- Commit and push using a Conventional Commit message that reflects the review fix.
- Reply directly to the review comment summarizing what changed and what validation ran.
- Resolve the review thread after the fix is pushed and the reply is posted.

## Visual PR Screenshot Workflow
- Canonical process is defined in `CONTRIBUTING.md` under `Visual Screenshot Workflow (required for visual PRs)`.
- For any visual/UI PR, follow that section as the source of truth (do not duplicate or diverge workflow rules in other docs).

## Agent Update Policy
- If you add or change developer workflows, commands, or project structure, update this file in the same change set.
- Always update project tracker files (e.g., `PROJECT_PLAN.md`) when material progress or blockers occur, without waiting for a reminder.

## Security & Configuration Tips
- Never commit secrets. Use `.env` files and add an `.env.example` template.
- Redact credentials from discovery artifacts in `data/discovery` before committing or sharing.
- Document required environment variables and local setup steps in `README.md`.
