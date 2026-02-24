export const AUTH_MODE = import.meta.env.VITE_AUTH_MODE ?? "header";
export const AUTH_ISSUER =
  import.meta.env.VITE_AUTH_ISSUER_URL ??
  import.meta.env.VITE_AUTH_BROWSER_ISSUER_URL ??
  "";
export const AUTH_CLIENT_ID = import.meta.env.VITE_AUTH_CLIENT_ID ?? "skybridge-inspirespace";
export const AUTH_SCOPE =
  import.meta.env.VITE_AUTH_SCOPE ?? "openid profile email offline_access";
export const AUTH_REDIRECT_PATH =
  import.meta.env.VITE_AUTH_REDIRECT_PATH ?? "/app/auth/callback";
export const AUTH_PROVIDER_PARAM = import.meta.env.VITE_AUTH_PROVIDER_PARAM ?? "kc_idp_hint";
export const AUTH_LOGOUT_URL = import.meta.env.VITE_AUTH_LOGOUT_URL ?? "";

export const FIREBASE_API_KEY = import.meta.env.VITE_FIREBASE_API_KEY ?? "";
export const FIREBASE_AUTH_DOMAIN = import.meta.env.VITE_FIREBASE_AUTH_DOMAIN ?? "";
export const FIREBASE_PROJECT_ID = import.meta.env.VITE_FIREBASE_PROJECT_ID ?? "";
export const FIREBASE_APP_ID = import.meta.env.VITE_FIREBASE_APP_ID ?? "";
export const FIREBASE_EMULATOR_HOST =
  import.meta.env.VITE_FIREBASE_AUTH_EMULATOR_HOST ?? "";
export const FIREBASE_USE_EMULATOR =
  (import.meta.env.VITE_FIREBASE_USE_EMULATOR ?? "") === "1";
export const FIREBASE_ENABLE_GOOGLE =
  (import.meta.env.VITE_FIREBASE_ENABLE_GOOGLE ?? "") === "1";
export const FIREBASE_ENABLE_APPLE =
  (import.meta.env.VITE_FIREBASE_ENABLE_APPLE ?? "") === "1";
export const FIREBASE_ENABLE_FACEBOOK =
  (import.meta.env.VITE_FIREBASE_ENABLE_FACEBOOK ?? "") === "1";
export const FIREBASE_ENABLE_MICROSOFT =
  (import.meta.env.VITE_FIREBASE_ENABLE_MICROSOFT ?? "") === "1";
export const FIREBASE_ENABLE_GUEST =
  (import.meta.env.VITE_FIREBASE_ENABLE_GUEST ?? "") === "1";

export const DEV_PREFILL =
  import.meta.env.DEV && (import.meta.env.VITE_DEV_PREFILL_CREDENTIALS ?? "") === "1";
export const DEV_CLOUD_AHOY_EMAIL = import.meta.env.VITE_CLOUD_AHOY_EMAIL ?? "";
export const DEV_CLOUD_AHOY_PASSWORD = import.meta.env.VITE_CLOUD_AHOY_PASSWORD ?? "";
export const DEV_FLYSTO_EMAIL = import.meta.env.VITE_FLYSTO_EMAIL ?? "";
export const DEV_FLYSTO_PASSWORD = import.meta.env.VITE_FLYSTO_PASSWORD ?? "";

const RETENTION_DAYS = Number.parseInt(import.meta.env.VITE_RETENTION_DAYS ?? "7", 10);
export const retentionDays = Number.isFinite(RETENTION_DAYS) ? RETENTION_DAYS : 7;
