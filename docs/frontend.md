# Frontend Architecture

## Overview
The frontend is a Vite SPA (`src/frontend/`) plus a static landing page and legal pages. The SPA talks to the API via the base URL below.

## Entry points
- Landing page: `src/frontend/index.html`
- SPA app: `src/frontend/app/index.html`
- Privacy page: `src/frontend/privacy/index.html`
- Imprint page: `src/frontend/imprint/index.html`

## Runtime config
- `VITE_API_BASE_URL` — API Gateway base URL
- `VITE_AUTH_MODE` — `oidc`
- `VITE_AUTH_ISSUER_URL` — OIDC issuer
- `VITE_AUTH_CLIENT_ID` — OIDC client id
- `VITE_AUTH_REDIRECT_PATH` — `/app/auth/callback`
- `VITE_AUTH_LOGOUT_URL` — IdP logout URL
