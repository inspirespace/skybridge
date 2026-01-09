#!/usr/bin/env bash
set -euo pipefail

if [ "${DEVCONTAINER_E2E_VNC:-0}" = "1" ]; then
  bash ./scripts/stop-e2e-vnc.sh
fi
