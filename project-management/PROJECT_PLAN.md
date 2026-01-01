# Project Plan (Web App)

## Goal
Build the production web app for the CloudAhoy → FlySto import flow using the wireframe as the single UI reference.

## Constraints
- Use default component library styling wherever possible.
- Stick to the wireframe (no mockup‑specific visuals).
- Support light/dark mode toggle.

## Milestones
1. **Plan + UI Inventory**
   - Components: accordion steps, progress card, summary chips, tables, CTAs, info panels.
   - States: signed‑out, signed‑in, connected, review running/complete, import running/complete.
2. **UI Skeleton**
   - Layout: header, left nav (sticky), main accordion stack, footer.
   - Theme toggle wired to tokens.
3. **State + Flow**
   - Finite‑state flow for steps, locked/readonly behavior.
   - Button enable/disable rules and progress polling placeholders.
4. **API Integration**
   - Auth (OIDC), review start, import approval, progress polling, report download.
   - Error states + retries.
5. **Polish + QA**
   - Accessibility (focus, ARIA), responsive checks, copy finalization.

## Current Focus
- Solidify component inventory and state model against the wireframe.

## Open Questions
- API contract finalization for progress and report download.
- Theme token source (CSS variables vs. Tailwind config).
