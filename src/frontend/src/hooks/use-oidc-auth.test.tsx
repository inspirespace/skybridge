import { afterEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";

vi.mock("@/api/client", () => ({
  exchangeToken: vi.fn(),
  refreshToken: vi.fn(),
}));

vi.mock("@/lib/auth-helpers", () => ({
  generateCodeVerifier: vi.fn(() => "verifier"),
  generateCodeChallenge: vi.fn(async () => "challenge"),
  generateState: vi.fn(() => "state"),
  getJwtExpiry: vi.fn(() => null),
  isJwtExpired: vi.fn(() => false),
  parseJwt: vi.fn(() => ({ email: "pilot@example.com" })),
}));

import { exchangeToken, refreshToken } from "@/api/client";
import { isJwtExpired } from "@/lib/auth-helpers";
import { useOidcAuth } from "@/hooks/use-oidc-auth";

const TOKEN_KEY = "skybridge_access_token";
const ID_TOKEN_KEY = "skybridge_id_token";
const REFRESH_TOKEN_KEY = "skybridge_refresh_token";
const AUTH_STATE_KEY = "skybridge_auth_state";
const CODE_VERIFIER_KEY = "skybridge_code_verifier";

afterEach(() => {
  vi.resetAllMocks();
  vi.unstubAllGlobals();
  localStorage.clear();
  sessionStorage.clear();
});

describe("useOidcAuth", () => {
  it("reports error when issuer is missing", async () => {
    const onError = vi.fn();
    const { result } = renderHook(() =>
      useOidcAuth({
        enabled: true,
        issuer: "",
        clientId: "client",
        scope: "openid",
        redirectPath: "/app/auth/callback",
        providerParam: "kc_idp_hint",
        logoutUrl: "",
        onError,
      })
    );

    await result.current.startLogin();
    expect(onError).toHaveBeenCalled();
  });

  it("builds authorize URL and redirects", async () => {
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
        redirectPath: "/app/auth/callback",
        providerParam: "kc_idp_hint",
        logoutUrl: "",
      })
    );

    await result.current.startLogin("google");

    expect(sessionStorage.getItem(CODE_VERIFIER_KEY)).toBe("verifier");
    expect(sessionStorage.getItem(AUTH_STATE_KEY)).toBe("state");
    expect(assign).toHaveBeenCalled();
    const url = new URL(assign.mock.calls[0][0]);
    expect(url.searchParams.get("code_challenge")).toBe("challenge");
    expect(url.searchParams.get("kc_idp_hint")).toBe("google");
  });

  it("exchanges code for token on callback", async () => {
    (exchangeToken as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      access_token: "access",
      refresh_token: "refresh",
      id_token: "id",
    });

    sessionStorage.setItem(AUTH_STATE_KEY, "state");
    sessionStorage.setItem(CODE_VERIFIER_KEY, "verifier");
    window.history.replaceState({}, "", "/app/auth/callback?code=abc&state=state");

    renderHook(() =>
      useOidcAuth({
        enabled: true,
        issuer: "https://issuer.example",
        clientId: "client",
        scope: "openid",
        redirectPath: "/app/auth/callback",
        providerParam: "kc_idp_hint",
        logoutUrl: "",
      })
    );

    await waitFor(() => {
      expect(exchangeToken).toHaveBeenCalled();
    });

    expect(localStorage.getItem(TOKEN_KEY)).toBe("access");
    expect(localStorage.getItem(REFRESH_TOKEN_KEY)).toBe("refresh");
    expect(localStorage.getItem(ID_TOKEN_KEY)).toBe("id");
  });

  it("refreshes access token when expired", async () => {
    localStorage.setItem(TOKEN_KEY, "expired");
    localStorage.setItem(REFRESH_TOKEN_KEY, "refresh");
    (isJwtExpired as unknown as ReturnType<typeof vi.fn>).mockReturnValue(true);
    (refreshToken as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      access_token: "new-access",
      refresh_token: "refresh",
      id_token: "id",
    });

    renderHook(() =>
      useOidcAuth({
        enabled: true,
        issuer: "https://issuer.example",
        clientId: "client",
        scope: "openid",
        redirectPath: "/app/auth/callback",
        providerParam: "kc_idp_hint",
        logoutUrl: "",
      })
    );

    await waitFor(() => {
      expect(refreshToken).toHaveBeenCalled();
    });

    expect(localStorage.getItem(TOKEN_KEY)).toBe("new-access");
  });
});
