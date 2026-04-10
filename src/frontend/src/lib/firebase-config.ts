export type FirebaseWebConfig = {
  apiKey: string;
  authDomain: string;
  projectId: string;
  appId: string;
};

type PartialFirebaseWebConfig = Partial<FirebaseWebConfig> | null | undefined;

const INIT_CONFIG_PATH = "/__/firebase/init.json";

let runtimeConfigPromise: Promise<FirebaseWebConfig | null> | null = null;

const asString = (value: unknown) => (typeof value === "string" ? value.trim() : "");

const normalizeFirebaseWebConfig = (
  config: PartialFirebaseWebConfig
): FirebaseWebConfig | null => {
  const apiKey = asString(config?.apiKey);
  const projectId = asString(config?.projectId);
  if (!apiKey || !projectId) {
    return null;
  }
  return {
    apiKey,
    authDomain: asString(config?.authDomain) || `${projectId}.firebaseapp.com`,
    projectId,
    appId: asString(config?.appId),
  };
};

export const getEffectiveFirebaseWebConfig = ({
  apiKey,
  authDomain,
  projectId,
  appId,
  runtimeConfig,
  useEmulator,
}: {
  apiKey?: string;
  authDomain?: string;
  projectId?: string;
  appId?: string;
  runtimeConfig?: FirebaseWebConfig | null;
  useEmulator?: boolean;
}): FirebaseWebConfig => {
  const resolvedProjectId =
    asString(projectId) || runtimeConfig?.projectId || (useEmulator ? "demo-local" : "");
  const resolvedApiKey =
    asString(apiKey) || runtimeConfig?.apiKey || (useEmulator ? "demo-local" : "");
  const resolvedAuthDomain =
    asString(authDomain) ||
    runtimeConfig?.authDomain ||
    (resolvedProjectId ? `${resolvedProjectId}.firebaseapp.com` : "");
  const resolvedAppId =
    asString(appId) || runtimeConfig?.appId || (useEmulator ? "demo-local-app" : "");

  return {
    apiKey: resolvedApiKey,
    authDomain: resolvedAuthDomain,
    projectId: resolvedProjectId,
    appId: resolvedAppId,
  };
};

export const readGlobalFirebaseWebConfig = (): FirebaseWebConfig | null => {
  if (typeof window === "undefined") {
    return null;
  }
  const defaultsRaw = (
    window as Window & {
      __FIREBASE_DEFAULTS__?: unknown;
    }
  ).__FIREBASE_DEFAULTS__;
  if (!defaultsRaw) {
    return null;
  }

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
  if (!root || typeof root !== "object") {
    return null;
  }

  return normalizeFirebaseWebConfig(root as PartialFirebaseWebConfig);
};

export const fetchFirebaseRuntimeConfig = async (
  fetchImpl: typeof fetch = fetch
): Promise<FirebaseWebConfig | null> => {
  const response = await fetchImpl(INIT_CONFIG_PATH, {
    method: "GET",
    cache: "no-store",
  });
  if (!response.ok) {
    return null;
  }
  const payload = await response.json();
  return normalizeFirebaseWebConfig(payload as PartialFirebaseWebConfig);
};

export const resolveFirebaseRuntimeConfig = async (): Promise<FirebaseWebConfig | null> => {
  const globalConfig = readGlobalFirebaseWebConfig();
  if (globalConfig) {
    return globalConfig;
  }
  if (!runtimeConfigPromise) {
    runtimeConfigPromise = fetchFirebaseRuntimeConfig().catch(() => null);
  }
  return runtimeConfigPromise;
};

export const resetFirebaseRuntimeConfigCache = () => {
  runtimeConfigPromise = null;
};
