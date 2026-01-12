# Frontend Architecture

Location: `src/frontend/`

## Overview
The frontend is a React + Vite app that implements the wireframe in
`design/final/skybridge-import-flow-wireframe.html` using shadcn/ui components
with minimal customization. The UI is intentionally minimal and relies on
default component styling, with light/dark themes and a small set of custom
tokens for layout polish.

## Routes
- `/` – main import flow (accordion).
- `/imprint` – legal imprint page.
- `/privacy` – privacy policy.

## Key concepts
- **Accordion flow**: The app shows 4 steps (Sign in → Connect → Review → Import).
- **Single-run model**: The UI always operates on one active job per user.
- **State machine**: `src/frontend/src/state/flow.ts` derives the step state from
  the current job status and gates navigation accordingly.
- **Job updates**: `useJobSnapshot` polls for updates in serverless mode.
- **Mock mode**: Dev uses `DEV_USE_MOCKS=1` to simulate CloudAhoy/FlySto flows.

## Main modules
- `src/frontend/src/App.tsx`
  - Page router (app vs static pages)
  - Global state & step orchestration
  - API calls for create/review/import/delete/download
- `src/frontend/src/state/flow.ts`
  - Derived flow state + step gating
- `src/frontend/src/state/mock-api.ts`
  - Mocked responses for the full flow
- `src/frontend/src/hooks/use-job-snapshot.ts`
  - Polling-based job updates
- `src/frontend/src/components/app/*`
  - Step sections + reusable layout pieces
- `src/frontend/src/components/ui/*`
  - shadcn/ui components (button, calendar, dialogs, etc.)

## Styling
- Tailwind + shadcn/ui
- Light/Dark theme toggle (`ThemeToggle`)
- IBM Plex Sans loaded locally via `@fontsource/ibm-plex-sans`
- Design tokens live in `src/frontend/src/index.css`

## Auth
- `VITE_AUTH_MODE=header` (dev) uses `X-User-Id` headers.
- `VITE_AUTH_MODE=oidc` uses PKCE and `/api/auth/token` exchange.
- `/auth/callback` is handled by `App.tsx` and then redirects to `/`.

## Environment variables
- `VITE_AUTH_MODE` – `header` (dev) or `oidc` (prod-like).
- `VITE_AUTH_ISSUER`, `VITE_AUTH_CLIENT_ID`, `VITE_AUTH_SCOPE` – OIDC config.
- `VITE_API_BASE_URL` – API base (default `/api`).
- `VITE_DEV_PREFILL_CREDENTIALS=1` – prefill credentials in dev only.

## Tests
- Unit/integration: Vitest + RTL
- E2E: Playwright (see `src/frontend/e2e/`)
