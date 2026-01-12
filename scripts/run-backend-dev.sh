#!/usr/bin/env bash
set -euo pipefail

export AUTH_MODE="${AUTH_MODE:-oidc}"
export AUTH_ISSUER_URL="${AUTH_ISSUER_URL:-https://auth.skybridge.localhost/realms/skybridge-dev}"
export AUTH_BROWSER_ISSUER_URL="${AUTH_BROWSER_ISSUER_URL:-https://auth.skybridge.localhost/realms/skybridge-dev}"
export AUTH_JWKS_URL="${AUTH_JWKS_URL:-http://localhost:8080/realms/skybridge-dev/protocol/openid-connect/certs}"
export AUTH_TOKEN_URL="${AUTH_TOKEN_URL:-http://localhost:8080/realms/skybridge-dev/protocol/openid-connect/token}"
export AUTH_CLIENT_ID="${AUTH_CLIENT_ID:-skybridge-dev}"
export AUTH_SCOPE="${AUTH_SCOPE:-openid profile email}"
export BACKEND_SQS_ENABLED="${BACKEND_SQS_ENABLED:-1}"

if [[ -z "${SQS_QUEUE_URL:-}" ]]; then
  echo "SQS_QUEUE_URL is required for lambda-style local dev." >&2
  exit 1
fi

python -m src.backend.lambda_api_local
