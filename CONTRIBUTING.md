# Contributing

Thanks for helping improve Skybridge! This guide keeps PRs consistent, reviewable, and safe.

## What to include in every PR
- **Goal**: 1–2 sentences describing the user/customer outcome.
- **Scope**: What changed and what did not change.
- **Testing**: How you validated the change (commands, environments).
- **Risk**: Any rollout, data, or UX risk and how it’s mitigated.
- **Screenshots**: Required for UI changes (light + dark if applicable).

## PR writing checklist
- Keep titles **short and specific** (Conventional Commit style).
- Use **bullets** for changes and tests.
- Link issues/tickets if applicable.
- Call out **breaking changes** clearly.

## Testing expectations
- Frontend: `npm test`, `npm run lint`, and e2e where applicable.
- Backend: `pytest` (or targeted tests).

## UI changes
- Verify mobile + desktop.
- Check accessibility basics (contrast, focus, keyboard).
- Ensure copy matches product intent and current wireframes.

## Security and data
- Never commit credentials.
- Ensure mock/test data is used for dev.
- Verify any storage/retention behavior if touched.
