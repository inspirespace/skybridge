# Repository Guidelines

This repository contains a Dockerized Python CLI with Playwright-based automation. Keep this file accurate as the project evolves; update it whenever new commands, layouts, or workflows are introduced.

## Project Structure & Module Organization
- Place application/source code under `src/`.
- Put tests under `tests/` or `test/` (match your framework).
- Keep scripts in `scripts/`, assets in `assets/`, and config files at the repo root.
- If you adopt a different layout, document it here with concrete paths (example: `cmd/`, `internal/`, `pkg/` for Go).

## Build, Test, and Development Commands
- `docker build -t cloudahoy2flysto .` — build the image.
- `./scripts/run-review.sh` — run review mode via Docker (default `MAX_FLIGHTS=5`).
- `docker run --rm --env-file .env cloudahoy2flysto --mode hybrid --approve-import --max-flights 5` — run approved import.
- `python -m src.cli --review` — run locally (requires Python deps).
- `pytest` — run tests (if installed).

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

## Agent Update Policy
- If you add or change developer workflows, commands, or project structure, update this file in the same change set.
- Always update `CONTEXT.md` and any project tracker files (e.g., `PROJECT_PLAN.md`) when material progress or blockers occur, without waiting for a reminder.

## Security & Configuration Tips
- Never commit secrets. Use `.env` files and add an `.env.example` template.
- Document required environment variables and local setup steps in `README.md`.
