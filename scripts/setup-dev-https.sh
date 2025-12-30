#!/usr/bin/env bash
set -euo pipefail

if ! command -v mkcert >/dev/null 2>&1; then
  echo "mkcert is required. Install with: brew install mkcert" >&2
  exit 1
fi

mkdir -p docker/https/certs

mkcert -install
mkcert -cert-file docker/https/certs/skybridge.localhost.pem -key-file docker/https/certs/skybridge.localhost-key.pem skybridge.localhost
mkcert -cert-file docker/https/certs/auth.skybridge.localhost.pem -key-file docker/https/certs/auth.skybridge.localhost-key.pem auth.skybridge.localhost

echo "Certificates written to docker/https/certs."
