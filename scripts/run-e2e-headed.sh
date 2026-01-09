#!/usr/bin/env bash
set -euo pipefail

# Headed Playwright on macOS + devcontainer via XQuartz (software rendering).
# Force DISPLAY to the host XQuartz server when the container has a local display.
if [ -z "${DISPLAY:-}" ] || [[ "${DISPLAY}" == :* ]]; then
  export DISPLAY="host.docker.internal:0"
fi

export LIBGL_ALWAYS_SOFTWARE=1
export LIBGL_DRI3_DISABLE=1
export QT_X11_NO_MITSHM=1
export _X11_NO_MITSHM=1

npm --prefix src/frontend run test:e2e -- --headed
