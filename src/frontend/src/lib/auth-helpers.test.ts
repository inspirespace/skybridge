import { describe, expect, it, vi } from "vitest";
import {
  generateCodeVerifier,
  generateState,
  getJwtExpiry,
  isAuthExpiredError,
  isJwtExpired,
  parseJwt,
} from "@/lib/auth-helpers";

function base64UrlEncode(value: string) {
  return btoa(value).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function buildToken(payload: object) {
  const header = base64UrlEncode(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const body = base64UrlEncode(JSON.stringify(payload));
  return `${header}.${body}.sig`;
}

describe("auth-helpers", () => {
  it("parses jwt payload", () => {
    const token = buildToken({ email: "pilot@example.com" });
    expect(parseJwt(token)).toMatchObject({ email: "pilot@example.com" });
  });

  it("extracts expiry and checks skew", () => {
    const now = Math.floor(Date.now() / 1000);
    const token = buildToken({ exp: now + 30 });
    expect(getJwtExpiry(token)).toBe(now + 30);
    expect(isJwtExpired(token, 60)).toBe(false);
    expect(isJwtExpired(token, 0)).toBe(false);
  });

  it("detects auth expired errors", () => {
    const statusError = new Error("unauthorized") as Error & { status?: number };
    statusError.status = 401;
    expect(isAuthExpiredError(statusError)).toBe(true);
    expect(isAuthExpiredError(new Error("token expired"))).toBe(true);
    expect(isAuthExpiredError(new Error("other"))).toBe(false);
  });

  it("generates verifier and state", () => {
    vi.stubGlobal("crypto", {
      getRandomValues: (arr: Uint8Array) => {
        arr.fill(1);
        return arr;
      },
    });

    const verifier = generateCodeVerifier();
    const state = generateState();

    expect(verifier.length).toBeGreaterThan(10);
    expect(state.length).toBeGreaterThan(10);
    expect(verifier).not.toMatch(/=/);
    expect(state).not.toMatch(/=/);
  });
});
