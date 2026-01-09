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

## Tests (Devcontainer)
- Unit/integration: `devcontainer exec --workspace-folder . npm --prefix src/frontend run test`
- E2E (Playwright): `devcontainer exec --workspace-folder . npm --prefix src/frontend run test:e2e`
- E2E headed (macOS + XQuartz): `./scripts/run-e2e-headed.sh`
- E2E headed (no host config): `./scripts/setup-e2e-vnc.sh` then `./scripts/run-e2e-vnc.sh`

### Headed Playwright on macOS (XQuartz)
If the Chromium window opens but stays black, ensure:
- XQuartz → Preferences → Security → "Allow connections from network clients" enabled.
- Restart XQuartz, then run: `xhost +localhost` on the host.
- Use the helper script above (it sets software rendering + DISPLAY to `host.docker.internal:0` if needed).

### Headed Playwright without host configuration
Run inside the devcontainer:
1) `./scripts/setup-e2e-vnc.sh`
2) `./scripts/run-e2e-vnc.sh`

This starts Xvfb + a lightweight WM + VNC + noVNC. Open
`http://localhost:6080/vnc_auto.html?autoconnect=1&resize=remote`
via the forwarded port to see the browser (try `/vnc.html` if needed).
(No passwords, default screen 1280x720.)

To auto-install VNC deps when the devcontainer starts, set:
`DEVCONTAINER_E2E_VNC=1`

For VS Code Testing (Playwright Test UI), the devcontainer now auto-starts
the VNC/noVNC server on `DISPLAY=:99` when `DEVCONTAINER_E2E_VNC=1`.
Playwright also invokes `src/frontend/e2e/setup.ts` to ensure the server is up
when tests are launched from the Testing UI, and will attempt to open the
noVNC URL automatically.

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
