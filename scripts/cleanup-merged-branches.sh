#!/usr/bin/env bash
set -euo pipefail

TARGET_BRANCH="${1:-main}"
REMOTE="${2:-origin}"
CURRENT_BRANCH="$(git branch --show-current)"

# Prune remote-tracking refs before cleanup.
git fetch --prune

# Delete local branches that are fully merged into TARGET_BRANCH.
while IFS= read -r branch; do
  if [ -z "${branch}" ] || [ "${branch}" = "${TARGET_BRANCH}" ] || [ "${branch}" = "${CURRENT_BRANCH}" ]; then
    continue
  fi

  if git worktree list --porcelain | grep -Fxq "branch refs/heads/${branch}"; then
    echo "Skipping local branch '${branch}' (used by a worktree)." >&2
    continue
  fi

  if ! git branch -d "${branch}"; then
    echo "Skipping local branch '${branch}' (could not delete safely)." >&2
  fi
done < <(git for-each-ref --format='%(refname:short)' --merged="${TARGET_BRANCH}" refs/heads)

# Delete remote branches on REMOTE that are fully merged into REMOTE/TARGET_BRANCH.
while IFS= read -r branch; do
  if [ -z "${branch}" ] || [ "${branch}" = "HEAD" ] || [ "${branch}" = "${TARGET_BRANCH}" ]; then
    continue
  fi

  if ! git push "${REMOTE}" --delete "${branch}"; then
    echo "Skipping remote branch '${REMOTE}/${branch}' (could not delete)." >&2
  fi
done < <(
  git for-each-ref --format='%(refname)' --merged="${REMOTE}/${TARGET_BRANCH}" "refs/remotes/${REMOTE}" \
    | sed -n "s#^refs/remotes/${REMOTE}/##p"
)
