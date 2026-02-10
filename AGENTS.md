# Repository Guidelines

This repository contains a Dockerized Python CLI with Playwright-based automation. Keep this file accurate as the project evolves; update it whenever new commands, layouts, or workflows are introduced.

## Project Structure & Module Organization
- Place application/source code under `src/`.
- Put tests under `tests/` or `test/` (match your framework).
- Keep assets in `assets/`, and config files at the repo root.
- Inspector scripts live in `tools/inspector/` (dev-only helpers).
- VNC helpers for Playwright live in `scripts/` (devcontainer use only).
- `scripts/cleanup-merged-branches.sh` is the only user-facing script (branch cleanup).
- Frontend entry points: landing page in `src/frontend/index.html`, SPA app in `src/frontend/app/index.html`, static legal pages in `src/frontend/privacy/index.html` and `src/frontend/imprint/index.html`.
- Infrastructure-as-code is not tracked in this repository (Firebase-only deployment).
- Firebase emulators are configured by `firebase.json` and `.firebaserc`.
- Firebase Functions entrypoints live in `functions/`.
- `docker-compose.yml` runs the Firebase emulators + Functions for local dev.
- If you adopt a different layout, document it here with concrete paths (example: `cmd/`, `internal/`, `pkg/` for Go).

## Build, Test, and Development Commands
- `docker compose up --build` — run the local dev stack (Firebase emulators, API, worker, frontend, HTTPS proxy, mocks).
- VS Code launch configs: `Stack: Start (Docker Compose)`, `Stack: Stop (Docker Compose)`, `Stack: Build (Docker Compose)` in `.vscode/launch.json`.
- VS Code tasks: `Compose: Up (detached)`, `Compose: Down`, `Compose: Build` in `.vscode/tasks.json`.
- Firebase deploy workflow lives in `.github/workflows/firebase-deploy.yml` and requires `FIREBASE_PROJECT_ID` + `FIREBASE_SERVICE_ACCOUNT` secrets.
- Local dev runs behind `http://skybridge.localhost` with emulator subdomains (`auth.skybridge.localhost`, `firestore.skybridge.localhost`, `ui.skybridge.localhost`) instead of localhost ports.
- `python -m src.core.cli --review` — run the CLI locally (requires Python deps).
- CLI supports `--start-date` / `--end-date` for targeted imports (YYYY-MM-DD or ISO8601).
- `pytest` — run backend tests (if installed).
- `devcontainer exec --workspace-folder . pytest` — run backend tests in the devcontainer.
- `devcontainer exec --workspace-folder . npm --prefix src/frontend run test` — run frontend unit tests in the devcontainer.
- `devcontainer exec --workspace-folder . npm --prefix src/frontend run test:e2e` — run frontend e2e tests in the devcontainer.
- `npm --prefix src/frontend run logo:generate` — regenerate logo-derived assets (header/footer logos, favicon set, web manifest icons) from `design/logo/skybridge-logo-2048x2048.webp` (or pass a custom source path as an argument; requires `magick` or macOS `sips`).

## Coding Style & Naming Conventions
- Indentation: 2 spaces by default; follow language-specific conventions where standard (e.g., Python 4 spaces).
- Filenames: use `PascalCase` or `camelCase` for code modules per language norms.
- Add a formatter/linter config (`.editorconfig`, `prettier`, `ruff`, `gofmt`, etc.) and keep it enforced in CI.

## Testing Guidelines
- Prefer a dedicated test framework appropriate to the language (e.g., `pytest`, `jest`, `go test`).
- Name tests with a clear suffix/prefix (example: `*_test.py`, `*.spec.ts`).
- Keep unit tests close to modules or in `tests/` with mirrored structure.
- Always run frontend tests via the devcontainer (`devcontainer exec --workspace-folder . npm --prefix src/frontend run test`) before reporting changes.

## Commit & Pull Request Guidelines
- Use Conventional Commits (`feat:`, `fix:`, `chore:`).
- PRs should include: a concise description, linked issue (if applicable), test results, and screenshots for UI changes.
- Follow CONTRIBUTING.md PR format (Goal / Scope / Testing / Risk / Screenshots) when creating or editing PRs.
- Never use escaped newline sequences (`\n`) in PR bodies; always use real line breaks.
- Work in feature branches for non-trivial changes (e.g., `feature/...`, `fix/...`), then merge into `main`.
 - When asked to open a PR, prepare the full PR (title + body) without further prompts, using the CONTRIBUTING.md format and including tests/scope/risk as applicable.

## Visual PR Screenshot Workflow
- Required for PRs that change visuals/UI (landing page, app, legal pages, shared layout/components, theming).
- Capture before/after pairs with the same viewport and framing:
  - Before source must be `main`.
  - After source must be the PR branch.
- Standard desktop viewport is `1440x1100`; add mobile screenshots when mobile layout is affected.
- Capture both light and dark mode for changed screens (`localStorage` key `skybridge-theme`).
- App screenshots must show a real in-app flow state (for example `review_ready`), not only the sign-in screen:
  - Seed deterministic session state and stub API responses as needed for stable visuals.
- Do not commit screenshot binaries to git history for PR evidence (`.png`, `.jpg`, `.webp`).
- Persist screenshot evidence in PR context:
  - Preferred: GitHub PR attachments (description/comment upload via web UI).
  - CLI fallback: PR-specific prerelease assets (for example `pr-<number>-visual-screenshots`) linked from the PR body.
- PR screenshot section must explicitly label:
  - Before branch (`main`) vs after branch (PR head).
  - Light mode and dark mode sets.
  - Direct links fallback when inline image previews fail.
- Before merge, verify screenshots are not in repo diff/history (`git diff --name-only`, `gh pr diff --name-only`).

## Agent Update Policy
- If you add or change developer workflows, commands, or project structure, update this file in the same change set.
- Always update project tracker files (e.g., `PROJECT_PLAN.md`) when material progress or blockers occur, without waiting for a reminder.

## Security & Configuration Tips
- Never commit secrets. Use `.env` files and add an `.env.example` template.
- Redact credentials from discovery artifacts in `data/discovery` before committing or sharing.
- Document required environment variables and local setup steps in `README.md`.
