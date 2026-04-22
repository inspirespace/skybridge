import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import fs from "fs";
import path from "path";

function loadProjectIdFromFirebaserc(): string | null {
  const candidates = [
    process.env.FIREBASERC_FILE,
    path.resolve(__dirname, ".firebaserc"),
    path.resolve(__dirname, "../../.firebaserc"),
  ].filter((value): value is string => Boolean(value && value.trim()));
  for (const filePath of candidates) {
    if (!fs.existsSync(filePath)) continue;
    try {
      const payload = JSON.parse(fs.readFileSync(filePath, "utf-8"));
      const projectId = payload?.projects?.default;
      if (typeof projectId === "string" && projectId.trim()) {
        return projectId.trim();
      }
    } catch {
      continue;
    }
  }
  return null;
}

function setEnvDefault(target: string, ...sources: Array<string | undefined>) {
  const current = process.env[target];
  if (current && current.trim()) {
    return;
  }
  for (const source of sources) {
    if (source && source.trim()) {
      process.env[target] = source.trim();
      return;
    }
  }
}

function parsePositiveInt(value: string | undefined): number | null {
  if (!value || !value.trim()) {
    return null;
  }
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return null;
  }
  return parsed;
}

const derivedProjectId =
  process.env.FIREBASE_PROJECT_ID ?? loadProjectIdFromFirebaserc() ?? "";

setEnvDefault("VITE_FIREBASE_PROJECT_ID", derivedProjectId);

if (!process.env.VITE_FIREBASE_AUTH_DOMAIN && process.env.VITE_FIREBASE_PROJECT_ID) {
  process.env.VITE_FIREBASE_AUTH_DOMAIN =
    `${process.env.VITE_FIREBASE_PROJECT_ID}.firebaseapp.com`;
}

setEnvDefault("VITE_FIREBASE_APP_CHECK_ENABLED", process.env.FIREBASE_APP_CHECK_ENABLED);
setEnvDefault("VITE_FIREBASE_APP_CHECK_SITE_KEY", process.env.FIREBASE_APP_CHECK_SITE_KEY);
setEnvDefault("VITE_FIREBASE_APP_CHECK_DEBUG_TOKEN", process.env.FIREBASE_APP_CHECK_DEBUG_TOKEN);
setEnvDefault("VITE_FIRESTORE_JOBS_COLLECTION", process.env.FIRESTORE_JOBS_COLLECTION);
setEnvDefault("VITE_RETENTION_DAYS", process.env.BACKEND_RETENTION_DAYS);
setEnvDefault("VITE_CLOUD_AHOY_EMAIL", process.env.CLOUD_AHOY_EMAIL);
setEnvDefault("VITE_CLOUD_AHOY_PASSWORD", process.env.CLOUD_AHOY_PASSWORD);
setEnvDefault("VITE_FLYSTO_EMAIL", process.env.FLYSTO_EMAIL);
setEnvDefault("VITE_FLYSTO_PASSWORD", process.env.FLYSTO_PASSWORD);
const runningStaleTimeoutSeconds = parsePositiveInt(
  process.env.BACKEND_RUNNING_STALE_TIMEOUT_SECONDS
);
const derivedWarningSeconds =
  runningStaleTimeoutSeconds && runningStaleTimeoutSeconds > 30
    ? String(runningStaleTimeoutSeconds - 30)
    : undefined;
setEnvDefault("VITE_RUNNING_STALL_WARNING_SECONDS", derivedWarningSeconds);

// https://vite.dev/config/
export default defineConfig({
  appType: "mpa",
  assetsInclude: ["**/*.woff", "**/*.woff2"],
  plugins: [
    react(),
    {
      name: "static-partials",
      transformIndexHtml(html) {
        const header = fs.readFileSync(
          path.resolve(__dirname, "partials/header.html"),
          "utf-8"
        );
        const footer = fs.readFileSync(
          path.resolve(__dirname, "partials/footer.html"),
          "utf-8"
        );
        const retentionDays = process.env.VITE_RETENTION_DAYS || "7";
        return html
          .replace("<!-- @partial header -->", header)
          .replace("<!-- @partial footer -->", footer)
          .replace(/\{\{RETENTION_DAYS\}\}/g, retentionDays);
      },
    },
    {
      name: "spa-app-rewrite",
      configureServer(server) {
        server.middlewares.use((req, res, next) => {
          const url = req.url?.split("?")[0] ?? "";
          if (!url.startsWith("/app/")) {
            next();
            return;
          }
          if (url === "/app/" || url === "/app/index.html") {
            next();
            return;
          }
          if (url.includes(".")) {
            next();
            return;
          }
          const htmlPath = path.resolve(__dirname, "app/index.html");
          const html = fs.readFileSync(htmlPath, "utf-8");
          server
            .transformIndexHtml("/app/index.html", html)
            .then((result) => {
              res.statusCode = 200;
              res.setHeader("Content-Type", "text/html");
              res.end(result);
            })
            .catch((err) => next(err));
        });
      },
    },
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    rollupOptions: {
      input: {
        landing: path.resolve(__dirname, "index.html"),
        app: path.resolve(__dirname, "app/index.html"),
        imprint: path.resolve(__dirname, "imprint/index.html"),
        privacy: path.resolve(__dirname, "privacy/index.html"),
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    globals: true,
    css: true,
    include: ["src/**/*.test.{ts,tsx}"],
    exclude: ["e2e/**", "node_modules/**"],
    coverage: {
      provider: "v8",
      reporter: ["text", "lcov"],
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/**/*.test.{ts,tsx}", "src/test/**"],
    },
  },
});
