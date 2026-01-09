import { afterEach, describe, expect, it, vi } from "vitest";
import { renderHook } from "@testing-library/react";

vi.mock("@/api/client", () => ({
  exchangeToken: vi.fn(),
  refreshToken: vi.fn(),
}));

vi.mock("@/lib/auth-helpers", () => ({
  generateCodeVerifier: vi.fn(() => "verifier"),
  generateCodeChallenge: vi.fn(async () => "challenge"),
  generateState: vi.fn(() => "state"),
  getJwtExpiry: vi.fn(() => Math.floor(Date.now() / 1000) + 5),
  isJwtExpired: vi.fn(() => false),
  parseJwt: vi.fn(() => ({ email: "pilot@example.com" })),
}));

import { useOidcAuth } from "@/hooks/use-oidc-auth";

afterEach(() => {
  vi.resetAllMocks();
  vi.unstubAllGlobals();
  localStorage.clear();
  sessionStorage.clear();
});

describe("useOidcAuth sign out", () => {
  it("redirects to logout when enabled and id token set", () => {
    localStorage.setItem("skybridge_id_token", "id");
    const assign = vi.fn();
    vi.stubGlobal("location", {
      ...window.location,
      assign,
      origin: "https://app.local",
      href: "https://app.local/",
    });

    const { result } = renderHook(() =>
      useOidcAuth({
        enabled: true,
        issuer: "https://issuer.example",
        clientId: "client",
        scope: "openid",
        redirectPath: "/auth/callback",
        providerParam: "kc_idp_hint",
        logoutUrl: "https://issuer.example/logout",
      })
    );

    result.current.signOut();

    expect(assign).toHaveBeenCalled();
    const url = new URL(assign.mock.calls[0][0]);
    expect(url.searchParams.get("client_id")).toBe("client");
  });
});
