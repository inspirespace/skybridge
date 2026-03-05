import { afterEach, describe, expect, it, vi } from "vitest";

const ORIGINAL_XHR_OPEN = XMLHttpRequest.prototype.open;
const ORIGINAL_FETCH = window.fetch;
const ORIGINAL_BEACON = navigator.sendBeacon;

afterEach(() => {
  XMLHttpRequest.prototype.open = ORIGINAL_XHR_OPEN;
  window.fetch = ORIGINAL_FETCH;
  navigator.sendBeacon = ORIGINAL_BEACON;
  delete (window as unknown as Record<string, unknown>).__skybridgeFirebaseEmulatorProxyPatched;
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  vi.resetModules();
});

describe("patchFirebaseEmulatorRequests", () => {
  it("rewrites runtime-hosted emulator calls to https", async () => {
    vi.stubEnv("VITE_FIREBASE_USE_EMULATOR", "1");
    const fetchMock = vi.fn(async () => new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    const { patchFirebaseEmulatorRequests } = await import("@/lib/firebase-emulator");

    patchFirebaseEmulatorRequests({
      origin: "https://app.example",
      protocol: "https:",
      hostname: "app.example",
    });

    await window.fetch("http://auth.app.example/emulator/v1/projects/demo/oobCodes");
    const firstCall = fetchMock.mock.calls.at(0) as unknown[] | undefined;
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(firstCall?.[0]).toBe(
      "https://auth.app.example/emulator/v1/projects/demo/oobCodes"
    );
  });

  it("keeps external hosts unchanged", async () => {
    vi.stubEnv("VITE_FIREBASE_USE_EMULATOR", "1");
    const fetchMock = vi.fn(async () => new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    const { patchFirebaseEmulatorRequests } = await import("@/lib/firebase-emulator");

    patchFirebaseEmulatorRequests({
      origin: "https://app.example",
      protocol: "https:",
      hostname: "app.example",
    });

    await window.fetch("http://example.net/api");
    const firstCall = fetchMock.mock.calls.at(0) as unknown[] | undefined;
    expect(firstCall?.[0]).toBe("http://example.net/api");
  });
});
