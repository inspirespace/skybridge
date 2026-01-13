# Testing

Run tests inside the devcontainer to ensure consistent dependencies (especially Playwright).

## Backend
- `pytest` (inside devcontainer)
- `devcontainer exec --workspace-folder . pytest`

## Frontend
- `devcontainer exec --workspace-folder . npm --prefix src/frontend run test`
- `devcontainer exec --workspace-folder . npm --prefix src/frontend run test:e2e`
