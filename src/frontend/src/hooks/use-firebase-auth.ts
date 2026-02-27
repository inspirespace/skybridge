import * as React from "react";

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
  allowAnonymous,
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
  allowAnonymous?: boolean;
  onError?: (message: string) => void;
  onLoadingChange?: (loading: boolean) => void;
}) {
  const [accessToken, setAccessToken] = React.useState<string | null>(() =>
    null
  );
  const [idToken, setIdToken] = React.useState<string | null>(() =>
    null
  );
  const [isAnonymous, setIsAnonymous] = React.useState(false);
  const [emulatorProvider, setEmulatorProvider] = React.useState<ProviderName | null>(null);
  const [emulatorReady, setEmulatorReady] = React.useState(!useEmulator);
  const [userId, setUserId] = React.useState<string | null>(null);
  const [emailLinkPending, setEmailLinkPending] = React.useState(false);
  const [authReady, setAuthReady] = React.useState(false);
  const authRef = React.useRef<ReturnType<typeof import("firebase/auth").getAuth> | null>(null);
  const emulatorUrl = React.useMemo(() => {
    if (!useEmulator) return undefined;
    let fallback = "http://localhost:9099";
    if (typeof window !== "undefined") {
      const isHttps = window.location.protocol === "https:";
      const hostname = window.location.hostname;
      if (isHttps && hostname.endsWith("skybridge.localhost")) {
        // Use same-origin proxy in HTTPS local mode to avoid cross-origin CORS drift.
        fallback = "https://skybridge.localhost";
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
    // Reaching the emulator endpoint is enough; 4xx can still mean emulator is up.
    if (response.status >= 500) {
      throw new Error(`Auth emulator readiness check failed (${response.status})`);
    }
    return true;
  }, [useEmulator, emulatorUrl, apiKey]);

  React.useEffect(() => {
    if (!useEmulator) {
      setEmulatorReady(true);
      return;
    }
    let cancelled = false;
    setEmulatorReady(false);
    (async () => {
      let attempt = 0;
      while (!cancelled) {
        try {
          await checkEmulatorReady();
          if (!cancelled) setEmulatorReady(true);
          return;
        } catch {
          if (cancelled) return;
          attempt += 1;
          const waitMs = Math.min(1_000 + attempt * 500, 5_000);
          await delay(waitMs);
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
        url.searchParams.set("email", email);
        return url.toString();
      } catch {
        return `${redirectUrl}?mode=signIn&oobCode=${encodeURIComponent(
          oobCode
        )}&apiKey=${encodeURIComponent(apiKey || "demo-local")}&email=${encodeURIComponent(
          email
        )}`;
      }
    },
    [apiKey, emulatorUrl, projectId]
  );

  const clearAuth = React.useCallback(() => {
    setAccessToken(null);
    setIdToken(null);
    setUserId(null);
    setEmailLinkPending(false);
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
        setEmailLinkPending(false);
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
      try {
        const { initializeApp, getApps } = await import("firebase/app");
        const { getAuth, onIdTokenChanged, connectAuthEmulator } = await import(
          "firebase/auth"
        );
        const { setPersistence, browserSessionPersistence } = await import("firebase/auth");
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
          try {
            connectAuthEmulator(auth, host, { disableWarnings: true });
          } catch (err) {
            const code = (err as { code?: string })?.code;
            // In dev/HMR, auth may already be emulator-configured. Keep existing config.
            if (code !== "auth/emulator-config-failed") {
              throw err;
            }
          }
        }
        await setPersistence(auth, browserSessionPersistence);
        authRef.current = auth;
        setAuthReady(true);
        unsubscribe = onIdTokenChanged(auth, async (user) => {
          if (disposed) return;
          if (!user) {
            clearAuth();
            setIsAnonymous(false);
            setEmulatorProvider(null);
            return;
          }
          if (user.isAnonymous && !allowAnonymous) {
            try {
              const { signOut } = await import("firebase/auth");
              await signOut(auth);
            } catch {
              // Best-effort cleanup for stale anonymous sessions.
            }
            clearAuth();
            setIsAnonymous(false);
            setEmulatorProvider(null);
            return;
          }
          try {
            const token = await user.getIdToken();
            setAccessToken(token);
            setIdToken(token);
            setIsAnonymous(Boolean(user.isAnonymous));
            setUserId(user.uid ?? null);
            setEmailLinkPending(false);
          } catch (err) {
            onError?.(err instanceof Error ? err.message : "Failed to load auth token");
          }
        });

        const { isSignInWithEmailLink } = await import("firebase/auth");
        if (typeof window !== "undefined" && isSignInWithEmailLink(auth, window.location.href)) {
          setEmailLinkPending(true);
        }
      } catch (err) {
        if (!disposed) {
          setAuthReady(false);
          onError?.(formatEmulatorError(err instanceof Error ? err.message : "Firebase auth initialization failed"));
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
    allowAnonymous,
    clearAuth,
    onError,
    completeEmailLink,
  ]);

  const startLogin = React.useCallback(
    async (provider?: ProviderName, options?: { link?: boolean }) => {
      if (!enabled) return;
      const auth = authRef.current;
      if (!auth) {
        onError?.("Auth is not ready yet.");
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
          if (!allowAnonymous) {
            onError?.("Guest sign-in is disabled.");
            return;
          }
          if (!auth.currentUser) {
            if (useEmulator) {
              await retryEmulatorAuth(async () => {
                await signInAnonymously(auth);
              });
            } else {
              await signInAnonymously(auth);
            }
          }
          if (useEmulator) {
            setEmulatorProvider("anonymous");
          }
          return;
        }
        if (useEmulator) {
          if (!auth.currentUser) {
            await retryEmulatorAuth(async () => {
              await signInAnonymously(auth);
            });
          }
          const nextProvider = provider ?? "google";
          setEmulatorProvider(nextProvider);
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
        if (options?.link && auth.currentUser) {
          await linkWithPopup(auth.currentUser, authProvider);
        } else {
          await signInWithPopup(auth, authProvider);
        }
      } catch (err) {
        if (useEmulator) {
          try {
            const { signInAnonymously } = await import("firebase/auth");
            if (!authRef.current?.currentUser) {
              const nextAuth = authRef.current;
              if (!nextAuth) return;
              await retryEmulatorAuth(async () => {
                await signInAnonymously(nextAuth);
              });
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
    [allowAnonymous, enabled, useEmulator, onError, onLoadingChange]
  );

  const startEmailLink = React.useCallback(
    async (email: string): Promise<string | null> => {
      if (!enabled) return null;
      const auth = authRef.current;
      if (!auth) {
        onError?.("Auth is not ready yet.");
        return null;
      }
      if (!email) {
        onError?.("Enter a valid email address.");
        return null;
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
          return link;
        }
        await sendSignInLinkToEmail(auth, email, {
          url: redirectUrl,
          handleCodeInApp: true,
        });
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
    const auth = authRef.current;
    if (!auth) {
      clearAuth();
      return;
    }
    try {
      const { signOut } = await import("firebase/auth");
      if (useEmulator) {
        await retryEmulatorAuth(async () => {
          await signOut(auth);
        });
      } else {
        await signOut(auth);
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
    authReady,
    userId,
    emailLinkPending,
    startLogin,
    startEmailLink,
    completeEmailLink,
    signOut,
    clearAuth,
  };
}
