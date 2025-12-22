# CloudAhoy to FlySto Migration CLI

![Skybridge logo](assets/logo.svg)

A Dockerized CLI that migrates flights from CloudAhoy to FlySto. This repo is intentionally minimal so local dev only needs Docker.

## Quickstart

Build the image:

```sh
docker build -t skybridge .
```

Run a review (generates GPX exports from `flt.points` and retains CSV sidecars):

```sh
docker run --rm \
  --env-file .env \
  skybridge --review --max-flights 5

docker run --rm \
  --env-file .env \
  skybridge --approve-import --max-flights 5
```

Or use the wrapper scripts:

```sh
./scripts/run-review.sh
./scripts/run-import.sh
./scripts/run.sh --approve-import --max-flights 10
```

## Configuration

Create a `.env` file from `.env.example` and fill in your credentials. The CLI infers upload URLs and API version automatically.

Optional:
- `CLOUD_AHOY_BASE_URL` (default `https://www.cloudahoy.com/api`)
- `CLOUD_AHOY_WEB_BASE_URL` (default `https://www.cloudahoy.com`)
- `CLOUD_AHOY_EMAIL` / `CLOUD_AHOY_PASSWORD` (web mode login)
- `CLOUD_AHOY_FLIGHTS_URL` (direct flights page URL if auto-detect fails)
- `CLOUD_AHOY_EXPORT_URL_TEMPLATE` (example: `https://www.cloudahoy.com/api/export.cgi?id={flight_id}`)
- `FLYSTO_BASE_URL` (default `https://www.flysto.net`)
- `FLYSTO_WEB_BASE_URL` (default `https://www.flysto.net`)
- `FLYSTO_EMAIL` / `FLYSTO_PASSWORD` (web mode login)
- `FLYSTO_UPLOAD_URL` (direct upload page URL if auto-detect fails)
- `FLYSTO_SESSION_COOKIE` (optional API auth cookie value for `USER_SESSION`; if omitted, email/password login is used)
- `FLYSTO_LOG_UPLOAD_URL` (optional override for API endpoint; defaults to `https://www.flysto.net/api/log-upload`)
- `FLYSTO_INCLUDE_METADATA` (`true`/`false`, attach metadata when using API)
- `FLYSTO_API_VERSION` (optional; inferred from FlySto bundle if omitted)
- `MODE` (`auto`, `web`, `hybrid`, or `api`, default `auto`; auto uses API only)
- `BROWSER_HEADLESS` (`true`/`false`)
- `DRY_RUN` (`true`/`false`)
- `MAX_FLIGHTS` (integer)
Note: `CLOUD_AHOY_API_KEY` and `FLYSTO_API_KEY` are not used yet.

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

The default path uses CloudAhoy JSON APIs for full-flight data and FlySto API upload.

## Web Automation Notes

The web mode uses Playwright to log in and export/upload flights when no official APIs are available. Provide `CLOUD_AHOY_EXPORT_URL_TEMPLATE` and `FLYSTO_UPLOAD_URL` to bypass UI discovery if needed. For interactive debugging, run with `--headful` and watch the browser session. FlySto uploads are driven through the `Load logs` → `Browse files` flow on `/logs`. The CloudAhoy flights list uses the web UI and auto-clicks `Load more` to fetch additional pages when available. Auto mode does not fall back to web automation.

Review manifests include a `points_schema` and `points_preview` derived from `flt.points` so you can validate the trajectory fields before import.
Approved imports require a review ID; `./scripts/run-import.sh` reads it from `data/review.json` automatically.


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
