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

/** Handle isJwtExpired. */
export function isJwtExpired(token: string, skewSeconds = 60) {
  try {
    const payload = parseJwt(token);
    const exp = typeof payload?.exp === "number" ? payload.exp : null;
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
  if (status === 401 || status === 403) return true;
  const message = (error as Error).message || "";
  return /expired|invalid token/i.test(message);
}
