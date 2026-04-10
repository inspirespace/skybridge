#!/usr/bin/env bash
set -euo pipefail

trim() {
  local value="$1"
  # shellcheck disable=SC2001
  value="$(printf '%s' "${value}" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
  printf '%s' "${value}"
}

resolve_bind_root_from_devcontainer() {
  if [ ! -f "/.dockerenv" ]; then
    return 1
  fi
  if [ ! -S "/var/run/docker.sock" ]; then
    return 1
  fi
  if ! command -v docker >/dev/null 2>&1; then
    return 1
  fi

  local container_id
  container_id="$(hostname 2>/dev/null || true)"
  if [ -z "${container_id}" ]; then
    return 1
  fi

  local mount_lines
  mount_lines="$(docker inspect --format '{{range .Mounts}}{{println .Destination "|" .Source}}{{end}}' "${container_id}" 2>/dev/null || true)"
  if [ -z "${mount_lines}" ]; then
    return 1
  fi

  local cwd best_dest="" best_src=""
  cwd="$(pwd)"

  local line dest src
  while IFS= read -r line; do
    [ -n "${line}" ] || continue
    dest="$(trim "${line%%|*}")"
    src="$(trim "${line#*|}")"
    [ -n "${dest}" ] || continue
    [ -n "${src}" ] || continue

    case "${cwd}" in
      "${dest}"|"${dest}"/*)
        if [ "${#dest}" -gt "${#best_dest}" ]; then
          best_dest="${dest}"
          best_src="${src}"
        fi
        ;;
    esac
  done <<EOF
${mount_lines}
EOF

  if [ -z "${best_dest}" ] || [ -z "${best_src}" ]; then
    return 1
  fi

  local suffix
  suffix="${cwd#${best_dest}}"
  printf '%s%s\n' "${best_src}" "${suffix}"
}

if [ -z "${WORKSPACE_BIND_ROOT:-}" ] || [ "${WORKSPACE_BIND_ROOT}" = "." ]; then
  if bind_root="$(resolve_bind_root_from_devcontainer)"; then
    export WORKSPACE_BIND_ROOT="${bind_root}"
  else
    export WORKSPACE_BIND_ROOT="${WORKSPACE_BIND_ROOT:-.}"
  fi
fi

# The attached Docker Compose shortcut menu advertises Docker Desktop actions
# that are not reachable from inside the devcontainer. Keep it off there
# unless the caller explicitly opted in/out via COMPOSE_MENU.
if [ -f "/.dockerenv" ] && [ -z "${COMPOSE_MENU+x}" ]; then
  export COMPOSE_MENU=false
fi

exec docker compose "$@"
