# Repository Guidelines

This repository contains a Dockerized Python CLI with Playwright-based automation. Keep this file accurate as the project evolves; update it whenever new commands, layouts, or workflows are introduced.

## Project Structure & Module Organization
- Place application/source code under `src/`.
- Put tests under `tests/` or `test/` (match your framework).
- Keep scripts in `scripts/`, assets in `assets/`, and config files at the repo root.
- Keycloak dev realm import lives in `docker/keycloak/`.
- Infrastructure-as-code lives under `infra/terraform/`.
- If you adopt a different layout, document it here with concrete paths (example: `cmd/`, `internal/`, `pkg/` for Go).

## Build, Test, and Development Commands
- `./scripts/cleanup-merged-branches.sh` — delete local branches already merged into `main` and prune remotes.
- `docker build -t skybridge .` — build the image.
- `./scripts/run-review.sh` — run review mode via Docker (default `MAX_FLIGHTS=5`).
- `./scripts/run-import.sh` — run approved import using the latest `data/review.json`.
- `./scripts/run-discovery.sh` — run endpoint discovery via the dedicated discovery CLI (outputs to `data/discovery`).
- `./scripts/run.sh --approve-import --max-flights 5` — run the CLI with explicit options (container named `skybridge`).
- `./scripts/run.sh --approve-import` — writes artifacts under `data/runs/<RUN_ID>/` (review, report, exports, logs, state).
- `./scripts/run.sh --verify-import-report --import-report data/runs/<RUN_ID>/import_report.json` — verify report entries against FlySto.
- `./scripts/run-backend-dev.sh` — run the backend dev web (FastAPI API + UI) locally.
- `./scripts/setup-dev-https.sh` — install mkcert CA and generate trusted dev certs for HTTPS (Caddy).
- `docker compose up --build` — run the backend dev stack (API, worker, DynamoDB Local, MinIO).
- Backend dev auth uses Keycloak OIDC in Docker Compose (login with `demo` / `demo-password`); local runs should set `AUTH_MODE=oidc`, `AUTH_ISSUER_URL`, `AUTH_BROWSER_ISSUER_URL`, and `AUTH_CLIENT_ID`.
- `./scripts/build-lambda.sh` — package the Lambda handlers to `infra/terraform/lambda/backend-handlers.zip`.
- `python -m src.cli --review` — run locally (requires Python deps).
- CLI supports `--start-date` / `--end-date` for targeted imports (YYYY-MM-DD or ISO8601).
- Set `CLOUD_AHOY_G3X_INCLUDE_HDG=1` to include heading in G3X exports (TRK is always included; default omits HDG to preserve block-time detection).
- `pytest` — run tests (if installed).
- `terraform fmt -check -recursive` (run from `infra/terraform`) — format check for IaC.
- Runbook + readiness docs are in `docs/backend-runbook.md`, `docs/backend-maintenance.md`, and `docs/backend-release-readiness.md`.
- Run all CLI workflows through the devcontainer scripts (`./scripts/run*.sh`) so required dependencies and browser tooling are available.
- Devcontainer post-start uninstalls GitHub Copilot/Copilot Chat to avoid invalid-extension warnings.
- Devcontainer installs GitHub CLI via the `github-cli` feature for authenticated GH access.
- Devcontainer ensures Node is on PATH for Codex and installs Codex zsh completions automatically.
- Devcontainer persists GitHub CLI auth under a mounted volume at `/home/vscode/.config/gh`.
- Devcontainer disables zsh-autosuggestions to avoid duplicated paste input in the terminal.
Note: default `MODE=auto` uses API only and does not fall back to web automation.

## Coding Style & Naming Conventions
- Indentation: 2 spaces by default; follow language-specific conventions where standard (e.g., Python 4 spaces).
- Filenames: use `kebab-case` for scripts, `PascalCase` or `camelCase` for code modules per language norms.
- Add a formatter/linter config (`.editorconfig`, `prettier`, `ruff`, `gofmt`, etc.) and keep it enforced in CI.

## Testing Guidelines
- Prefer a dedicated test framework appropriate to the language (e.g., `pytest`, `jest`, `go test`).
- Name tests with a clear suffix/prefix (example: `*_test.py`, `*.spec.ts`).
- Keep unit tests close to modules or in `tests/` with mirrored structure.

## Commit & Pull Request Guidelines
- Use Conventional Commits (`feat:`, `fix:`, `chore:`).
- PRs should include: a concise description, linked issue (if applicable), test results, and screenshots for UI changes.
- Work in feature branches for non-trivial changes (e.g., `feature/...`, `fix/...`), then merge into `main`.
- After merging, delete merged feature branches and prune remotes (use `./scripts/cleanup-merged-branches.sh`).

## Agent Update Policy
- If you add or change developer workflows, commands, or project structure, update this file in the same change set.
- Always update `CONTEXT.md` and any project tracker files (e.g., `PROJECT_PLAN.md`) when material progress or blockers occur, without waiting for a reminder.

## Security & Configuration Tips
- Never commit secrets. Use `.env` files and add an `.env.example` template.
- Redact credentials from discovery artifacts in `data/discovery` before committing or sharing.
- Document required environment variables and local setup steps in `README.md`.
