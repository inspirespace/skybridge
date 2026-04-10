import { afterEach, describe, expect, it, vi } from "vitest";

const initializeApp = vi.fn(() => ({ name: "app" }));
const getApps = vi.fn(() => []);
const getAppCheck = vi.fn(() => ({ name: "app-check" }));
const initializeAppCheck = vi.fn(() => ({ name: "app-check" }));
const getToken = vi.fn(async () => ({ token: "app-check-token" }));

vi.mock("firebase/app", () => ({
  getApps,
  initializeApp,
}));

vi.mock("firebase/app-check", () => ({
  ReCaptchaV3Provider: class ReCaptchaV3Provider {
    key: string;

    constructor(key: string) {
      this.key = key;
    }
  },
  getAppCheck,
  initializeAppCheck,
  getToken,
}));

afterEach(async () => {
  delete (
    window as Window & {
      __FIREBASE_DEFAULTS__?: unknown;
    }
  ).__FIREBASE_DEFAULTS__;
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.clearAllMocks();
  const { resetFirebaseRuntimeConfigCache } = await import("@/lib/firebase-config");
  resetFirebaseRuntimeConfigCache();
  vi.resetModules();
});

describe("getAppCheckTokenHeader", () => {
  it("uses Firebase Hosting runtime config when build-time config is absent", async () => {
    vi.stubEnv("VITE_FIREBASE_APP_CHECK_ENABLED", "1");
    vi.stubEnv("VITE_FIREBASE_APP_CHECK_SITE_KEY", "site-key");
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          apiKey: "runtime-api-key",
          authDomain: "runtime-project.firebaseapp.com",
          projectId: "runtime-project",
          appId: "runtime-app-id",
        }),
      }))
    );

    const { getAppCheckTokenHeader } = await import("@/lib/firebase-app-check");
    const header = await getAppCheckTokenHeader();

    expect(header).toEqual({ "X-Firebase-AppCheck": "app-check-token" });
    expect(initializeApp).toHaveBeenCalledWith(
      expect.objectContaining({
        apiKey: "runtime-api-key",
        appId: "runtime-app-id",
      })
    );
    expect(initializeAppCheck).toHaveBeenCalled();
    expect(getToken).toHaveBeenCalled();
  });
});
