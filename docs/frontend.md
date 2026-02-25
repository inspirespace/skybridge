# Frontend Architecture

## Overview
The frontend is a Vite SPA (`src/frontend/`) plus a static landing page and legal pages. The SPA talks to the API via the base URL below.

## Entry points
- Landing page: `src/frontend/index.html`
- SPA app: `src/frontend/app/index.html`
- Privacy page: `src/frontend/privacy/index.html`
- Imprint page: `src/frontend/imprint/index.html`

## Runtime config
- `VITE_API_BASE_URL` — Firebase Hosting base URL
- `VITE_AUTH_MODE` — `firebase` (defaults from `AUTH_MODE`)
- `VITE_FIREBASE_API_KEY` — Firebase/Identity Platform web API key
- `VITE_FIREBASE_PROJECT_ID` — Firebase project id (optional; defaults from `.firebaserc`)
- `VITE_FIREBASE_AUTH_DOMAIN` — auth domain (optional; defaults to `<project-id>.firebaseapp.com`)
- `VITE_FIREBASE_APP_ID` — Firebase app id
- `VITE_FIREBASE_USE_EMULATOR` — `1` to use local emulator
- `VITE_FIREBASE_AUTH_EMULATOR_HOST` — auth emulator host (e.g. `https://auth.skybridge.localhost`)
- `VITE_FIRESTORE_JOBS_COLLECTION` — optional override (defaults from `FIRESTORE_JOBS_COLLECTION`)
- `VITE_RETENTION_DAYS` — optional override (defaults from `BACKEND_RETENTION_DAYS`)
- `VITE_CLOUD_AHOY_EMAIL` / `VITE_CLOUD_AHOY_PASSWORD` / `VITE_FLYSTO_EMAIL` / `VITE_FLYSTO_PASSWORD` — optional prefill overrides (default from non-`VITE_` credentials)
