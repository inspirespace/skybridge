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
  type RuntimeFirebaseConfig = {
    apiKey: string;
    authDomain: string;
    projectId: string;
    appId?: string;
  };

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
  const [runtimeConfig, setRuntimeConfig] = React.useState<RuntimeFirebaseConfig | null>(null);
  const [runtimeConfigAttempted, setRuntimeConfigAttempted] = React.useState(false);
  const [runtimeConfigError, setRuntimeConfigError] = React.useState<string | null>(null);
  const authRef = React.useRef<ReturnType<typeof import("firebase/auth").getAuth> | null>(null);
  const effectiveApiKey = React.useMemo(() => {
    const configured = apiKey?.trim() ?? "";
    if (configured) return configured;
    const runtime = runtimeConfig?.apiKey?.trim() ?? "";
    if (runtime) return runtime;
    return useEmulator ? "demo-local" : "";
  }, [apiKey, runtimeConfig?.apiKey, useEmulator]);
  const effectiveProjectId = React.useMemo(() => {
    const configured = projectId?.trim() ?? "";
    if (configured) return configured;
    const runtime = runtimeConfig?.projectId?.trim() ?? "";
    if (runtime) return runtime;
    return useEmulator ? "demo-local" : "";
  }, [projectId, runtimeConfig?.projectId, useEmulator]);
  const effectiveAuthDomain = React.useMemo(() => {
    const configured = authDomain?.trim() ?? "";
    if (configured) return configured;
    const runtime = runtimeConfig?.authDomain?.trim() ?? "";
    if (runtime) return runtime;
    return effectiveProjectId ? `${effectiveProjectId}.firebaseapp.com` : "";
  }, [authDomain, runtimeConfig?.authDomain, effectiveProjectId]);
  const effectiveAppId = React.useMemo(() => {
    const configured = appId?.trim() ?? "";
    if (configured) return configured;
    const runtime = runtimeConfig?.appId?.trim() ?? "";
    if (runtime) return runtime;
    return useEmulator ? "demo-local-app" : "";
  }, [appId, runtimeConfig?.appId, useEmulator]);

  React.useEffect(() => {
    if (!enabled) return;
    if (effectiveApiKey && effectiveAuthDomain && effectiveProjectId) {
      setRuntimeConfigAttempted(true);
      setRuntimeConfigError(null);
      return;
    }
    if (typeof window === "undefined") return;

    const readGlobalRuntimeConfig = (): RuntimeFirebaseConfig | null => {
      const defaultsRaw = (
        window as Window & {
          __FIREBASE_DEFAULTS__?: unknown;
        }
      ).__FIREBASE_DEFAULTS__;
      if (!defaultsRaw) return null;

      let defaults = defaultsRaw;
      if (typeof defaultsRaw === "string") {
        try {
          defaults = JSON.parse(defaultsRaw);
        } catch {
          return null;
        }
      }

      const root =
        typeof defaults === "object" && defaults
          ? ((defaults as { config?: unknown }).config ?? defaults)
          : defaults;
      if (!root || typeof root !== "object") return null;

      const asString = (value: unknown) =>
        typeof value === "string" ? value.trim() : "";
      const candidate = root as {
        apiKey?: unknown;
        authDomain?: unknown;
        projectId?: unknown;
        appId?: unknown;
      };
      const apiKeyValue = asString(candidate.apiKey);
      const authDomainValue = asString(candidate.authDomain);
      const projectIdValue = asString(candidate.projectId);
      const appIdValue = asString(candidate.appId);

      if (!apiKeyValue || !projectIdValue) return null;
      return {
        apiKey: apiKeyValue,
        authDomain: authDomainValue,
        projectId: projectIdValue,
        appId: appIdValue,
      };
    };

    const mergeRuntimeConfig = (resolved: RuntimeFirebaseConfig) => {
      setRuntimeConfig((prev) => {
        const nextApiKey = resolved.apiKey || prev?.apiKey || "";
        const nextAuthDomain = resolved.authDomain || prev?.authDomain || "";
        const nextProjectId = resolved.projectId || prev?.projectId || "";
        const nextAppId = resolved.appId || prev?.appId || "";
        if (
          prev?.apiKey === nextApiKey &&
          prev?.authDomain === nextAuthDomain &&
          prev?.projectId === nextProjectId &&
          prev?.appId === nextAppId
        ) {
          return prev;
        }
        return {
          apiKey: nextApiKey,
          authDomain: nextAuthDomain,
          projectId: nextProjectId,
          appId: nextAppId,
        };
      });
    };

    const globalConfig = readGlobalRuntimeConfig();
    if (globalConfig) {
      mergeRuntimeConfig(globalConfig);
      setRuntimeConfigAttempted(true);
      setRuntimeConfigError(null);
      return;
    }

    let cancelled = false;
    (async () => {
      try {
        const response = await fetch("/__/firebase/init.json", {
          method: "GET",
          cache: "no-store",
        });
        if (!response.ok) {
          if (!cancelled) {
            setRuntimeConfigError(`init.json returned ${response.status}`);
          }
          return;
        }
        const payload = await response.json();
        const resolved: RuntimeFirebaseConfig = {
          apiKey: typeof payload?.apiKey === "string" ? payload.apiKey : "",
          authDomain: typeof payload?.authDomain === "string" ? payload.authDomain : "",
          projectId: typeof payload?.projectId === "string" ? payload.projectId : "",
          appId: typeof payload?.appId === "string" ? payload.appId : "",
        };
        if (!cancelled) {
          if (!resolved.apiKey || !resolved.projectId) {
            setRuntimeConfigError("init.json did not include apiKey/projectId");
          } else {
            mergeRuntimeConfig(resolved);
            setRuntimeConfigError(null);
          }
        }
      } catch (err) {
        if (!cancelled) {
          const message =
            err instanceof Error ? err.message : "init.json fetch failed";
          setRuntimeConfigError(message);
        }
      } finally {
        if (!cancelled) {
          setRuntimeConfigAttempted(true);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [enabled, effectiveApiKey, effectiveAuthDomain, effectiveProjectId]);

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
      effectiveApiKey
    )}`;
    const response = await fetch(endpoint, { method: "GET", mode: "cors" });
    // Reaching the emulator endpoint is enough; 4xx can still mean emulator is up.
    if (response.status >= 500) {
      throw new Error(`Auth emulator readiness check failed (${response.status})`);
    }
    return true;
  }, [useEmulator, emulatorUrl, effectiveApiKey]);

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
        effectiveApiKey
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
          effectiveProjectId || "demo"
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
        url.searchParams.set("apiKey", effectiveApiKey || "demo-local");
        url.searchParams.set("email", email);
        return url.toString();
      } catch {
        return `${redirectUrl}?mode=signIn&oobCode=${encodeURIComponent(
          oobCode
        )}&apiKey=${encodeURIComponent(effectiveApiKey || "demo-local")}&email=${encodeURIComponent(
          email
        )}`;
      }
    },
    [effectiveApiKey, emulatorUrl, effectiveProjectId]
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
    if (!runtimeConfigAttempted) return;
    if (!effectiveApiKey || !effectiveAuthDomain || !effectiveProjectId) {
      if (runtimeConfigError) {
        onError?.(`Firebase auth is not configured (${runtimeConfigError}).`);
      } else {
        onError?.("Firebase auth is not configured.");
      }
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
                apiKey: effectiveApiKey,
                authDomain: effectiveAuthDomain,
                projectId: effectiveProjectId,
                appId: effectiveAppId || undefined,
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
    effectiveApiKey,
    effectiveAuthDomain,
    effectiveProjectId,
    effectiveAppId,
    emulatorUrl,
    useEmulator,
    allowAnonymous,
    clearAuth,
    onError,
    completeEmailLink,
    runtimeConfigAttempted,
    runtimeConfigError,
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
