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

## State Model (Mocked)
See `src/state/flow.ts` for flow state, open-step logic, and CTA rules.

## Component Inventory (Mapped from Wireframe)
- Layout: header, sticky left nav, footer
- Steps: accordion sections (sign-in, connect, review, import)
- Cards: progress card, info alert, summary chips, tables
- CTAs: primary/secondary/outline/tertiary buttons
