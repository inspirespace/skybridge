---
name: review-fix
description: Handle GitHub pull request review feedback on the current branch PR or a PR assigned or review-requested to the user. Use when Codex needs to inspect unresolved review threads, decide whether each comment is valid, implement warranted changes, validate them, commit and push the branch when code changed, reply inline to each handled thread, and resolve the thread after the response is posted.
---

# Review Fix

Use this skill when the job is to clear assigned GitHub PR review feedback end-to-end rather than only summarize it. Use the GitHub connector for PR metadata, patch context, and lightweight top-level comment reads, but treat thread-aware review state as a `gh api graphql` problem because the connector comment surface is flat and does not preserve full review-thread state. Use the bundled helper script for deterministic PR discovery, full review-context fetches, replies, and resolution.

Run `gh` commands with network access enabled. Check `gh auth status` first; if authentication fails, stop and ask the user to run `gh auth login`.

## Workflow

1. Resolve the target PR.
   - If the user gives a PR URL, repository, or PR number, use it directly.
   - Otherwise run `python .codex/skills/review-fix/scripts/review_threads.py discover`.
   - Prefer the current branch PR when it exists and is also one of the candidate assigned or review-requested PRs.
   - If discovery returns multiple candidate PRs and the user did not specify one, stop and ask which PR to handle.

2. Load the review state.
   - Fetch PR metadata and patch context with the GitHub connector when file-level context helps evaluate the comment.
   - Fetch thread-aware review data with `python .codex/skills/review-fix/scripts/review_threads.py fetch --repo <owner/repo> --pr <number>`.
   - The helper returns `conversation_comments`, `reviews`, and `review_threads`; use all three when reconstructing review intent.
   - Work from unresolved, non-outdated review threads by default.
   - Use connector-only comment reads only for lightweight top-level PR comment summaries.

3. Cluster actionable feedback.
   - Group related comments by file or behavior area before editing.
   - Separate actionable change requests from informational comments, approvals, duplicates, already-resolved threads, and comments that only need explanation.
   - If a comment only needs explanation, plan a reply instead of forcing a code change.

4. Confirm scope before editing.
   - Present the actionable clusters with a one-line summary of the required change or reply.
   - If the user did not ask to handle everything, ask which clusters to address.
   - If the user asked to handle all review feedback, interpret that as all unresolved actionable threads and call out anything ambiguous before editing.

5. Evaluate each thread before changing code.
   - Classify each unresolved thread as one of: `apply change`, `already satisfied`, `not adopting`, or `blocked`.
   - Mark `apply change` only after confirming the feedback improves correctness, maintainability, style consistency, or test coverage in this repository.
   - Mark `already satisfied` only when the requested behavior or structure already exists on the PR branch.
   - Mark `not adopting` when the feedback is based on a false assumption, duplicates another handled thread, is outdated, or would create a regression or conflict with repo conventions.
   - Mark `blocked` when the thread is ambiguous, conflicts with another reviewer, or requires product or architecture direction that the codebase cannot answer safely.
   - Do not agree with a comment just because it was left in review; verify it against the code, tests, and surrounding diff.

6. Implement and validate the warranted changes.
   - Group compatible `apply change` threads into the smallest sensible patch.
   - Keep each edit traceable back to the thread that motivated it.
   - Run the smallest relevant validation tied to the touched files before replying.
   - If code changed, commit and push before replying or resolving. Use a Conventional Commit message that matches the review fix, for example `fix: address assigned PR review feedback`.
   - If no code changed because the feedback was already satisfied or not adopted, do not create a noop commit.

7. Reply and resolve handled review threads.
   - Reply to the thread first, then resolve it.
   - Use `python .codex/skills/review-fix/scripts/review_threads.py reply --repo <owner/repo> --pr <number> --comment-id <root-comment-id> --body-file <path>` to post the inline response.
   - Use `python .codex/skills/review-fix/scripts/review_threads.py resolve --thread-id <thread-id>` after the reply succeeds.
   - For `apply change`, explain what changed, mention the validation that ran, and include the commit SHA when useful.
   - For `already satisfied`, explain where the behavior already exists and why no code change was needed.
   - For `not adopting`, explain the technical reason concisely and concretely.
   - For `blocked`, do not reply-resolve automatically; summarize the blocker and ask the user how to proceed.

## Response Rules

- Never resolve a review thread without posting a concrete reply in the same pass.
- Never claim a comment was addressed without citing the actual change, existing code path, or validation result.
- Keep replies short and factual. Avoid thanking language or vague promises.
- If the user asks to handle all review feedback, interpret that as all unresolved actionable review threads on the target PR unless the user narrows scope.
- If a thread is already resolved, leave it alone unless the user explicitly asks to revisit it.
- If a top-level PR comment needs an answer, reply to it but note that it cannot be resolved through GitHub review-thread state.
- If review comments conflict with each other or would cause a behavioral regression, surface the tradeoff before making changes.
- If `gh` fails because of auth, repo scope, or rate limits, stop and ask the user to refresh authentication or provide the missing PR context instead of guessing.

Reply patterns live in [references/reply-patterns.md](references/reply-patterns.md). Reuse the helper script instead of rebuilding GraphQL mutations or review-comment reply requests by hand.

## Fallback

- If neither the GitHub connector nor `gh` can resolve the PR cleanly, tell the user whether the blocker is missing repository scope, missing PR context, or CLI authentication.
- If only top-level conversation comments are in scope, reply to them directly and state that GitHub does not expose a thread-resolution action for those comments.
