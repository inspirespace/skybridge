import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import fs from "fs";
import path from "path";

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
