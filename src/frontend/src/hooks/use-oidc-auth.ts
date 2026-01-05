import * as React from "react";

import { exchangeToken } from "@/api/client";
import {
  generateCodeChallenge,
  generateCodeVerifier,
  generateState,
  isJwtExpired,
  parseJwt,
} from "@/lib/auth-helpers";

const TOKEN_KEY = "skybridge_access_token";
const ID_TOKEN_KEY = "skybridge_id_token";
const CODE_VERIFIER_KEY = "skybridge_code_verifier";
const AUTH_STATE_KEY = "skybridge_auth_state";
const USER_ID_KEY = "skybridge_user_id";

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
  const [accessToken, setAccessToken] = React.useState<string | null>(() =>
    localStorage.getItem(TOKEN_KEY)
  );
  const [idToken, setIdToken] = React.useState<string | null>(() =>
    localStorage.getItem(ID_TOKEN_KEY)
  );
  const [userId, setUserId] = React.useState<string | null>(() =>
    localStorage.getItem(USER_ID_KEY)
  );
  const didExchangeRef = React.useRef(false);

  const clearAuth = React.useCallback(() => {
    localStorage.removeItem(USER_ID_KEY);
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(ID_TOKEN_KEY);
    sessionStorage.removeItem(CODE_VERIFIER_KEY);
    sessionStorage.removeItem(AUTH_STATE_KEY);
    setUserId(null);
    setAccessToken(null);
    setIdToken(null);
  }, []);

  React.useEffect(() => {
    if (!enabled) return;
    if (accessToken && isJwtExpired(accessToken)) {
      clearAuth();
    }
  }, [enabled, accessToken, clearAuth]);

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
        localStorage.setItem(TOKEN_KEY, token.access_token);
        setAccessToken(token.access_token);
        if (token.id_token) {
          localStorage.setItem(ID_TOKEN_KEY, token.id_token);
          setIdToken(token.id_token);
          const claims = parseJwt(token.id_token);
          if (claims?.email) {
            localStorage.setItem(USER_ID_KEY, claims.email);
            setUserId(claims.email);
          }
        }
        sessionStorage.removeItem(CODE_VERIFIER_KEY);
        sessionStorage.removeItem(AUTH_STATE_KEY);
        window.history.replaceState({}, document.title, "/");
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
  ]);

  const startLogin = React.useCallback(
    async (provider?: string) => {
      if (!enabled) return;
      if (!issuer) {
        onError?.("Auth issuer is not configured.");
        return;
      }
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
      if (provider) {
        authUrl.searchParams.set(providerParam, provider);
      }
      window.location.assign(authUrl.toString());
    },
    [enabled, issuer, clientId, scope, redirectPath, providerParam, onError]
  );

  const signOut = React.useCallback(() => {
    const currentIdToken = idToken;
    clearAuth();
    if (enabled && logoutUrl && currentIdToken) {
      const url = new URL(logoutUrl);
      url.searchParams.set("client_id", clientId);
      url.searchParams.set("id_token_hint", currentIdToken);
      url.searchParams.set(
        "post_logout_redirect_uri",
        window.location.origin + redirectPath
      );
      window.location.assign(url.toString());
    }
  }, [enabled, logoutUrl, clientId, redirectPath, idToken, clearAuth]);

  return {
    accessToken,
    idToken,
    userId,
    setUserId,
    setAccessToken,
    setIdToken,
    startLogin,
    signOut,
    clearAuth,
  };
}
