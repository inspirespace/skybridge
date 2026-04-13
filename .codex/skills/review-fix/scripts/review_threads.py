#!/usr/bin/env python3
"""
Discover, inspect, reply to, and resolve GitHub PR review threads.

Commands:
  discover
    Show the current branch PR and open PRs in the current repository that are
    assigned or review-requested to the authenticated GitHub user.

  fetch
    Fetch review-thread metadata for a specific PR, including review comment
    database IDs suitable for replies.

  reply
    Reply to a review thread by creating a pull-request review comment reply.

  resolve
    Resolve a review thread via GraphQL.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


VIEWER_QUERY = """\
query {
  viewer {
    login
  }
}
"""


DISCOVER_QUERY = """\
query($owner: String!, $repo: String!, $cursor: String) {
  viewer {
    login
  }
  repository(owner: $owner, name: $repo) {
    pullRequests(
      first: 50,
      states: OPEN,
      orderBy: {field: UPDATED_AT, direction: DESC},
      after: $cursor
    ) {
      pageInfo {
        hasNextPage
        endCursor
      }
      nodes {
        number
        url
        title
        updatedAt
        reviewDecision
        assignees(first: 20) {
          nodes {
            login
          }
        }
        reviewRequests(first: 20) {
          nodes {
            requestedReviewer {
              __typename
              ... on User {
                login
              }
              ... on Team {
                organization {
                  login
                }
                slug
              }
            }
          }
        }
      }
    }
  }
}
"""


FETCH_QUERY = """\
query($owner: String!, $repo: String!, $number: Int!, $threadsCursor: String) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      number
      url
      title
      state
      reviewDecision
      reviewThreads(first: 100, after: $threadsCursor) {
        pageInfo {
          hasNextPage
          endCursor
        }
        nodes {
          id
          isResolved
          isOutdated
          path
          line
          startLine
          originalLine
          originalStartLine
          diffSide
          startDiffSide
          comments(first: 100) {
            nodes {
              id
              databaseId
              url
              body
              createdAt
              updatedAt
              author {
                login
              }
            }
          }
        }
      }
    }
  }
}
"""


RESOLVE_MUTATION = """\
mutation($threadId: ID!) {
  resolveReviewThread(input: {threadId: $threadId}) {
    thread {
      id
      isResolved
    }
  }
}
"""


def _run(cmd: list[str], stdin: str | None = None) -> str:
    result = subprocess.run(cmd, input=stdin, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {' '.join(cmd)}\n{result.stderr.strip()}"
        )
    return result.stdout


def _run_json(cmd: list[str], stdin: str | None = None) -> dict[str, Any]:
    output = _run(cmd, stdin=stdin)
    try:
        return json.loads(output)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse JSON output from {' '.join(cmd)}") from exc


def _ensure_gh_authenticated() -> None:
    try:
        _run(["gh", "auth", "status"])
    except RuntimeError as exc:
        raise RuntimeError("gh auth failed; run `gh auth login` first") from exc


def _graphql(fields: list[str], query: str) -> dict[str, Any]:
    cmd = ["gh", "api", "graphql", "-F", "query=@-"]
    for field in fields:
        cmd.extend(["-F", field])
    payload = _run_json(cmd, stdin=query)
    if payload.get("errors"):
        raise RuntimeError(json.dumps(payload["errors"], indent=2))
    return payload["data"]


def _repo_parts(repo: str | None) -> tuple[str, str]:
    if repo:
        owner, name = repo.split("/", 1)
        return owner, name

    data = _run_json(["gh", "repo", "view", "--json", "nameWithOwner"])
    owner, name = data["nameWithOwner"].split("/", 1)
    return owner, name


def _current_pr() -> dict[str, Any] | None:
    try:
        return _run_json(["gh", "pr", "view", "--json", "number,url,title,state"])
    except RuntimeError:
        return None


def _viewer_login() -> str:
    data = _graphql([], VIEWER_QUERY)
    return data["viewer"]["login"]


def _discover(repo: str | None) -> dict[str, Any]:
    owner, name = _repo_parts(repo)
    viewer = _viewer_login()

    candidates: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        fields = [f"owner={owner}", f"repo={name}"]
        if cursor:
            fields.append(f"cursor={cursor}")
        data = _graphql(fields, DISCOVER_QUERY)
        pull_requests = data["repository"]["pullRequests"]
        for pr in pull_requests["nodes"]:
            assignees = [node["login"] for node in pr["assignees"]["nodes"]]
            requested_reviewers = []
            for request in pr["reviewRequests"]["nodes"]:
                reviewer = request["requestedReviewer"]
                if reviewer["__typename"] == "User":
                    requested_reviewers.append(reviewer["login"])
                elif reviewer["__typename"] == "Team":
                    requested_reviewers.append(
                        f'{reviewer["organization"]["login"]}/{reviewer["slug"]}'
                    )

            if viewer in assignees or viewer in requested_reviewers:
                candidates.append(
                    {
                        "number": pr["number"],
                        "url": pr["url"],
                        "title": pr["title"],
                        "updated_at": pr["updatedAt"],
                        "review_decision": pr["reviewDecision"],
                        "assignees": assignees,
                        "requested_reviewers": requested_reviewers,
                    }
                )

        if not pull_requests["pageInfo"]["hasNextPage"]:
            break
        cursor = pull_requests["pageInfo"]["endCursor"]

    return {
        "viewer": viewer,
        "repository": f"{owner}/{name}",
        "current_branch_pull_request": _current_pr(),
        "assigned_pull_requests": candidates,
    }


def _fetch(repo: str | None, pr_number: int | None) -> dict[str, Any]:
    owner, name = _repo_parts(repo)
    if pr_number is None:
        current = _current_pr()
        if current is None:
            raise RuntimeError("No PR specified and current branch is not associated with a PR")
        pr_number = int(current["number"])

    threads: list[dict[str, Any]] = []
    cursor: str | None = None
    pr_meta: dict[str, Any] | None = None
    while True:
        fields = [f"owner={owner}", f"repo={name}", f"number={pr_number}"]
        if cursor:
            fields.append(f"threadsCursor={cursor}")
        data = _graphql(fields, FETCH_QUERY)
        pr = data["repository"]["pullRequest"]
        if pr_meta is None:
            pr_meta = {
                "number": pr["number"],
                "url": pr["url"],
                "title": pr["title"],
                "state": pr["state"],
                "review_decision": pr["reviewDecision"],
                "repository": f"{owner}/{name}",
            }

        review_threads = pr["reviewThreads"]
        for thread in review_threads["nodes"]:
            comments = thread["comments"]["nodes"]
            threads.append(
                {
                    "id": thread["id"],
                    "is_resolved": thread["isResolved"],
                    "is_outdated": thread["isOutdated"],
                    "path": thread["path"],
                    "line": thread["line"],
                    "start_line": thread["startLine"],
                    "original_line": thread["originalLine"],
                    "original_start_line": thread["originalStartLine"],
                    "diff_side": thread["diffSide"],
                    "start_diff_side": thread["startDiffSide"],
                    "root_comment_database_id": comments[0]["databaseId"] if comments else None,
                    "latest_comment_database_id": comments[-1]["databaseId"] if comments else None,
                    "comments": comments,
                }
            )

        if not review_threads["pageInfo"]["hasNextPage"]:
            break
        cursor = review_threads["pageInfo"]["endCursor"]

    return {
        "pull_request": pr_meta,
        "review_threads": threads,
    }


def _reply(repo: str, pr_number: int, comment_id: int, body: str) -> dict[str, Any]:
    owner, name = _repo_parts(repo)
    return _run_json(
        [
            "gh",
            "api",
            "--method",
            "POST",
            f"repos/{owner}/{name}/pulls/{pr_number}/comments",
            "-f",
            f"body={body}",
            "-F",
            f"in_reply_to={comment_id}",
        ]
    )


def _resolve(thread_id: str) -> dict[str, Any]:
    data = _graphql([f"threadId={thread_id}"], RESOLVE_MUTATION)
    return data["resolveReviewThread"]["thread"]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    discover_parser = subparsers.add_parser("discover", help="Discover relevant PRs")
    discover_parser.add_argument("--repo", help="Repository in owner/name form")

    fetch_parser = subparsers.add_parser("fetch", help="Fetch review threads for a PR")
    fetch_parser.add_argument("--repo", help="Repository in owner/name form")
    fetch_parser.add_argument("--pr", type=int, help="Pull request number")

    reply_parser = subparsers.add_parser("reply", help="Reply to a review comment")
    reply_parser.add_argument("--repo", required=True, help="Repository in owner/name form")
    reply_parser.add_argument("--pr", required=True, type=int, help="Pull request number")
    reply_parser.add_argument("--comment-id", required=True, type=int, help="Root review comment database ID")
    body_group = reply_parser.add_mutually_exclusive_group(required=True)
    body_group.add_argument("--body", help="Reply body text")
    body_group.add_argument("--body-file", type=Path, help="Path to a file containing the reply body")

    resolve_parser = subparsers.add_parser("resolve", help="Resolve a review thread")
    resolve_parser.add_argument("--thread-id", required=True, help="GraphQL review thread ID")

    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    _ensure_gh_authenticated()

    if args.command == "discover":
        result = _discover(args.repo)
    elif args.command == "fetch":
        result = _fetch(args.repo, args.pr)
    elif args.command == "reply":
        body = args.body if args.body is not None else args.body_file.read_text(encoding="utf-8")
        result = _reply(args.repo, args.pr, args.comment_id, body)
    else:
        result = _resolve(args.thread_id)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
