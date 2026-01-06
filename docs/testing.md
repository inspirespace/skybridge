# Testing

## Backend
- Unit/integration tests: `pytest`
- Devcontainer: `devcontainer exec --workspace-folder . pytest`
- VS Code Test Explorer auto-discovers pytest tests via `.vscode/settings.json`.

## Frontend
- Unit/integration: Vitest + RTL
  - `devcontainer exec --workspace-folder . npm --prefix src/frontend run test`
- E2E: Playwright
  - `devcontainer exec --workspace-folder . npm --prefix src/frontend run test:e2e`
- VS Code Test Explorer discovers Vitest and Playwright via extensions in
  `.vscode/extensions.json`.

## CI
- Backend tests: `.github/workflows/ci.yml` (pytest)
- Frontend unit + e2e: `.github/workflows/ci.yml`
