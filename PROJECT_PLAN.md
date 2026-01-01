# Project Plan (Web App)

## UI Plan (Wireframe‑Only, Default Components)

### Done
- [x] Wireframe finalized as the single UI reference (`design/final/skybridge-import-flow-wireframe.html`).
- [x] Review step layout simplified (helper line in progress card + summary chips).
- [x] Copy clarified (review/import labels, CTA wording, helper text, status pills).
- [x] Layout rules captured (sticky left nav, accordion steps, progress cards, tables, footer).
- [x] Mobile rules captured (top bar actions, bottom stepper, stacked inputs, scrollable tables).
- [x] Confirmed: use default component library styling wherever possible.
- [x] Confirmed: light/dark mode toggle required.

### To Do
- [ ] Translate wireframe into a component inventory (accordion, progress card, chips, table, CTA bar, info panels).
- [ ] Define state machine for the flow (signed‑out → signed‑in → connected → review running → review complete → import running → import complete).
- [ ] Decide theme strategy (CSS vars vs. Tailwind tokens) and implement light/dark toggle.
- [ ] Build layout shell (header, sticky left nav, accordion stack, footer) using default components.
- [ ] Implement step components with real state wiring (locked/readonly behavior, CTA enablement).
- [ ] Add mocked API layer and polling hooks for review/import progress.
- [ ] Connect to backend endpoints (auth, review start, import approval, progress polling, report download).
- [ ] Add error/empty states and retry UX for each step.
- [ ] Accessibility pass (focus order, ARIA, keyboard nav).
- [ ] Responsive QA on mobile/tablet/desktop.

## Open Questions
- [ ] Confirm API contracts for progress polling and report download.
- [ ] Confirm where theme tokens should live (global CSS vs. design‑system config).
