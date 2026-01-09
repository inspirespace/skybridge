import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { resolve } from "node:path";

function hasDisplay(): boolean {
  return Boolean(process.env.DISPLAY);
}

export default async function globalSetup(): Promise<void> {
  if (!hasDisplay()) return;

  const candidates = [
    resolve(process.cwd(), "scripts", "start-e2e-vnc.sh"),
    resolve(process.cwd(), "..", "..", "scripts", "start-e2e-vnc.sh"),
  ];
  const scriptPath = candidates.find((candidate) => existsSync(candidate));
  if (!scriptPath) return;

  try {
    execFileSync(scriptPath, { stdio: "ignore" });
  } catch {
    // Non-fatal: if VNC fails to start, Playwright will still run headless.
  }
}
