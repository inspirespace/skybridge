import { afterEach, describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";

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

const AUTH_STATE_KEY = "skybridge_auth_state";
const CODE_VERIFIER_KEY = "skybridge_code_verifier";

afterEach(() => {
  vi.resetAllMocks();
  vi.unstubAllGlobals();
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

    await waitFor(() => {
      expect(exchangeToken).toHaveBeenCalled();
    });

    await waitFor(() => {
      expect(result.current.accessToken).toBe("access");
      expect(result.current.idToken).toBe("id");
      expect(result.current.userId).toBe("pilot@example.com");
    });
  });

  it("refreshes access token when expired", async () => {
    (isJwtExpired as unknown as ReturnType<typeof vi.fn>).mockReturnValue(true);
    (refreshToken as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      access_token: "new-access",
      refresh_token: "refresh",
      id_token: "id",
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

    act(() => {
      result.current.setAccessToken("expired");
      result.current.setRefreshToken("refresh");
    });

    await waitFor(() => {
      expect(refreshToken).toHaveBeenCalled();
    });

    await waitFor(() => {
      expect(result.current.accessToken).toBe("new-access");
    });
  });
});
