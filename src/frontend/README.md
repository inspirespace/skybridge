# Skybridge Frontend

Source: `src/frontend/`

## Purpose
Production web UI for the CloudAhoy → FlySto import flow. The wireframe is the single UI reference:
`design/final/skybridge-import-flow-wireframe.html`

## Tech
- React + Vite + TypeScript
- Tailwind + shadcn/ui (default component styles)
- IBM Plex Sans (local via @fontsource)
- Light/Dark theme toggle

## Local Dev (Compose)
- `docker compose up --build`
- App: `https://skybridge.localhost`
- API: `https://skybridge.localhost/api`
- Auth (Keycloak): `https://auth.skybridge.localhost`

## State Model
See `src/state/flow.ts` for flow state, open-step logic, and CTA rules.

## API Wiring (Dev)
- Uses backend `/jobs` endpoints via `VITE_API_BASE_URL` (defaults to `https://skybridge.localhost/api`).
- Auth mode controlled via `VITE_AUTH_MODE`:
  - `header` (dev stub) sends `X-User-Id`.
  - `oidc` uses PKCE + `/api/auth/token` exchange and sends Bearer tokens.

### OIDC Env (Dev)
Set in docker compose for local dev:
- `VITE_AUTH_ISSUER_URL`
- `VITE_AUTH_CLIENT_ID`
- `VITE_AUTH_SCOPE`
- `VITE_AUTH_REDIRECT_PATH` (defaults to `/auth/callback`)
- `VITE_AUTH_PROVIDER_PARAM` (`idp_hint` for Keycloak)
- `VITE_AUTH_LOGOUT_URL` (optional end-session endpoint)

### Dev Credential Prefill
Only in Vite dev mode (`import.meta.env.DEV`) when `VITE_DEV_PREFILL_CREDENTIALS=1`:
- `VITE_CLOUD_AHOY_EMAIL`, `VITE_CLOUD_AHOY_PASSWORD`
- `VITE_FLYSTO_EMAIL`, `VITE_FLYSTO_PASSWORD`

## Component Inventory (Mapped from Wireframe)
- Layout: header, sticky left nav, footer
- Steps: accordion sections (sign-in, connect, review, import)
- Cards: progress card, info alert, summary chips, tables
- CTAs: primary/secondary/outline/tertiary buttons
