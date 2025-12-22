#!/usr/bin/env bash
set -euo pipefail

# Delete local branches that are fully merged into main.
BRANCHES=$(git branch --merged main | sed 's/^\*//' | sed 's/^ //')
for branch in ${BRANCHES}; do
  if [ "${branch}" = "main" ]; then
    continue
  fi
  git branch -d "${branch}"
done

# Prune remote-tracking refs.
git fetch --prune
