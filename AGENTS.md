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
- Keycloak dev realm import lives in `docker/keycloak/`.
- Infrastructure-as-code lives under `infra/terraform/`.
- If you adopt a different layout, document it here with concrete paths (example: `cmd/`, `internal/`, `pkg/` for Go).

## Build, Test, and Development Commands
- `docker compose up --build` — run the local dev stack (API, worker, DynamoDB Local, MinIO, Keycloak, SQS).
- `python -m src.core.cli --review` — run the CLI locally (requires Python deps).
- CLI supports `--start-date` / `--end-date` for targeted imports (YYYY-MM-DD or ISO8601).
- `pytest` — run backend tests (if installed).
- `devcontainer exec --workspace-folder . pytest` — run backend tests in the devcontainer.
- `devcontainer exec --workspace-folder . npm --prefix src/frontend run test` — run frontend unit tests in the devcontainer.
- `devcontainer exec --workspace-folder . npm --prefix src/frontend run test:e2e` — run frontend e2e tests in the devcontainer.
- `terraform fmt -check -recursive` (run from `infra/terraform`) — format check for IaC.

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

## Agent Update Policy
- If you add or change developer workflows, commands, or project structure, update this file in the same change set.
- Always update project tracker files (e.g., `PROJECT_PLAN.md`) when material progress or blockers occur, without waiting for a reminder.

## Security & Configuration Tips
- Never commit secrets. Use `.env` files and add an `.env.example` template.
- Redact credentials from discovery artifacts in `data/discovery` before committing or sharing.
- Document required environment variables and local setup steps in `README.md`.
