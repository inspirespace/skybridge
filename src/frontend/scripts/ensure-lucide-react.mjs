import { existsSync, readFileSync, rmSync } from "node:fs";
import { execSync } from "node:child_process";
import path from "node:path";

const cwd = process.cwd();
const pkgPath = path.join(cwd, "node_modules", "lucide-react", "package.json");
const distFile = path.join(cwd, "node_modules", "lucide-react", "dist", "esm", "lucide-react.js");

if (!existsSync(pkgPath)) {
  process.exit(0);
}

if (existsSync(distFile)) {
  process.exit(0);
}

const pkg = JSON.parse(readFileSync(pkgPath, "utf8"));
const version = pkg.version || "latest";

const packOutput = execSync(`npm pack lucide-react@${version}`, {
  encoding: "utf8",
}).trim();
const tarball = packOutput.split("\n").pop();
if (!tarball) {
  throw new Error("Failed to download lucide-react tarball.");
}

const tempDir = path.join(cwd, ".tmp-lucide-react");
rmSync(tempDir, { recursive: true, force: true });
execSync(`mkdir -p ${tempDir}`);
execSync(`tar -xzf ${tarball} -C ${tempDir}`);
execSync(`rm -rf node_modules/lucide-react/dist`);
execSync(`cp -R ${tempDir}/package/dist node_modules/lucide-react/`);
rmSync(tempDir, { recursive: true, force: true });
execSync(`rm -f ${tarball}`);
