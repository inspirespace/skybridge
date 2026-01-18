# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Skybridge migrates CloudAhoy flight history into FlySto. It's a serverless application with a Python backend (Firebase Functions 2nd gen), React frontend (Vite), and Firebase infrastructure (Firestore, Storage, Pub/Sub, Auth).

## Commands

### Local Development
```sh
docker compose up --build   # Start full stack (Firebase emulators, API, worker, frontend, HTTPS proxy)
```
Open https://skybridge.localhost (requires mkcert certs in `docker/https/certs/`).

### Backend Tests
```sh
devcontainer exec --workspace-folder . pytest                    # Run all tests
devcontainer exec --workspace-folder . pytest tests/test_foo.py  # Run single file
```

### Frontend Tests
```sh
devcontainer exec --workspace-folder . npm --prefix src/frontend run test      # Unit tests (Vitest)
devcontainer exec --workspace-folder . npm --prefix src/frontend run test:e2e  # E2E tests (Playwright)
```

### Build & Lint
```sh
npm --prefix src/frontend run build  # TypeScript + Vite build
npm --prefix src/frontend run lint   # ESLint
```

### Deploy
CI deploys from `main` via `.github/workflows/firebase-deploy.yml`. Manual:
```sh
npm --prefix src/frontend run build
firebase deploy --only functions,hosting --project <project_id>
```

## Architecture

### Repository Layout
- `src/core/` — CLI and core migration logic
- `src/backend/` — API handlers, service layer, store, auth
- `src/frontend/` — Vite SPA + static pages (landing, privacy, imprint)
- `functions/` — Firebase Functions entrypoints (2nd gen)
- `tests/` — Backend tests (pytest)
- `docker/` — Local infra configs (Caddy HTTPS proxy)

### Key Entry Points
- CLI: `./cloudahoy2flysto` (interactive review → approve → import)
- API handlers: `src/backend/lambda_handlers.py`
- Firebase Functions: `functions/main.py`
- Frontend app: `src/frontend/app/index.html` → `src/App.tsx`

### Backend Flow
1. UI starts job → API writes Firestore state + publishes Pub/Sub message
2. Worker consumes Pub/Sub → runs migration pipeline
3. Worker updates Firestore + uploads artifacts to Storage
4. UI polls status and downloads artifacts

### Tech Stack
- **Frontend**: React 19, Vite, TypeScript, Tailwind CSS, Shadcn/ui
- **Backend**: FastAPI, Firebase Functions (Python 3.10+), Firestore, Cloud Storage, Pub/Sub
- **Testing**: pytest (backend), Vitest + Playwright (frontend)
- **Package Management**: uv (Python), npm (frontend)

## Development Guidelines

- Run tests in the devcontainer for consistent dependencies (especially Playwright)
- Use Conventional Commits (`feat:`, `fix:`, `chore:`)
- PRs follow CONTRIBUTING.md format: Goal / Scope / Testing / Risk / Screenshots
- Local dev uses `.localhost` domains (macOS resolves automatically; other OS needs hosts entries)
- Generate HTTPS certs once with `mkcert` (see README.md)

## Documentation

Detailed architecture docs in `docs/`:
- `backend-architecture.md` — Serverless flow, Firestore/Storage/Pub/Sub design
- `frontend.md` — Frontend entry points, Firebase Auth setup
- `production.md` — Environment variables, Firebase resources, deploy checklist
- `testing.md` — Test commands and devcontainer usage
