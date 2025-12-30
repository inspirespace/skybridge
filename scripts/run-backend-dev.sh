#!/usr/bin/env bash
set -euo pipefail

export AUTH_MODE="${AUTH_MODE:-oidc}"
export AUTH_ISSUER_URL="${AUTH_ISSUER_URL:-https://auth.skybridge.localhost/realms/skybridge-dev}"
export AUTH_BROWSER_ISSUER_URL="${AUTH_BROWSER_ISSUER_URL:-https://auth.skybridge.localhost/realms/skybridge-dev}"
export AUTH_JWKS_URL="${AUTH_JWKS_URL:-http://localhost:8080/realms/skybridge-dev/protocol/openid-connect/certs}"
export AUTH_TOKEN_URL="${AUTH_TOKEN_URL:-http://localhost:8080/realms/skybridge-dev/protocol/openid-connect/token}"
export AUTH_TOKEN_PROXY="${AUTH_TOKEN_PROXY:-true}"
export AUTH_CLIENT_ID="${AUTH_CLIENT_ID:-skybridge-dev}"
export AUTH_SCOPE="${AUTH_SCOPE:-openid profile email}"

python -m uvicorn src.backend.app:app --host 0.0.0.0 --port 8000
