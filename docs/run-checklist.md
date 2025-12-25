# Skybridge import run checklist

Use this checklist for every import run to keep artifacts consistent and ensure FlySto data is complete.

## Pre-run
1) Confirm FlySto is cleared (flights and unknown aircraft).
2) Ensure `.env` is present and up to date.
3) Pick a new run id.

```
RUN_ID=$(date -u +%Y%m%dT%H%M%SZ)
```

## Run
1) Build the image (only needed if you changed code).

```
DOCKER_BUILDKIT=0 docker build -t skybridge .
```

2) Create review manifest.

```
RUN_ID=$RUN_ID docker run --rm --name skybridge-review \
  -e RUN_ID=$RUN_ID \
  --env-file .env \
  -v "$PWD":/app -w /app \
  skybridge --review --max-flights 50
```

3) Import all flights.

```
RUN_ID=$RUN_ID docker run --rm --name skybridge \
  -e RUN_ID=$RUN_ID \
  --env-file .env \
  -v "$PWD":/app -w /app \
  skybridge --approve-import --review-id <REVIEW_ID> \
  --max-flights 50 --force --wait-for-processing
```

## Post-run verification
1) Verify local artifacts and report summary.

```
./scripts/verify-run.sh $RUN_ID
```

2) Optional: re-verify against FlySto (requires valid FlySto credentials).

```
ONLINE_VERIFY=1 ./scripts/verify-run.sh $RUN_ID
```

## Expected artifacts
- `data/runs/<RUN_ID>/review.json`
- `data/runs/<RUN_ID>/import_report.json`
- `data/runs/<RUN_ID>/cloudahoy_exports/` (3 files per flight: `.gpx`, `.csv`, `.meta.json`)
- `data/runs/<RUN_ID>/docker.log`
- `data/runs/<RUN_ID>/migration.db`
