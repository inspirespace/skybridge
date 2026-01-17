import * as React from "react";

import { parseJwt } from "@/lib/auth-helpers";

const TOKEN_KEY = "skybridge_access_token";
const ID_TOKEN_KEY = "skybridge_id_token";
const USER_ID_KEY = "skybridge_user_id";
const EMAIL_LINK_KEY = "skybridge_email_link";
const EMULATOR_PROVIDER_KEY = "skybridge_emulator_provider";
const EMULATOR_RETRY_ATTEMPTS = 3;
const EMULATOR_RETRY_DELAY_MS = 600;

type ProviderName = "google" | "apple" | "facebook" | "microsoft" | "anonymous";

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

const formatEmulatorError = (message: string) => {
  if (message.toLowerCase().includes("network-request-failed")) {
    return "Auth emulator is still starting. Please try again in a moment.";
  }
  return message;
};

const retryEmulatorAuth = async (fn: () => Promise<void>) => {
  let lastError: unknown;
  for (let attempt = 0; attempt < EMULATOR_RETRY_ATTEMPTS; attempt += 1) {
    try {
      await fn();
      return;
    } catch (err) {
      lastError = err;
      await delay(EMULATOR_RETRY_DELAY_MS * (attempt + 1));
    }
  }
  if (lastError instanceof Error) {
    throw lastError;
  }
  throw new Error("Auth emulator unavailable.");
};

