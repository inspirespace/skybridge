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

## Visual Screenshot Workflow (required for visual PRs)
- Capture before/after with identical framing:
  - Before from `main`
  - After from the PR branch
- Default viewport: `1440x1100` desktop; include mobile shots when responsive/mobile UI changed.
- Capture both light and dark mode for affected screens.
- For app screenshots, show an in-app migration state (for example `review_ready`) instead of a login-only state:
  - Seed session state and mock/stub API responses for deterministic capture.
- Keep screenshot evidence out of git history:
  - Do not commit screenshot binaries for PR comparison evidence.
- Store screenshot evidence in PR context:
  - Preferred: GitHub PR attachments (uploaded in description/comment).
  - CLI fallback: PR-specific prerelease assets linked from the PR body.
- In the PR body, include explicit labels (`main` vs PR branch) and a direct-link fallback list.
- Before merge, confirm no screenshot binaries were added to the diff.

## Security and data
- Never commit credentials.
- Ensure mock/test data is used for dev.
- Verify any storage/retention behavior if touched.
