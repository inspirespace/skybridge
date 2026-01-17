import * as React from "react";

import { exchangeToken, refreshToken } from "@/api/client";
import {
  generateCodeChallenge,
  generateCodeVerifier,
  generateState,
  getJwtExpiry,
  isJwtExpired,
  parseJwt,
} from "@/lib/auth-helpers";

const CODE_VERIFIER_KEY = "skybridge_code_verifier";
const AUTH_STATE_KEY = "skybridge_auth_state";
const FORCE_LOGIN_KEY = "skybridge_force_login";

/** Hook for oidcauth. */
export function useOidcAuth({
  enabled,
  issuer,
  clientId,
  scope,
  redirectPath,
  providerParam,
  logoutUrl,
  onError,
  onLoadingChange,
}: {
  enabled: boolean;
  issuer: string;
  clientId: string;
  scope: string;
  redirectPath: string;
  providerParam: string;
  logoutUrl: string;
  onError?: (message: string) => void;
  onLoadingChange?: (loading: boolean) => void;
}) {
  const [accessToken, setAccessToken] = React.useState<string | null>(null);
  const [idToken, setIdToken] = React.useState<string | null>(null);
  const [refreshTokenValue, setRefreshTokenValue] = React.useState<string | null>(null);
  const [userId, setUserId] = React.useState<string | null>(null);
  const didExchangeRef = React.useRef(false);
  const refreshInFlight = React.useRef<Promise<void> | null>(null);
  const authEpochRef = React.useRef(0);
  const refreshAbortRef = React.useRef<AbortController | null>(null);

  const clearAuth = React.useCallback(() => {
    authEpochRef.current += 1;
    refreshAbortRef.current?.abort();
    refreshAbortRef.current = null;
    sessionStorage.removeItem(CODE_VERIFIER_KEY);
    sessionStorage.removeItem(AUTH_STATE_KEY);
    sessionStorage.removeItem(FORCE_LOGIN_KEY);
    setUserId(null);
    setAccessToken(null);
    setIdToken(null);
    setRefreshTokenValue(null);
    refreshInFlight.current = null;
  }, []);

  const applyTokenResponse = React.useCallback(
    (token: Awaited<ReturnType<typeof exchangeToken>>) => {
      setAccessToken(token.access_token);
      if (token.refresh_token) {
        setRefreshTokenValue(token.refresh_token);
      }
      if (token.id_token) {
        setIdToken(token.id_token);
        const claims = parseJwt(token.id_token);
        if (claims?.email) {
          setUserId(claims.email);
        }
      }
    },
    []
  );

  const refreshAccessToken = React.useCallback(async () => {
    if (!refreshTokenValue) return;
    if (refreshInFlight.current) return refreshInFlight.current;
    refreshInFlight.current = (async () => {
      const refreshEpoch = authEpochRef.current;
      const abortController = new AbortController();
      refreshAbortRef.current?.abort();
      refreshAbortRef.current = abortController;
      onLoadingChange?.(true);
      try {
        const token = await refreshToken(
          { refresh_token: refreshTokenValue },
          abortController.signal
        );
        if (authEpochRef.current !== refreshEpoch) return;
        applyTokenResponse(token);
      } catch (err) {
        if (err instanceof Error && err.name === "AbortError") {
          return;
        }
        clearAuth();
        onError?.(err instanceof Error ? err.message : "Auth refresh failed");
      } finally {
        onLoadingChange?.(false);
        refreshInFlight.current = null;
        if (refreshAbortRef.current === abortController) {
          refreshAbortRef.current = null;
        }
      }
    })();
    return refreshInFlight.current;
  }, [
    refreshTokenValue,
    applyTokenResponse,
    clearAuth,
    onError,
    onLoadingChange,
  ]);

  React.useEffect(() => {
    if (!enabled) return;
    if (accessToken && isJwtExpired(accessToken)) {
      if (refreshTokenValue) {
        void refreshAccessToken();
      } else {
        clearAuth();
      }
    }
  }, [enabled, accessToken, refreshTokenValue, refreshAccessToken, clearAuth]);

  React.useEffect(() => {
    if (!enabled) return;
    const url = new URL(window.location.href);
    const redirectPathTrimmed = redirectPath.endsWith("/")
      ? redirectPath.slice(0, -1)
      : redirectPath;
    const currentPath = url.pathname.endsWith("/")
      ? url.pathname.slice(0, -1)
      : url.pathname;
    if (!currentPath.endsWith(redirectPathTrimmed)) return;
    const code = url.searchParams.get("code");
    const state = url.searchParams.get("state");
    if (!code || !state) return;
    if (didExchangeRef.current) return;
    const expectedState = sessionStorage.getItem(AUTH_STATE_KEY);
    const verifier = sessionStorage.getItem(CODE_VERIFIER_KEY);
    if (!verifier || !expectedState || expectedState !== state) {
      onError?.("Auth session expired. Please sign in again.");
      return;
    }
    const redirectUri = `${window.location.origin}${redirectPath}`;
    (async () => {
      onLoadingChange?.(true);
      didExchangeRef.current = true;
      try {
        const token = await exchangeToken({
          code,
          code_verifier: verifier,
          redirect_uri: redirectUri,
        });
        applyTokenResponse(token);
        sessionStorage.removeItem(CODE_VERIFIER_KEY);
        sessionStorage.removeItem(AUTH_STATE_KEY);
        const postAuthPath = redirectPath.replace(/\/auth\/callback\/?$/, "/") || "/";
        window.history.replaceState({}, document.title, postAuthPath);
      } catch (err) {
        onError?.(err instanceof Error ? err.message : "Auth failed");
      } finally {
        onLoadingChange?.(false);
      }
    })();
  }, [
    enabled,
    issuer,
    redirectPath,
    clientId,
    scope,
    onError,
    onLoadingChange,
    applyTokenResponse,
  ]);

  React.useEffect(() => {
    if (!enabled || !accessToken || !refreshTokenValue) return;
    const exp = getJwtExpiry(accessToken);
    if (!exp) return;
    const now = Math.floor(Date.now() / 1000);
    const refreshAt = exp - 90;
    const delayMs = Math.max((refreshAt - now) * 1000, 0);
    const timeout = window.setTimeout(() => {
      void refreshAccessToken();
    }, delayMs);
    return () => window.clearTimeout(timeout);
  }, [enabled, accessToken, refreshTokenValue, refreshAccessToken]);

  const startLogin = React.useCallback(
    async (provider?: string) => {
      if (!enabled) return;
      if (!issuer) {
        onError?.("Auth issuer is not configured.");
        return;
      }
      const currentUrl = new URL(window.location.href);
      const forceLogin =
        currentUrl.searchParams.get("force") === "1" ||
        sessionStorage.getItem(FORCE_LOGIN_KEY) === "1";
      const redirectUri = `${window.location.origin}${redirectPath}`;
      const verifier = generateCodeVerifier();
      sessionStorage.setItem(CODE_VERIFIER_KEY, verifier);
      const challenge = await generateCodeChallenge(verifier);
      const state = generateState();
      sessionStorage.setItem(AUTH_STATE_KEY, state);
      const issuerBase = issuer.endsWith("/") ? issuer.slice(0, -1) : issuer;
      const authUrl = new URL(`${issuerBase}/protocol/openid-connect/auth`);
      authUrl.searchParams.set("client_id", clientId);
      authUrl.searchParams.set("response_type", "code");
      authUrl.searchParams.set("scope", scope);
      authUrl.searchParams.set("redirect_uri", redirectUri);
      authUrl.searchParams.set("code_challenge", challenge);
      authUrl.searchParams.set("code_challenge_method", "S256");
      authUrl.searchParams.set("state", state);
      if (forceLogin) {
        authUrl.searchParams.set("prompt", "login");
        authUrl.searchParams.set("max_age", "0");
        sessionStorage.removeItem(FORCE_LOGIN_KEY);
      }
      if (provider) {
        authUrl.searchParams.set(providerParam, provider);
      }
      window.location.assign(authUrl.toString());
    },
    [enabled, issuer, clientId, scope, redirectPath, providerParam, onError]
  );

  const signOut = React.useCallback(() => {
    const currentIdToken = idToken ?? undefined;
    clearAuth();
    if (enabled) {
      sessionStorage.setItem(FORCE_LOGIN_KEY, "1");
    }
    if (enabled && logoutUrl && currentIdToken) {
      const url = new URL(logoutUrl);
      url.searchParams.set("client_id", clientId);
      url.searchParams.set("id_token_hint", currentIdToken);
      url.searchParams.set("post_logout_redirect_uri", `${window.location.origin}/`);
      window.location.assign(url.toString());
      return;
    }
    if (enabled) {
      window.location.replace("/");
    }
  }, [enabled, logoutUrl, clientId, redirectPath, idToken, clearAuth]);

  return {
    accessToken,
    idToken,
    userId,
    setUserId,
    setAccessToken,
    setIdToken,
    setRefreshToken: setRefreshTokenValue,
    startLogin,
    signOut,
    clearAuth,
  };
}
