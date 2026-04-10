#!/usr/bin/env bash
set -euo pipefail

SOCKET_PATH="${DOCKER_SOCKET_PATH:-/var/run/docker.sock}"
CURRENT_USER="$(id -un)"
RESTART_VSCODE_SERVER=0

usage() {
  cat <<'EOF'
Usage: ./scripts/repair-docker-socket-access.sh [--restart-vscode-server]

Repairs Docker socket permissions inside the devcontainer for the current user.

Options:
  --restart-vscode-server  Restart remote VS Code server processes after updating
                           memberships (helps extension hosts pick up new groups).
  -h, --help               Show this help message.
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --restart-vscode-server)
      RESTART_VSCODE_SERVER=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [ ! -S "${SOCKET_PATH}" ]; then
  echo "Docker socket not found at ${SOCKET_PATH}; nothing to repair."
  exit 0
fi

SOCKET_GID="$(stat -c '%g' "${SOCKET_PATH}" 2>/dev/null || true)"
if [ -z "${SOCKET_GID}" ]; then
  echo "Warning: unable to read group id for ${SOCKET_PATH}."
  exit 0
fi

resolve_group_name() {
  getent group "${SOCKET_GID}" | cut -d: -f1 || true
}

run_as_root() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
    return
  fi
  if command -v sudo >/dev/null 2>&1; then
    sudo "$@"
    return
  fi
  return 1
}

has_socket_access_now() {
  [ -r "${SOCKET_PATH}" ] && [ -w "${SOCKET_PATH}" ]
}

configured_user_groups() {
  id -nG "${CURRENT_USER}" 2>/dev/null || true
}

process_user_groups() {
  id -nG 2>/dev/null || true
}

grant_socket_acl() {
  if ! command -v setfacl >/dev/null 2>&1; then
    return 1
  fi
  run_as_root setfacl -m "u:${CURRENT_USER}:rw" "${SOCKET_PATH}" >/dev/null 2>&1
}

SOCKET_GROUP="$(resolve_group_name)"
if [ -z "${SOCKET_GROUP}" ]; then
  SOCKET_GROUP="docker-host-${SOCKET_GID}"
  if ! getent group "${SOCKET_GROUP}" >/dev/null 2>&1; then
    if ! run_as_root groupadd -g "${SOCKET_GID}" "${SOCKET_GROUP}" >/dev/null 2>&1; then
      echo "Warning: unable to create docker socket group ${SOCKET_GROUP}."
      exit 0
    fi
  fi
  SOCKET_GROUP="$(resolve_group_name)"
fi

if [ -z "${SOCKET_GROUP}" ]; then
  echo "Warning: unable to resolve docker socket group for gid ${SOCKET_GID}."
  exit 0
fi

if has_socket_access_now; then
  echo "Docker socket access already active for ${CURRENT_USER}."
  exit 0
fi

if ! configured_user_groups | tr ' ' '\n' | grep -qx "${SOCKET_GROUP}"; then
  if ! run_as_root usermod -aG "${SOCKET_GROUP}" "${CURRENT_USER}" >/dev/null 2>&1; then
    echo "Warning: unable to add ${CURRENT_USER} to ${SOCKET_GROUP}."
    exit 0
  fi
fi

if has_socket_access_now; then
  echo "Docker socket access active for ${CURRENT_USER} via ${SOCKET_GROUP}."
  exit 0
fi

if grant_socket_acl; then
  if has_socket_access_now; then
    echo "Docker socket ACL applied for ${CURRENT_USER}."
    exit 0
  fi
  echo "Applied Docker socket ACL, but current shell still has no access."
else
  echo "Warning: could not apply socket ACL (setfacl unavailable or denied)."
fi

if [ "${RESTART_VSCODE_SERVER}" -eq 1 ]; then
  echo "Restarting remote VS Code server processes so new group membership takes effect..."
  pkill -u "${CURRENT_USER}" -f ".vscode-server" >/dev/null 2>&1 || true
  echo "VS Code server restart requested. Re-open the window if not reconnected automatically."
  exit 0
fi

if process_user_groups | tr ' ' '\n' | grep -qx "${SOCKET_GROUP}"; then
  echo "Docker socket group is present in current process groups but access is still denied."
  echo "Check host Docker Desktop status and socket mode: ls -ln ${SOCKET_PATH}"
else
  echo "Docker socket group updated to ${SOCKET_GROUP}, but current process groups are stale."
  echo "Run this again with --restart-vscode-server or rebuild/reopen the devcontainer."
fi
