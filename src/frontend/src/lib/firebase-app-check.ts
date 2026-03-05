import {
  AUTH_MODE,
  FIREBASE_API_KEY,
  FIREBASE_APP_CHECK_DEBUG_TOKEN,
  FIREBASE_APP_CHECK_ENABLED,
  FIREBASE_APP_CHECK_SITE_KEY,
  FIREBASE_APP_ID,
  FIREBASE_AUTH_DOMAIN,
  FIREBASE_PROJECT_ID,
  FIREBASE_USE_EMULATOR,
} from "@/lib/app-config";
import {
  getEffectiveFirebaseWebConfig,
  resolveFirebaseRuntimeConfig,
} from "@/lib/firebase-config";

let appCheckInitPromise: Promise<any | null> | null = null;
let warnedUnavailable = false;

const warnUnavailable = (reason: string, err?: unknown) => {
  if (warnedUnavailable) return;
  warnedUnavailable = true;
  if (err) {
    console.warn(reason, err);
    return;
  }
  console.warn(reason);
};

async function resolveFirebaseApp() {
  const { getApps, initializeApp } = await import("firebase/app");
  const existing = getApps();
  if (existing.length > 0) {
    return existing[0];
  }
  const runtimeConfig = await resolveFirebaseRuntimeConfig();
  const config = getEffectiveFirebaseWebConfig({
    apiKey: FIREBASE_API_KEY,
    authDomain: FIREBASE_AUTH_DOMAIN,
    projectId: FIREBASE_PROJECT_ID,
    appId: FIREBASE_APP_ID,
    runtimeConfig,
    useEmulator: FIREBASE_USE_EMULATOR,
  });
  if (!config.apiKey || !config.authDomain || !config.projectId) {
    return null;
  }
  return initializeApp({
    apiKey: config.apiKey,
    authDomain: config.authDomain,
    projectId: config.projectId,
    appId: config.appId || undefined,
  });
}

async function initAppCheck() {
  if (AUTH_MODE !== "firebase" || !FIREBASE_APP_CHECK_ENABLED) {
    return null;
  }
  if (!FIREBASE_APP_CHECK_SITE_KEY) {
    warnUnavailable("Firebase App Check is enabled but VITE_FIREBASE_APP_CHECK_SITE_KEY is missing.");
    return null;
  }
  if (FIREBASE_USE_EMULATOR && !FIREBASE_APP_CHECK_DEBUG_TOKEN) {
    // Emulator/dev defaults skip App Check unless a debug token is configured.
    return null;
  }

  const app = await resolveFirebaseApp();
  if (!app) {
    warnUnavailable("Firebase App Check could not initialize because Firebase app config is incomplete.");
    return null;
  }

  const appCheckModule = await import("firebase/app-check");
  const { ReCaptchaV3Provider, initializeAppCheck } = appCheckModule;
  const getAppCheck =
    (appCheckModule as { getAppCheck?: (app: unknown) => unknown }).getAppCheck ??
    (appCheckModule as { default?: { getAppCheck?: (app: unknown) => unknown } }).default
      ?.getAppCheck;

  if (FIREBASE_APP_CHECK_DEBUG_TOKEN && typeof window !== "undefined") {
    (window as typeof window & { FIREBASE_APPCHECK_DEBUG_TOKEN?: string }).FIREBASE_APPCHECK_DEBUG_TOKEN =
      FIREBASE_APP_CHECK_DEBUG_TOKEN;
  }

  try {
    return initializeAppCheck(app, {
      provider: new ReCaptchaV3Provider(FIREBASE_APP_CHECK_SITE_KEY),
      isTokenAutoRefreshEnabled: true,
    });
  } catch (err) {
    const code = (err as { code?: string })?.code;
    if (code === "appCheck/already-initialized" || code === "app-check/already-initialized") {
      if (typeof getAppCheck === "function") {
        return getAppCheck(app);
      }
      return null;
    }
    throw err;
  }
}

async function getAppCheckInstance() {
  if (!appCheckInitPromise) {
    appCheckInitPromise = initAppCheck().catch((err) => {
      warnUnavailable("Firebase App Check initialization failed; continuing without App Check header.", err);
      return null;
    });
  }
  return appCheckInitPromise;
}

export async function getAppCheckTokenHeader(): Promise<Record<string, string>> {
  const appCheck = await getAppCheckInstance();
  if (!appCheck) {
    return {};
  }
  try {
    const { getToken } = await import("firebase/app-check");
    const tokenResult = await getToken(appCheck, false);
    const token = tokenResult?.token?.trim();
    if (!token) {
      return {};
    }
    return { "X-Firebase-AppCheck": token };
  } catch (err) {
    warnUnavailable("Firebase App Check token retrieval failed; continuing without App Check header.", err);
    return {};
  }
}
