#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="$ROOT_DIR/infra/terraform/lambda"

mkdir -p "$OUTPUT_DIR"

python - <<'PY'
import zipfile
from pathlib import Path

root = Path.cwd()
output = root / "dist" / "backend-handlers.zip"

handlers = root / "src" / "backend" / "lambda_handlers.py"

output.parent.mkdir(parents=True, exist_ok=True)

with zipfile.ZipFile(output, "w") as archive:
    archive.write(handlers, "lambda_handlers.py")
PY

echo "Wrote $ROOT_DIR/dist/backend-handlers.zip"
