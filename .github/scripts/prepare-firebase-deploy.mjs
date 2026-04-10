import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const workspaceRoot = process.cwd();
const defaultsPath = path.join(workspaceRoot, ".github", "firebase-deploy.defaults.json");
const functionsEnvDir = path.join(workspaceRoot, "functions");
const frontendEnvPath = path.join(workspaceRoot, "src", "frontend", ".env.production");
const deployInputEnv = loadEnvFiles([
  path.join(workspaceRoot, ".env"),
  path.join(functionsEnvDir, ".env"),
]);

const defaults = JSON.parse(fs.readFileSync(defaultsPath, "utf8"));
const projectId = requiredEnv("FIREBASE_PROJECT_ID");
const encryptionKey = requiredEnv("BACKEND_ENCRYPTION_KEY");
const region = envValue("FIREBASE_REGION") || "europe-west1";
const webAppId = envValue("FIREBASE_WEB_APP_ID") || discoverOrCreateWebAppId(projectId);
const sdkConfig = loadWebSdkConfig(projectId, webAppId);
const authProviders = defaults.authProviders || {};
const appCheckSiteKey = (envValue("FIREBASE_APP_CHECK_SITE_KEY") || "").trim();
const appCheckRequested = resolveBoolean(
  envValue("APP_CHECK_ENFORCE"),
  defaults.appCheckEnabled !== false
);
const appCheckEnabled = appCheckRequested && Boolean(appCheckSiteKey);
const appCheckStatus = appCheckEnabled
  ? "enabled"
  : appCheckRequested
    ? "requested by default, inactive (missing FIREBASE_APP_CHECK_SITE_KEY)"
    : "disabled";
const hostingOrigins = new Set([
  `https://${projectId}.web.app`,
  `https://${projectId}.firebaseapp.com`,
]);
const extraOrigins = (envValue("CORS_EXTRA_ORIGINS") || "")
  .split(",")
  .map((value) => value.trim())
  .filter(Boolean);

for (const origin of extraOrigins) {
  hostingOrigins.add(origin);
}

const functionsEnv = {
  BACKEND_PRODUCTION: "true",
  BACKEND_ENCRYPTION_KEY: encryptionKey,
  APP_CHECK_ENFORCE: appCheckEnabled ? "1" : "0",
  FIRESTORE_JOBS_COLLECTION:
    envValue("FIRESTORE_JOBS_COLLECTION") || defaults.firestoreJobsCollection,
  FIRESTORE_CREDENTIALS_COLLECTION:
    envValue("FIRESTORE_CREDENTIALS_COLLECTION") || defaults.firestoreCredentialsCollection,
  BACKEND_RETENTION_DAYS: envValue("BACKEND_RETENTION_DAYS") || defaults.retentionDays,
  CORS_ALLOW_ORIGINS: Array.from(hostingOrigins).join(","),
};

const frontendEnv = {
  VITE_API_BASE_URL: "/api",
  VITE_FIREBASE_API_KEY: requiredConfig(sdkConfig.apiKey, "Firebase web apiKey"),
  VITE_FIREBASE_AUTH_DOMAIN:
    requiredConfig(sdkConfig.authDomain, "Firebase web authDomain"),
  VITE_FIREBASE_PROJECT_ID: projectId,
  VITE_FIREBASE_APP_ID: requiredConfig(sdkConfig.appId, "Firebase web appId"),
  VITE_FIREBASE_USE_EMULATOR: "0",
  VITE_FIREBASE_APP_CHECK_ENABLED: appCheckEnabled ? "1" : "0",
  VITE_FIREBASE_ENABLE_GOOGLE: authProviders.google ? "1" : "0",
  VITE_FIREBASE_ENABLE_APPLE: authProviders.apple ? "1" : "0",
  VITE_FIREBASE_ENABLE_FACEBOOK: authProviders.facebook ? "1" : "0",
  VITE_FIREBASE_ENABLE_MICROSOFT: authProviders.microsoft ? "1" : "0",
  VITE_FIREBASE_ENABLE_GUEST: authProviders.guest ? "1" : "0",
  VITE_FIRESTORE_JOBS_COLLECTION: functionsEnv.FIRESTORE_JOBS_COLLECTION,
  VITE_RETENTION_DAYS: functionsEnv.BACKEND_RETENTION_DAYS,
};

if (appCheckEnabled) {
  frontendEnv.VITE_FIREBASE_APP_CHECK_SITE_KEY = appCheckSiteKey;
}

writeEnvFile(path.join(functionsEnvDir, `.env.${projectId}`), functionsEnv);
writeEnvFile(frontendEnvPath, frontendEnv);

