# Repository Guidelines

This repository contains a Dockerized Python CLI with Playwright-based automation. Keep this file accurate as the project evolves; update it whenever new commands, layouts, or workflows are introduced.

## Project Structure & Module Organization
- Place application/source code under `src/`.
- Put tests under `tests/` or `test/` (match your framework).
- Keep assets in `assets/`, and config files at the repo root.
- Inspector scripts live in `tools/inspector/` (dev-only helpers).
- VNC helpers for Playwright live in `scripts/` (devcontainer use only).
- User-facing scripts: `scripts/cleanup-merged-branches.sh` (branch cleanup), `scripts/clean-workspace.sh` (local dependency/build/log cleanup), and `scripts/firebase-deploy.sh` (shared local/CI Firebase deploy flow).
- Frontend entry points: landing page in `src/frontend/index.html`, SPA app in `src/frontend/app/index.html`, static legal pages in `src/frontend/privacy/index.html` and `src/frontend/imprint/index.html`.
- Infrastructure-as-code is not tracked in this repository (Firebase-only deployment).
- Firebase emulators are configured by `firebase.json` and `.firebaserc`.
- Firebase Functions entrypoints live in `functions/`.
- `docker-compose.yml` runs the Firebase emulators + Functions for local dev.
- If you adopt a different layout, document it here with concrete paths (example: `cmd/`, `internal/`, `pkg/` for Go).

## Build, Test, and Development Commands
- `docker compose up --build` — run the local dev stack (Firebase emulators, API, worker, frontend, HTTPS proxy, mocks).
- VS Code launch configs: `Stack: Start (Docker Compose)`, `Stack: Stop (Docker Compose)`, `Stack: Build (Docker Compose)` in `.vscode/launch.json`.
- VS Code tasks: `Compose: Up (detached)`, `Compose: Down`, `Compose: Build`, `Firebase: Deploy (Functions + Hosting)`, `Workspace: Clean`, `Git: Cleanup Merged Branches` in `.vscode/tasks.json`.
- Devcontainer startup attempts to install Firebase CLI (`firebase-tools`) when missing; if npm is unreachable, setup continues and `firebase` remains unavailable until install succeeds.
- Devcontainer tooling is pinned to Python `3.11` to match Firebase Functions runtime `python311`.
- Devcontainer post-start uses user-owned caches (`$HOME/.cache/npm`, `$HOME/.cache/uv`) to avoid permission issues from shared `/tmp` cache directories.
- Devcontainer startup disables npm update-notifier noise (`NPM_CONFIG_UPDATE_NOTIFIER=false`) for cleaner rebuild logs.
- Devcontainer VNC/noVNC setup is best-effort during post-start; failures are logged as warnings and do not block startup.
- Devcontainer image includes ImageMagick binaries for frontend asset generation commands (`convert`, `identify`, etc.).
- Firebase deploy workflow lives in `.github/workflows/firebase-deploy.yml` and requires `FIREBASE_PROJECT_ID` + `FIREBASE_SERVICE_ACCOUNT` secrets.
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
