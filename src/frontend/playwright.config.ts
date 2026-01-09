/// <reference types="node" />
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60000,
  globalSetup: "./e2e/setup.ts",
  use: {
    baseURL: "http://localhost:4173",
    trace: "retain-on-failure",
    headless: process.env.HEADFUL ? false : true,
    launchOptions: {
      chromiumSandbox: false,
      env: {
        ...process.env,
        LIBGL_ALWAYS_SOFTWARE: "1",
        LIBGL_DRI3_DISABLE: "1",
      },
      args: [
        "--disable-gpu",
        "--use-gl=swiftshader",
        "--disable-dev-shm-usage",
        "--no-sandbox",
      ],
    },
  },
  webServer: {
    command: "npm run dev -- --host 0.0.0.0 --port 4173",
    url: "http://localhost:4173",
    reuseExistingServer: true,
    env: {
      VITE_AUTH_MODE: "header",
      VITE_API_BASE_URL: "http://localhost:8000/api",
    },
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
