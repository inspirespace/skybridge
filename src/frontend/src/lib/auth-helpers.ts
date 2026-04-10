/** Handle generateCodeVerifier. */
export function generateCodeVerifier() {
  const array = new Uint8Array(32);
  crypto.getRandomValues(array);
  return base64UrlEncode(array);
}

export async function generateCodeChallenge(verifier: string) {
  const data = new TextEncoder().encode(verifier);
  const digest = await crypto.subtle.digest("SHA-256", data);
  return base64UrlEncode(new Uint8Array(digest));
}

/** Handle generateState. */
export function generateState() {
  const array = new Uint8Array(16);
  crypto.getRandomValues(array);
  return base64UrlEncode(array);
}

/** Handle base64UrlEncode. */
function base64UrlEncode(bytes: Uint8Array) {
  return btoa(String.fromCharCode(...bytes))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

/** Handle parseJwt. */
export function parseJwt(token: string) {
  const [, payload] = token.split(".");
  if (!payload) return {};
  const json = atob(payload.replace(/-/g, "+").replace(/_/g, "/"));
  return JSON.parse(json);
}

/** Handle getJwtExpiry. */
export function getJwtExpiry(token: string) {
  try {
    const payload = parseJwt(token);
    return typeof payload?.exp === "number" ? payload.exp : null;
  } catch {
    return null;
  }
}

/** Handle isJwtExpired. */
export function isJwtExpired(token: string, skewSeconds = 60) {
  try {
    const exp = getJwtExpiry(token);
    if (!exp) return false;
    const now = Math.floor(Date.now() / 1000);
    return exp < now - skewSeconds;
  } catch {
    return false;
  }
}

/** Handle isAuthExpiredError. */
export function isAuthExpiredError(error: unknown) {
  if (!error || typeof error !== "object") return false;
  const status = (error as Error & { status?: number }).status;
  const message = ((error as Error).message || "").trim();
  if (!message) return false;

  // App Check or provider readiness failures are auth/config issues, not token-expiry.
  if (/app check|provider not ready|auth is not configured/i.test(message)) {
    return false;
  }

  if (
    /expired|invalid token|token audience mismatch|unknown token key id|token missing key id|missing authorization bearer token|invalid token subject/i.test(
      message
    )
  ) {
    return true;
  }

  // Keep handling explicit unauthorized responses from API gateways/proxies.
  if ((status === 401 || status === 403) && /unauthorized|not authorized/i.test(message)) {
    return true;
  }

  return false;
}