export function useFirebaseAuth({
  enabled,
  apiKey,
  authDomain,
  projectId,
  appId,
  emulatorHost,
  useEmulator,
  onError,
  onLoadingChange,
}: {
  enabled: boolean;
  apiKey: string;
  authDomain: string;
  projectId: string;
  appId?: string;
  emulatorHost?: string;
  useEmulator?: boolean;
  onError?: (message: string) => void;
  onLoadingChange?: (loading: boolean) => void;
}) {
  const [accessToken, setAccessToken] = React.useState<string | null>(() =>
    localStorage.getItem(TOKEN_KEY)
  );
  const [idToken, setIdToken] = React.useState<string | null>(() =>
    localStorage.getItem(ID_TOKEN_KEY)
  );
  const [isAnonymous, setIsAnonymous] = React.useState(false);
  const [emulatorProvider, setEmulatorProvider] = React.useState<ProviderName | null>(() => {
    const stored = localStorage.getItem(EMULATOR_PROVIDER_KEY);
    return (stored as ProviderName) ?? null;
  });
  const [emulatorReady, setEmulatorReady] = React.useState(!useEmulator);
  const authRef = React.useRef<ReturnType<typeof import("firebase/auth").getAuth> | null>(null);
  const emulatorUrl = React.useMemo(() => {
    if (!useEmulator) return undefined;
    let fallback = "http://localhost:9099";
    if (typeof window !== "undefined") {
      const isHttps = window.location.protocol === "https:";
      const hostname = window.location.hostname;
      if (isHttps && hostname.endsWith("skybridge.localhost")) {
        fallback = window.location.origin;
      }
      if (window.location.protocol === "http:") {
        fallback = "http://localhost:9099";
      }
    }
    if (!emulatorHost) return fallback;
    if (
      typeof window !== "undefined" &&
      window.location.protocol === "http:" &&
      emulatorHost.startsWith("https://")
    ) {
      return "http://localhost:9099";
    }
    return emulatorHost;
  }, [useEmulator, emulatorHost]);

  const checkEmulatorReady = React.useCallback(async () => {
    if (!useEmulator || !emulatorUrl) return true;
    const base = emulatorUrl.startsWith("http") ? emulatorUrl : `http://${emulatorUrl}`;
    const endpoint = `${base}/identitytoolkit.googleapis.com/v1/projects?key=${encodeURIComponent(
      apiKey
    )}`;
    const response = await fetch(endpoint, { method: "GET", mode: "cors" });
    return Boolean(response);
  }, [useEmulator, emulatorUrl, apiKey]);

  React.useEffect(() => {
    if (!useEmulator) {
      setEmulatorReady(true);
      return;
    }
    let cancelled = false;
    setEmulatorReady(false);
    (async () => {
      for (let attempt = 0; attempt < EMULATOR_RETRY_ATTEMPTS * 3; attempt += 1) {
        try {
          await checkEmulatorReady();
          if (!cancelled) setEmulatorReady(true);
          return;
        } catch (err) {
          if (cancelled) return;
          await delay(EMULATOR_RETRY_DELAY_MS * (attempt + 1));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [useEmulator, checkEmulatorReady]);

  const buildEmulatorEmailLink = React.useCallback(
    async (email: string, redirectUrl: string) => {
      if (!emulatorUrl) return null;
      const base =
        emulatorUrl.startsWith("http") ? emulatorUrl : `http://${emulatorUrl}`;
      const endpoint = `${base}/identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key=${encodeURIComponent(
        apiKey
      )}`;
      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          requestType: "EMAIL_SIGNIN",
          email,
          continueUrl: redirectUrl,
          canHandleCodeInApp: true,
        }),
      });
      if (!response.ok) {
        throw new Error(`Emulator returned ${response.status}`);
      }
      const payload = await response.json();
      let oobCode =
        payload?.oobCode ??
        (() => {
          const link = payload?.oobLink as string | undefined;
          if (!link) return null;
          try {
            const parsed = new URL(link);
            return parsed.searchParams.get("oobCode");
          } catch {
            return null;
          }
        })();
      if (!oobCode) {
        const oobEndpoint = `${base}/emulator/v1/projects/${encodeURIComponent(
          projectId || "demo"
        )}/oobCodes`;
        const oobResponse = await fetch(oobEndpoint);
        if (oobResponse.ok) {
          const oobPayload = await oobResponse.json();
          const entries = Array.isArray(oobPayload?.oobCodes)
            ? oobPayload.oobCodes
            : [];
          const latest = [...entries]
            .reverse()
            .find(
              (entry) =>
                entry?.requestType === "EMAIL_SIGNIN" &&
                String(entry?.email || "").toLowerCase() === email.toLowerCase()
            );
          if (latest?.oobCode) {
            oobCode = latest.oobCode;
          } else if (latest?.oobLink) {
            try {
              const parsed = new URL(latest.oobLink);
              oobCode = parsed.searchParams.get("oobCode");
            } catch {
              oobCode = null;
            }
          }
        }
      }
      if (!oobCode) return null;
      try {
        const url = new URL(redirectUrl);
        url.searchParams.set("mode", "signIn");
        url.searchParams.set("oobCode", oobCode);
        url.searchParams.set("apiKey", apiKey || "demo-local");
        return url.toString();
      } catch {
        return `${redirectUrl}?mode=signIn&oobCode=${encodeURIComponent(
          oobCode
        )}&apiKey=${encodeURIComponent(apiKey || "demo-local")}`;
      }
    },
    [apiKey, emulatorUrl, projectId]
  );

  const clearAuth = React.useCallback(() => {
    localStorage.removeItem(USER_ID_KEY);
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(ID_TOKEN_KEY);
    setAccessToken(null);
    setIdToken(null);
  }, []);

  const completeEmailLink = React.useCallback(
    async (email: string) => {
      if (!authRef.current || !email) return;
      const auth = authRef.current;
      try {
        const {
          EmailAuthProvider,
          isSignInWithEmailLink,
          signInWithEmailLink,
          linkWithCredential,
        } = await import("firebase/auth");
        if (typeof window === "undefined") return;
        if (!isSignInWithEmailLink(auth, window.location.href)) return;
        if (auth.currentUser?.isAnonymous) {
          const credential = EmailAuthProvider.credentialWithLink(
            email,
            window.location.href
          );
          await linkWithCredential(auth.currentUser, credential);
        } else {
          await signInWithEmailLink(auth, email, window.location.href);
        }
        localStorage.removeItem(EMAIL_LINK_KEY);
        window.history.replaceState({}, document.title, window.location.pathname);
      } catch (err) {
        onError?.(err instanceof Error ? err.message : "Email link sign-in failed");
      }
    },
    [onError]
  );

  React.useEffect(() => {
    if (!enabled) return;
    if (!apiKey || !authDomain || !projectId) {
      onError?.("Firebase auth is not configured.");
      return;
    }
    let unsubscribe: (() => void) | undefined;
    let disposed = false;
    (async () => {
      const { initializeApp, getApps } = await import("firebase/app");
      const { getAuth, onIdTokenChanged, connectAuthEmulator } = await import(
        "firebase/auth"
      );
      const app =
        getApps().length > 0
          ? getApps()[0]
          : initializeApp({
              apiKey,
              authDomain,
              projectId,
              appId,
            });
      const auth = getAuth(app);
      if (useEmulator && emulatorUrl) {
        const host = emulatorUrl.startsWith("http")
          ? emulatorUrl
          : `http://${emulatorUrl}`;
        connectAuthEmulator(auth, host, { disableWarnings: true });
      }
      authRef.current = auth;
      unsubscribe = onIdTokenChanged(auth, async (user) => {
        if (disposed) return;
        if (!user) {
          clearAuth();
          setIsAnonymous(false);
          setEmulatorProvider(null);
          localStorage.removeItem(EMULATOR_PROVIDER_KEY);
          return;
        }
        try {
          const token = await user.getIdToken();
          localStorage.setItem(TOKEN_KEY, token);
          localStorage.setItem(ID_TOKEN_KEY, token);
          setAccessToken(token);
          setIdToken(token);
          setIsAnonymous(Boolean(user.isAnonymous));
          const claims = parseJwt(token);
          const userId = claims?.email ?? user.email ?? user.uid;
          if (userId) {
            localStorage.setItem(USER_ID_KEY, userId);
          }
        } catch (err) {
          onError?.(err instanceof Error ? err.message : "Failed to load auth token");
        }
      });

      const { isSignInWithEmailLink } = await import("firebase/auth");
      if (typeof window !== "undefined" && isSignInWithEmailLink(auth, window.location.href)) {
        const storedEmail = localStorage.getItem(EMAIL_LINK_KEY) ?? "";
        if (storedEmail) {
          await completeEmailLink(storedEmail);
        } else {
          onError?.("Missing email for sign-in link. Please request a new link.");
        }
      }
    })();
    return () => {
      disposed = true;
      unsubscribe?.();
    };
  }, [
    enabled,
    apiKey,
    authDomain,
    projectId,
    appId,
    emulatorUrl,
    useEmulator,
    clearAuth,
    onError,
    completeEmailLink,
  ]);

  const startLogin = React.useCallback(
    async (provider?: ProviderName, options?: { link?: boolean }) => {
      if (!enabled) return;
      if (!authRef.current) {
        onError?.("Auth is not ready yet.");
        return;
      }
      if (useEmulator && !emulatorReady) {
        onError?.("Auth emulator is still starting. Please try again in a moment.");
        return;
      }
      onLoadingChange?.(true);
      try {
        const {
          signInWithPopup,
          linkWithPopup,
          signInAnonymously,
          GoogleAuthProvider,
          FacebookAuthProvider,
          OAuthProvider,
        } = await import("firebase/auth");
        if (provider === "anonymous") {
          if (!authRef.current.currentUser) {
            if (useEmulator) {
              await retryEmulatorAuth(async () => signInAnonymously(authRef.current));
            } else {
              await signInAnonymously(authRef.current);
            }
          }
          if (useEmulator) {
            setEmulatorProvider("anonymous");
            localStorage.setItem(EMULATOR_PROVIDER_KEY, "anonymous");
          }
          return;
        }
        if (useEmulator) {
          if (!authRef.current.currentUser) {
            await retryEmulatorAuth(async () => signInAnonymously(authRef.current));
          }
          const nextProvider = provider ?? "google";
          setEmulatorProvider(nextProvider);
          localStorage.setItem(EMULATOR_PROVIDER_KEY, nextProvider);
          return;
        }
        let authProvider;
        switch (provider) {
          case "facebook":
            authProvider = new FacebookAuthProvider();
            break;
          case "apple":
            authProvider = new OAuthProvider("apple.com");
            break;
          case "microsoft": {
            const msProvider = new OAuthProvider("microsoft.com");
            msProvider.setCustomParameters({ prompt: "select_account" });
            authProvider = msProvider;
            break;
          }
          case "google":
          default:
            authProvider = new GoogleAuthProvider();
            break;
        }
        if (options?.link && authRef.current.currentUser) {
          await linkWithPopup(authRef.current.currentUser, authProvider);
        } else {
          await signInWithPopup(authRef.current, authProvider);
        }
      } catch (err) {
        if (useEmulator) {
          try {
            const { signInAnonymously } = await import("firebase/auth");
            if (!authRef.current?.currentUser) {
              await retryEmulatorAuth(async () => signInAnonymously(authRef.current));
            }
            return;
          } catch (fallbackError) {
            const message =
              fallbackError instanceof Error ? fallbackError.message : "Sign in failed";
            onError?.(formatEmulatorError(message));
            return;
          }
        }
        onError?.(err instanceof Error ? err.message : "Sign in failed");
      } finally {
        onLoadingChange?.(false);
      }
    },
    [enabled, useEmulator, onError, onLoadingChange]
  );

  const startEmailLink = React.useCallback(
    async (email: string): Promise<string | null> => {
      if (!enabled) return;
      if (!authRef.current) {
        onError?.("Auth is not ready yet.");
        return;
      }
      if (!email) {
        onError?.("Enter a valid email address.");
        return;
      }
      onLoadingChange?.(true);
      try {
        const { sendSignInLinkToEmail } = await import("firebase/auth");
        const redirectUrl =
          typeof window !== "undefined"
            ? `${window.location.origin}/app/?emailLink=1`
            : "";
        if (!redirectUrl) {
          onError?.("Email link sign-in is unavailable in this environment.");
          return null;
        }
        if (useEmulator) {
          const link = await buildEmulatorEmailLink(email, redirectUrl);
          localStorage.setItem(EMAIL_LINK_KEY, email);
          return link;
        }
        await sendSignInLinkToEmail(authRef.current, email, {
          url: redirectUrl,
          handleCodeInApp: true,
        });
        localStorage.setItem(EMAIL_LINK_KEY, email);
        return null;
      } catch (err) {
        onError?.(err instanceof Error ? err.message : "Failed to send sign-in link");
        return null;
      } finally {
        onLoadingChange?.(false);
      }
    },
    [enabled, onError, onLoadingChange, useEmulator, buildEmulatorEmailLink]
  );

  const signOut = React.useCallback(async () => {
    if (!authRef.current) {
      clearAuth();
      return;
    }
    try {
      const { signOut } = await import("firebase/auth");
      if (useEmulator) {
        await retryEmulatorAuth(async () => signOut(authRef.current));
      } else {
        await signOut(authRef.current);
      }
    } catch (err) {
      onError?.(formatEmulatorError(err instanceof Error ? err.message : "Sign out failed"));
    }
    clearAuth();
  }, [clearAuth, useEmulator, onError]);

  return {
    accessToken,
    idToken,
    isAnonymous,
    emulatorProvider,
    emulatorReady,
    startLogin,
    startEmailLink,
    signOut,
    clearAuth,
  };
}
