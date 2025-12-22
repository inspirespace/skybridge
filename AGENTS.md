# Repository Guidelines

This repository is currently empty (no tracked files or Git history detected). The guidance below establishes a lightweight default. Update it as soon as real code and tooling land so it stays accurate.

## Project Structure & Module Organization
- Place application/source code under `src/`.
- Put tests under `tests/` or `test/` (match your framework).
- Keep scripts in `scripts/`, assets in `assets/`, and config files at the repo root.
- If you adopt a different layout, document it here with concrete paths (example: `cmd/`, `internal/`, `pkg/` for Go).

## Build, Test, and Development Commands
No build system is defined yet. When you add one, ensure the primary commands are documented here and runnable from the repo root. Typical examples:
- `make build` — build binaries or bundles.
- `make test` or `npm test` — run the test suite.
- `make dev` or `npm run dev` — start a local dev server.

## Coding Style & Naming Conventions
- Indentation: 2 spaces by default; follow language-specific conventions where standard (e.g., Python 4 spaces).
- Filenames: use `kebab-case` for scripts, `PascalCase` or `camelCase` for code modules per language norms.
- Add a formatter/linter config (`.editorconfig`, `prettier`, `ruff`, `gofmt`, etc.) and keep it enforced in CI.

## Testing Guidelines
- Prefer a dedicated test framework appropriate to the language (e.g., `pytest`, `jest`, `go test`).
- Name tests with a clear suffix/prefix (example: `*_test.py`, `*.spec.ts`).
- Keep unit tests close to modules or in `tests/` with mirrored structure.

## Commit & Pull Request Guidelines
- No Git history detected; default to Conventional Commits (`feat:`, `fix:`, `chore:`) until project-specific rules exist.
- PRs should include: a concise description, linked issue (if applicable), test results, and screenshots for UI changes.

## Security & Configuration Tips
- Never commit secrets. Use `.env` files and add an `.env.example` template.
- Document required environment variables and local setup steps in `README.md`.
