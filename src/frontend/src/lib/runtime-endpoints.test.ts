import { describe, expect, it } from "vitest";

import {
  resolveApiBaseUrl,
  resolveAuthEmulatorBaseUrl,
  resolveFirestoreEmulatorHostPort,
  rewriteHttpToHttpsForRuntimeHost,
} from "@/lib/runtime-endpoints";

const HTTPS_RUNTIME = {
  origin: "https://app.example",
  protocol: "https:",
  hostname: "app.example",
};

const HTTP_RUNTIME = {
  origin: "http://localhost:5173",
  protocol: "http:",
  hostname: "localhost",
};

describe("resolveApiBaseUrl", () => {
  it("defaults to same-origin api route", () => {
    expect(resolveApiBaseUrl("")).toBe("/api");
  });

  it("normalizes trailing slash for explicit config", () => {
    expect(resolveApiBaseUrl("https://api.example/v1/")).toBe("https://api.example/v1");
  });
});

describe("resolveAuthEmulatorBaseUrl", () => {
  it("uses explicit emulator host when provided", () => {
    const resolved = resolveAuthEmulatorBaseUrl({
      useEmulator: true,
      explicitHost: "https://emulator.example",
      runtimeLocation: HTTPS_RUNTIME,
    });
    expect(resolved).toBe("https://emulator.example");
  });

  it("uses same-origin base for https runtime", () => {
    const resolved = resolveAuthEmulatorBaseUrl({
      useEmulator: true,
      runtimeLocation: HTTPS_RUNTIME,
    });
    expect(resolved).toBe("https://app.example");
  });

  it("falls back to localhost for http runtime", () => {
    const resolved = resolveAuthEmulatorBaseUrl({
      useEmulator: true,
      runtimeLocation: HTTP_RUNTIME,
    });
    expect(resolved).toBe("http://localhost:9099");
  });
});

describe("resolveFirestoreEmulatorHostPort", () => {
  it("uses same-origin host and tls port in https runtime", () => {
    const resolved = resolveFirestoreEmulatorHostPort({
      useEmulator: true,
      runtimeLocation: HTTPS_RUNTIME,
    });
    expect(resolved).toEqual({
      host: "app.example",
      port: 443,
    });
  });

  it("falls back to localhost firestore port in http runtime", () => {
    const resolved = resolveFirestoreEmulatorHostPort({
      useEmulator: true,
      runtimeLocation: HTTP_RUNTIME,
    });
    expect(resolved).toEqual({
      host: "localhost",
      port: 8080,
    });
  });

  it("maps localhost auth-emulator override to firestore port", () => {
    const resolved = resolveFirestoreEmulatorHostPort({
      useEmulator: true,
      explicitHost: "http://localhost:9099",
      runtimeLocation: HTTP_RUNTIME,
    });
    expect(resolved).toEqual({
      host: "localhost",
      port: 8080,
    });
  });
});

describe("rewriteHttpToHttpsForRuntimeHost", () => {
  it("rewrites the current host", () => {
    const rewritten = rewriteHttpToHttpsForRuntimeHost({
      url: "http://app.example/identitytoolkit.googleapis.com/v1/projects",
      runtimeLocation: HTTPS_RUNTIME,
    });
    expect(rewritten.startsWith("https://app.example/")).toBe(true);
  });

  it("rewrites matching subdomains", () => {
    const rewritten = rewriteHttpToHttpsForRuntimeHost({
      url: "http://auth.app.example/path",
      runtimeLocation: HTTPS_RUNTIME,
    });
    expect(rewritten).toBe("https://auth.app.example/path");
  });

  it("keeps external domains unchanged", () => {
    const rewritten = rewriteHttpToHttpsForRuntimeHost({
      url: "http://example.net/path",
      runtimeLocation: HTTPS_RUNTIME,
    });
    expect(rewritten).toBe("http://example.net/path");
  });
});
