import {
  rewriteHttpToHttpsForRuntimeHost,
  type RuntimeLocationLike,
} from "@/lib/runtime-endpoints";

const FIREBASE_USE_EMULATOR =
  (import.meta.env.VITE_FIREBASE_USE_EMULATOR ?? "") === "1";

const PATCH_FLAG = "__skybridgeFirebaseEmulatorProxyPatched";

export const patchFirebaseEmulatorRequests = (runtimeLocation?: RuntimeLocationLike) => {
  if (!FIREBASE_USE_EMULATOR) return;
  if (typeof window === "undefined") return;
  const activeLocation = runtimeLocation ?? {
    origin: window.location.origin,
    protocol: window.location.protocol,
    hostname: window.location.hostname,
  };
  if (activeLocation.protocol !== "https:") return;
  if ((window as unknown as Record<string, boolean>)[PATCH_FLAG]) return;
  (window as unknown as Record<string, boolean>)[PATCH_FLAG] = true;
  const rewriteEmulatorUrl = (url: string) =>
    rewriteHttpToHttpsForRuntimeHost({ url, runtimeLocation: activeLocation });

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

  if (typeof navigator !== "undefined" && typeof navigator.sendBeacon === "function") {
    const originalBeacon = navigator.sendBeacon.bind(navigator);
    navigator.sendBeacon = ((url: string | URL, data?: BodyInit | null) => {
      const raw = typeof url === "string" ? url : url.toString();
      const nextUrl = rewriteEmulatorUrl(raw);
      return originalBeacon(nextUrl, data);
    }) as typeof navigator.sendBeacon;
  }
};
