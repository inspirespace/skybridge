import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

const firebaseConfigPath = path.resolve(process.cwd(), "../../firebase.json");

const readCspValue = () => {
  const payload = JSON.parse(readFileSync(firebaseConfigPath, "utf8")) as {
    hosting?: {
      headers?: Array<{
        source?: string;
        headers?: Array<{ key?: string; value?: string }>;
      }>;
    };
  };
  const globalHeaders = payload.hosting?.headers?.find((entry) => entry.source === "**");
  const cspHeader = globalHeaders?.headers?.find(
    (header) => header.key === "Content-Security-Policy"
  );
  return cspHeader?.value ?? "";
};

describe("firebase hosting CSP", () => {
  it("allows Firebase Auth helper frames and scripts for custom-domain auth", () => {
    const csp = readCspValue();

    expect(csp).toContain("script-src 'self' 'unsafe-inline' https://apis.google.com");
    expect(csp).toContain("https://www.google.com");
    expect(csp).toContain("https://www.gstatic.com");
    expect(csp).toContain("frame-src 'self' https://*.firebaseapp.com https://*.web.app");
  });
});
