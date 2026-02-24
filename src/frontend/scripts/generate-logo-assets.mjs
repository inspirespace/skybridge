#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const frontendDir = path.resolve(__dirname, "..");
const repoRoot = path.resolve(frontendDir, "..", "..");
const publicDir = path.resolve(frontendDir, "public");
const brandDir = path.resolve(publicDir, "brand");
const SOCIAL_PREVIEW_WIDTH = 1280;
const SOCIAL_PREVIEW_HEIGHT = 640;
const SOCIAL_PREVIEW_SAFE_MARGIN = 40;
const SOCIAL_PREVIEW_CORE_SIZE = SOCIAL_PREVIEW_HEIGHT - SOCIAL_PREVIEW_SAFE_MARGIN;

if (SOCIAL_PREVIEW_CORE_SIZE <= 0) {
  console.error("Social preview safe area leaves no drawable content.");
  process.exit(1);
}

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

const imageMagickCommand = resolveImageMagickCommand();

if (!imageMagickCommand) {
  console.error("Missing ImageMagick tooling. Install ImageMagick (`magick` or `convert`).");
  process.exit(1);
}

fs.mkdirSync(brandDir, { recursive: true });

console.log(`Using logo source: ${sourcePath}`);
console.log(`Renderer: ImageMagick (${imageMagickCommand})`);

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
  resizeSquarePng(sourcePath, target.size, target.path, imageMagickCommand);
}

const logoWebpPath = path.resolve(brandDir, "logo-512.webp");
runImageMagick(imageMagickCommand, [
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

runImageMagick(imageMagickCommand, [
  sourcePath,
  "-background",
  "none",
  "-define",
  "icon:auto-resize=16,32,48",
  path.resolve(publicDir, "favicon.ico"),
]);

const socialPreviewPath = path.resolve(publicDir, "social-preview.png");
generateSocialPreview(sourcePath, socialPreviewPath, imageMagickCommand);

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
console.log("- public/social-preview.png");
console.log("- public/favicon.ico");
console.log("- public/site.webmanifest");

function resizeSquarePng(source, size, outputPath, imageMagickCommand) {
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  runImageMagick(imageMagickCommand, [
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
}

function generateSocialPreview(source, outputPath, imageMagickCommand) {
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  generateSocialPreviewWithMagick(source, outputPath, imageMagickCommand);
}

function generateSocialPreviewWithMagick(source, outputPath, imageMagickCommand) {
  const sideWidth = (SOCIAL_PREVIEW_WIDTH - SOCIAL_PREVIEW_CORE_SIZE) / 2;
  if (!Number.isInteger(sideWidth) || sideWidth < 0) {
    console.error(`Invalid social preview side width: ${sideWidth}`);
    process.exit(1);
  }

  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "skybridge-social-preview-"));
  const centerPath = path.join(tempDir, "center.png");
  const leftPath = path.join(tempDir, "left.png");
  const rightPath = path.join(tempDir, "right.png");
  const middlePath = path.join(tempDir, "middle.png");
  const topPath = path.join(tempDir, "top.png");

  try {
    runImageMagick(imageMagickCommand, [
      source,
      "-resize",
      `${SOCIAL_PREVIEW_CORE_SIZE}x${SOCIAL_PREVIEW_CORE_SIZE}`,
      centerPath,
    ]);
    runImageMagick(imageMagickCommand, [
      centerPath,
      "-crop",
      `1x${SOCIAL_PREVIEW_CORE_SIZE}+0+0`,
      "+repage",
      "-resize",
      `${sideWidth}x${SOCIAL_PREVIEW_CORE_SIZE}!`,
      leftPath,
    ]);
    runImageMagick(imageMagickCommand, [
      centerPath,
      "-crop",
      `1x${SOCIAL_PREVIEW_CORE_SIZE}+${SOCIAL_PREVIEW_CORE_SIZE - 1}+0`,
      "+repage",
      "-resize",
      `${sideWidth}x${SOCIAL_PREVIEW_CORE_SIZE}!`,
      rightPath,
    ]);
    runImageMagick(imageMagickCommand, [leftPath, centerPath, rightPath, "+append", middlePath]);
    runImageMagick(imageMagickCommand, [
      middlePath,
      "-crop",
      `${SOCIAL_PREVIEW_WIDTH}x1+0+0`,
      "+repage",
      "-resize",
      `${SOCIAL_PREVIEW_WIDTH}x${SOCIAL_PREVIEW_SAFE_MARGIN}!`,
      topPath,
    ]);
    runImageMagick(imageMagickCommand, [topPath, middlePath, "-append", outputPath]);
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
}

function resolveImageMagickCommand() {
  if (commandExists("magick")) {
    return "magick";
  }
  if (commandExists("convert")) {
    return "convert";
  }
  return null;
}

function runImageMagick(command, args) {
  run(command, args);
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
