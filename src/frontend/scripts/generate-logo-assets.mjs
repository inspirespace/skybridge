#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const frontendDir = path.resolve(__dirname, "..");
const repoRoot = path.resolve(frontendDir, "..", "..");
const publicDir = path.resolve(frontendDir, "public");
const brandDir = path.resolve(publicDir, "brand");

const cliSource = process.argv[2]
  ? path.resolve(process.cwd(), process.argv[2])
  : null;

const sourceCandidates = [
  cliSource,
  path.resolve(repoRoot, "design/logo/skybridge-logo-2048x2048.webp"),
].filter(Boolean);

const sourcePath = sourceCandidates.find((candidate) => fs.existsSync(candidate));

if (!sourcePath) {
  console.error("No source logo found.");
  console.error("Pass a file path or add one of:");
  sourceCandidates.forEach((candidate) => console.error(`- ${candidate}`));
  process.exit(1);
}

const hasMagick = commandExists("magick");
const hasSips = commandExists("sips");

if (!hasMagick && !hasSips) {
  console.error("Missing image tooling. Install ImageMagick (`magick`) or use macOS `sips`.");
  process.exit(1);
}

fs.mkdirSync(brandDir, { recursive: true });

console.log(`Using logo source: ${sourcePath}`);
console.log(`Renderer: ${hasMagick ? "ImageMagick" : "sips"}`);

const squarePngTargets = [
  { size: 48, path: path.resolve(brandDir, "logo-48.png") },
  { size: 64, path: path.resolve(brandDir, "logo-64.png") },
  { size: 96, path: path.resolve(brandDir, "logo-96.png") },
  { size: 128, path: path.resolve(brandDir, "logo-128.png") },
  { size: 180, path: path.resolve(brandDir, "logo-180.png") },
  { size: 192, path: path.resolve(brandDir, "logo-192.png") },
  { size: 256, path: path.resolve(brandDir, "logo-256.png") },
  { size: 512, path: path.resolve(brandDir, "logo-512.png") },
  { size: 1024, path: path.resolve(brandDir, "logo-1024.png") },
  { size: 16, path: path.resolve(publicDir, "favicon-16x16.png") },
  { size: 32, path: path.resolve(publicDir, "favicon-32x32.png") },
  { size: 180, path: path.resolve(publicDir, "apple-touch-icon.png") },
  { size: 192, path: path.resolve(publicDir, "android-chrome-192x192.png") },
  { size: 512, path: path.resolve(publicDir, "android-chrome-512x512.png") },
];

for (const target of squarePngTargets) {
  resizeSquarePng(sourcePath, target.size, target.path, hasMagick);
}

const logoWebpPath = path.resolve(brandDir, "logo-512.webp");
if (hasMagick) {
  run("magick", [
    sourcePath,
    "-resize",
    "512x512",
    "-background",
    "none",
    "-gravity",
    "center",
    "-extent",
    "512x512",
    logoWebpPath,
  ]);
} else {
  run("sips", ["-s", "format", "webp", "-z", "512", "512", sourcePath, "--out", logoWebpPath]);
}

if (hasMagick) {
  run("magick", [
    sourcePath,
    "-background",
    "none",
    "-define",
    "icon:auto-resize=16,32,48",
    path.resolve(publicDir, "favicon.ico"),
  ]);
} else {
  console.warn("Skipping favicon.ico generation (requires ImageMagick `magick`).");
}

const webmanifest = {
  name: "Skybridge",
  short_name: "Skybridge",
  icons: [
    {
      src: "/android-chrome-192x192.png",
      sizes: "192x192",
      type: "image/png",
    },
    {
      src: "/android-chrome-512x512.png",
      sizes: "512x512",
      type: "image/png",
    },
  ],
  theme_color: "#0b1120",
  background_color: "#0b1120",
  display: "standalone",
};

fs.writeFileSync(
  path.resolve(publicDir, "site.webmanifest"),
  `${JSON.stringify(webmanifest, null, 2)}\n`,
  "utf8"
);

console.log("Generated logo assets:");
console.log(`- ${path.relative(frontendDir, brandDir)}/logo-*.png`);
console.log(`- ${path.relative(frontendDir, logoWebpPath)}`);
console.log("- public/favicon-16x16.png");
console.log("- public/favicon-32x32.png");
console.log("- public/apple-touch-icon.png");
console.log("- public/android-chrome-192x192.png");
console.log("- public/android-chrome-512x512.png");
if (hasMagick) {
  console.log("- public/favicon.ico");
}
console.log("- public/site.webmanifest");

function resizeSquarePng(source, size, outputPath, useMagick) {
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  if (useMagick) {
    run("magick", [
      source,
      "-resize",
      `${size}x${size}`,
      "-background",
      "none",
      "-gravity",
      "center",
      "-extent",
      `${size}x${size}`,
      outputPath,
    ]);
    return;
  }
  run("sips", [
    "-s",
    "format",
    "png",
    "-z",
    String(size),
    String(size),
    source,
    "--out",
    outputPath,
  ]);
}

function commandExists(command) {
  const result = spawnSync("bash", ["-lc", `command -v ${command}`], {
    stdio: "ignore",
  });
  return result.status === 0;
}

function run(command, args) {
  const result = spawnSync(command, args, { stdio: "inherit" });
  if (result.status !== 0) {
    console.error(`Command failed: ${command} ${args.join(" ")}`);
    process.exit(result.status ?? 1);
  }
}