console.log(`Prepared Firebase deploy configuration:
  Project: ${projectId}
  Region: ${region}
  Web app: ${webAppId}
  Functions env: ${path.join("functions", `.env.${projectId}`)}
  Frontend env: ${path.join("src", "frontend", ".env.production")}
  App Check: ${appCheckStatus}`);

function requiredEnv(name) {
  const value = envValue(name);
  if (!value) {
    throw new Error(
      `Missing required environment variable: ${name} (checked process env, .env, functions/.env)`
    );
  }
  return value;
}

function envValue(name) {
  return process.env[name] ?? deployInputEnv[name] ?? "";
}

function requiredConfig(value, label) {
  if (!value) {
    throw new Error(`Missing ${label} in Firebase web app config`);
  }
  return value;
}

function resolveBoolean(rawValue, defaultValue) {
  if (rawValue == null || rawValue === "") {
    return Boolean(defaultValue);
  }
  return ["1", "true", "yes", "on"].includes(String(rawValue).trim().toLowerCase());
}

function loadEnvFiles(filePaths) {
  const values = {};
  for (const filePath of filePaths) {
    if (!fs.existsSync(filePath)) {
      continue;
    }
    Object.assign(values, parseEnvFile(fs.readFileSync(filePath, "utf8")));
  }
  return values;
}

function parseEnvFile(source) {
  const values = {};
  for (const rawLine of String(source).split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) {
      continue;
    }

    const normalized = line.startsWith("export ") ? line.slice(7).trim() : line;
    const separatorIndex = normalized.indexOf("=");
    if (separatorIndex <= 0) {
      continue;
    }

    const key = normalized.slice(0, separatorIndex).trim();
    let value = normalized.slice(separatorIndex + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }

    values[key] = value;
  }
  return values;
}

function discoverOrCreateWebAppId(project) {
  const payload = firebaseJson(["apps:list", "WEB", "--project", project, "--json"]);
  const apps = extractAppEntries(payload);

  if (apps.length === 1) {
    return apps[0].appId || apps[0].app_id;
  }

  if (apps.length === 0) {
    const created = firebaseJson([
      "apps:create",
      "WEB",
      `${project}-web`,
      "--project",
      project,
      "--json",
    ]);
    const createdApps = extractAppEntries(created);
    const createdId = createdApps[0]?.appId || createdApps[0]?.app_id;
    if (createdId) {
      return createdId;
    }
    throw new Error("No Firebase WEB app found and automatic creation failed.");
  }

  throw new Error(
    "Multiple Firebase WEB apps found. Set FIREBASE_WEB_APP_ID so deploy config stays deterministic."
  );
}

function extractAppEntries(payload) {
  const queue = [payload];
  const apps = [];

  while (queue.length > 0) {
    const current = queue.shift();
    if (!current) continue;
    if (Array.isArray(current)) {
      queue.push(...current);
      continue;
    }
    if (typeof current !== "object") {
      continue;
    }
    const appId = current.appId || current.app_id;
    if (typeof appId === "string" && appId) {
      apps.push(current);
      continue;
    }
    queue.push(...Object.values(current));
  }

  return apps;
}

function loadWebSdkConfig(project, appId) {
  const payload = firebaseJson([
    "apps:sdkconfig",
    "WEB",
    appId,
    "--project",
    project,
    "--json",
  ]);

  if (payload.result?.sdkConfig) return payload.result.sdkConfig;
  if (payload.sdkConfig) return payload.sdkConfig;
  if (payload.result?.fileContents) return parseSdkConfigSnippet(payload.result.fileContents);
  if (payload.fileContents) return parseSdkConfigSnippet(payload.fileContents);
  if (payload.result?.apiKey) return payload.result;
  if (payload.apiKey) return payload;

  throw new Error("Unable to read Firebase WEB sdk config from firebase CLI output.");
}

function parseSdkConfigSnippet(fileContents) {
  const match = String(fileContents).match(/\{[\s\S]*\}/);
  if (!match) {
    throw new Error("Unable to parse Firebase WEB sdk config snippet.");
  }

  const normalized = match[0]
    .replace(/(\s*)([A-Za-z0-9_]+)\s*:/g, '$1"$2":')
    .replace(/'/g, '"')
    .replace(/,\s*}/g, "}");

  return JSON.parse(normalized);
}

function firebaseJson(args) {
  const stdout = execFileSync("firebase", args, {
    cwd: workspaceRoot,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  });
  return JSON.parse(stdout);
}

function writeEnvFile(targetPath, values) {
  const body = Object.entries(values)
    .map(([key, value]) => `${key}=${escapeEnvValue(value)}`)
    .join("\n");
  fs.writeFileSync(targetPath, `${body}\n`, "utf8");
}

function escapeEnvValue(value) {
  return String(value).replace(/\n/g, "\\n");
}
