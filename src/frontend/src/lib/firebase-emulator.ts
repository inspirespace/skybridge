const FIREBASE_USE_EMULATOR =
  (import.meta.env.VITE_FIREBASE_USE_EMULATOR ?? "") === "1";

const PROXY_HOSTS = [
  "skybridge.localhost",
  "firestore.skybridge.localhost",
  "auth.skybridge.localhost",
  "storage.skybridge.localhost",
  "functions.skybridge.localhost",
  "hosting.skybridge.localhost",
];

const PATCH_FLAG = "__skybridgeFirebaseEmulatorProxyPatched";

const rewriteEmulatorUrl = (url: string) => {
  for (const host of PROXY_HOSTS) {
    const prefix = `http://${host}`;
    if (url.startsWith(prefix)) {
      return url.replace(prefix, `https://${host}`);
    }
  }
  return url;
};

export const patchFirebaseEmulatorRequests = () => {
  if (!FIREBASE_USE_EMULATOR) return;
  if (typeof window === "undefined") return;
  if (window.location.protocol !== "https:") return;
  if (!window.location.hostname.endsWith("skybridge.localhost")) return;
  if ((window as unknown as Record<string, boolean>)[PATCH_FLAG]) return;
  (window as unknown as Record<string, boolean>)[PATCH_FLAG] = true;

  const originalOpen = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function openProxy(
    method: string,
    url: string,
    async?: boolean,
    username?: string | null,
    password?: string | null
  ) {
    const nextUrl = rewriteEmulatorUrl(url);
    return originalOpen.call(this, method, nextUrl, async ?? true, username ?? null, password ?? null);
  };

  const originalFetch = window.fetch.bind(window);
  window.fetch = ((input: RequestInfo | URL, init?: RequestInit) => {
    const url =
      typeof input === "string"
        ? input
        : input instanceof URL
          ? input.toString()
          : input.url;
    const nextUrl = rewriteEmulatorUrl(url);
    if (nextUrl !== url) {
      if (typeof input === "string") {
        return originalFetch(nextUrl, init);
      }
      if (input instanceof URL) {
        return originalFetch(new URL(nextUrl), init);
      }
      const nextRequest = new Request(nextUrl, input);
      return originalFetch(nextRequest, init);
    }
    return originalFetch(input as RequestInfo, init);
  }) as typeof window.fetch;
};
