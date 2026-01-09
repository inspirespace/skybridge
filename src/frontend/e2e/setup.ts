import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { resolve } from "node:path";

function hasDisplay(): boolean {
  return Boolean(process.env.DISPLAY);
}

function inVsCode(): boolean {
  return process.env.TERM_PROGRAM === "vscode" || Boolean(process.env.VSCODE_PID);
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

  if (!inVsCode()) return;
  const port = process.env.NOVNC_PORT || "6080";
  const url = `http://localhost:${port}/vnc_auto.html?autoconnect=1&resize=remote`;
  try {
    execFileSync("code", ["--open-url", url], { stdio: "ignore" });
  } catch {
    // Best effort only; some environments do not have the code CLI available.
  }
}
