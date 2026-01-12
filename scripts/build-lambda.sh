#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="$ROOT_DIR/infra/terraform/lambda"
BUILD_DIR="$ROOT_DIR/dist/lambda-build"

mkdir -p "$OUTPUT_DIR"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# Install only the minimal runtime dependencies needed for Lambda handlers.
python -m pip install --upgrade --target "$BUILD_DIR" \
  "requests==2.32.5" \
  "pyjwt==2.9.0" \
  "cryptography==42.0.7" \
  "pydantic==2.11.1"

python - <<'PY'
import zipfile
from pathlib import Path
import shutil

root = Path.cwd()
output = root / "dist" / "backend-handlers.zip"
build_dir = root / "dist" / "lambda-build"

backend_dir = root / "src" / "backend"

output.parent.mkdir(parents=True, exist_ok=True)

# Copy backend sources into build dir
dest_backend = build_dir / "backend"
if dest_backend.exists():
    shutil.rmtree(dest_backend)
shutil.copytree(backend_dir, dest_backend)

with zipfile.ZipFile(output, "w") as archive:
    for path in build_dir.rglob("*"):
        if path.is_file():
            archive.write(path, path.relative_to(build_dir))
    archive.writestr(
        "lambda_handlers.py",
        """from backend.lambda_handlers import (
    accept_review_handler,
    create_job_handler,
    get_job_handler,
    list_artifacts_handler,
    list_jobs_handler,
    read_artifact_handler,
    sqs_worker_handler,
    auth_token_handler,
    download_artifacts_zip_handler,
    validate_credentials_handler,
)
""",
    )
PY

cp "$ROOT_DIR/dist/backend-handlers.zip" "$OUTPUT_DIR/backend-handlers.zip"

echo "Wrote $ROOT_DIR/dist/backend-handlers.zip"
