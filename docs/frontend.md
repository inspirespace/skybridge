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
- `VITE_AUTH_MODE` — `firebase` (Firebase Auth / Identity Platform)
- `VITE_FIREBASE_API_KEY` — Firebase/Identity Platform web API key
- `VITE_FIREBASE_AUTH_DOMAIN` — `<project-id>.firebaseapp.com`
- `VITE_FIREBASE_PROJECT_ID` — GCP project id
- `VITE_FIREBASE_APP_ID` — Firebase app id
- `VITE_FIREBASE_USE_EMULATOR` — `1` to use local emulator
- `VITE_FIREBASE_AUTH_EMULATOR_HOST` — auth emulator host (e.g. `https://auth.skybridge.localhost`)
