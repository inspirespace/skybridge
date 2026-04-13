# Reply Patterns

Keep replies concrete and scoped to the thread.

## Applied Change

Use when the comment led to a code or test change.

Template:
`Applied in <commit-or-branch-state>. <brief technical change>. Validation: <command or check>.`

Example:
`Applied in 1a2b3c4. Normalized the storage bucket fallback in the deploy preflight so missing Firebase SDK config no longer crashes deploys. Validation: pytest tests/test_firebase_deploy.py.`

## Already Satisfied

Use when the requested behavior is already present on the PR branch.

Template:
`No code change needed. <existing file/behavior> already handles this by <mechanism>. Verified via <file, diff, or command>.`

Example:
`No code change needed. src/backend/env.py already centralizes region resolution through resolve_region(), so this callsite inherits the shared default. Verified in the current branch diff.`

## Not Adopting

Use when the suggestion would be incorrect or would regress behavior.

Template:
`Not applying this change. <brief technical reason>. Verified against <code path, test, or product constraint>.`

Example:
`Not applying this change. Reintroducing the per-callsite fallback would bypass the shared Firebase project resolver and reopen the inconsistent-config bug. Verified against src/backend/env.py and the deploy path.`
