# CloudAhoy to FlySto Migration CLI

A Dockerized CLI that migrates flights from CloudAhoy to FlySto. This repo is intentionally minimal so local dev only needs Docker.

## Quickstart

Build the image:

```sh
docker build -t cloudahoy2flysto .
```

Run a review (generates CSV exports from `flt.points`):

```sh
docker run --rm \
  --env-file .env \
  cloudahoy2flysto --mode hybrid --review --max-flights 5

docker run --rm \
  --env-file .env \
  cloudahoy2flysto --mode hybrid --approve-import --max-flights 5
```

Or use the wrapper script:

```sh
./scripts/run-review.sh
```

## Configuration

Create a `.env` file from `.env.example` and fill in your API keys.

Required:
- `CLOUD_AHOY_API_KEY`
- `FLYSTO_API_KEY`

Optional:
- `CLOUD_AHOY_BASE_URL` (default `https://www.cloudahoy.com/api`)
- `CLOUD_AHOY_WEB_BASE_URL` (default `https://www.cloudahoy.com`)
- `CLOUD_AHOY_EMAIL` / `CLOUD_AHOY_PASSWORD` (web mode login)
- `CLOUD_AHOY_FLIGHTS_URL` (direct flights page URL if auto-detect fails)
- `CLOUD_AHOY_EXPORT_URL_TEMPLATE` (example: `https://www.cloudahoy.com/api/export.cgi?id={flight_id}`)
- `FLYSTO_BASE_URL` (default `https://api.flysto.net`)
- `FLYSTO_WEB_BASE_URL` (default `https://www.flysto.net`)
- `FLYSTO_EMAIL` / `FLYSTO_PASSWORD` (web mode login)
- `FLYSTO_UPLOAD_URL` (direct upload page URL if auto-detect fails)
- `MODE` (`web`, `hybrid`, or `api`, default `web`)
- `BROWSER_HEADLESS` (`true`/`false`)
- `DRY_RUN` (`true`/`false`)
- `MAX_FLIGHTS` (integer)

CLI options:
- `--state-path` (default `data/migration.db`)
- `--force` to re-upload already migrated flights
- `--mode` to select `web` or `api`
- `--headful` to run browser non-headless
- `--cloudahoy-state-path` / `--flysto-state-path` for browser storage state
- `--exports-dir` for downloaded CloudAhoy exports
- `--discover` to run endpoint discovery into `data/discovery/discovery.json`
- `--discovery-dir` to control discovery output directory
- `--discovery-upload-file` to use a specific file for FlySto upload discovery

## Status

Hybrid mode uses CloudAhoy JSON APIs for full-flight data and FlySto web upload. API-only mode is not implemented for FlySto yet.

## Web Automation Notes

The web mode uses Playwright to log in and export/upload flights when no official APIs are available. Provide `CLOUD_AHOY_EXPORT_URL_TEMPLATE` and `FLYSTO_UPLOAD_URL` to bypass UI discovery if needed. For interactive debugging, run with `--headful` and watch the browser session. FlySto uploads are driven through the `Load logs` → `Browse files` flow on `/logs`. The CloudAhoy flights list uses the web UI and auto-clicks `Load more` to fetch additional pages when available.

Review manifests include a `points_schema` and `points_preview` derived from `flt.points` so you can validate the trajectory fields before import.


Discovery mode will attempt to log in and collect endpoint hints; it writes a sanitized JSON summary to `data/discovery/discovery.json`.

## SaaS Roadmap (draft)

- MVP: single-user CLI + Docker
- Phase 2: hosted worker that runs scheduled migrations per account
- Phase 3: multi-tenant SaaS with billing (per-flight + bundles), admin dashboard, and audit logs

## Development

Local execution without Docker is possible with:

```sh
python -m src.cli --review
python -m src.cli --approve-import
```

(No extra dependencies required.)
