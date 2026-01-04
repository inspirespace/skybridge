# Frontend Architecture

Location: `src/frontend/`

## Overview
The frontend is a React + Vite app that implements the wireframe in
`design/final/skybridge-import-flow-wireframe.html` using shadcn/ui components
with minimal customization.

## Key concepts
- **Accordion flow**: The app shows 4 steps (Sign in → Connect → Review → Import).
- **Single-run model**: The UI always operates on one active job per user.
- **State machine**: `src/frontend/src/state/flow.ts` derives the step state from
  the current job status.
- **SSE updates**: `useJobSnapshot` tries SSE first and falls back to polling.

## Main modules
- `src/frontend/src/App.tsx`
  - Page router (app vs static pages)
  - Global state & step orchestration
  - API calls for create/review/import/delete/download
- `src/frontend/src/state/flow.ts`
  - Derived flow state + step gating
- `src/frontend/src/hooks/use-job-snapshot.ts`
  - SSE subscription + polling fallback
- `src/frontend/src/components/app/*`
  - Step sections + reusable layout pieces

## Styling
- Tailwind + shadcn/ui
- Light/Dark theme toggle (`ThemeToggle`)
- IBM Plex Sans loaded locally via `@fontsource/ibm-plex-sans`

## Auth
- `VITE_AUTH_MODE=header` (dev) uses `X-User-Id` headers.
- `VITE_AUTH_MODE=oidc` uses PKCE and `/api/auth/token` exchange.

## Tests
- Unit/integration: Vitest + RTL
- E2E: Playwright (see `src/frontend/e2e/`)
