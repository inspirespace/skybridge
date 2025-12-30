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

backend_dir = root / "src" / "backend"

output.parent.mkdir(parents=True, exist_ok=True)

with zipfile.ZipFile(output, "w") as archive:
    for path in backend_dir.rglob("*"):
        if path.is_file():
            archive.write(path, path.relative_to(root / "src"))
    archive.writestr(
        "lambda_handlers.py",
        """from backend.lambda_handlers import (
    accept_review_handler,
    create_job_handler,
    get_job_handler,
    list_artifacts_handler,
    list_jobs_handler,
    read_artifact_handler,
)
""",
    )
PY

echo "Wrote $ROOT_DIR/dist/backend-handlers.zip"
