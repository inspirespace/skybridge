# Testing

## Backend
- Unit/integration tests: `pytest`
- Devcontainer: `devcontainer exec --workspace-folder . pytest`

## Frontend
- Unit/integration: Vitest + RTL
  - `devcontainer exec --workspace-folder . npm --prefix src/frontend run test`
- E2E: Playwright
  - `devcontainer exec --workspace-folder . npm --prefix src/frontend run test:e2e`

## CI
- Backend tests: `.github/workflows/ci.yml` (pytest)
- Frontend unit + e2e: `.github/workflows/ci.yml`
