# Skybridge

A Dockerized CLI that migrates flights from CloudAhoy to FlySto. This repo is intentionally minimal so local dev only needs Docker.

## Quickstart

Build the image:

```sh
docker build -t skybridge .
```

Run a review (generates GPX exports from `flt.points`, retains CSV sidecars, and creates FlySto aircraft by tail number):

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
./scripts/run.sh --approve-import --review-id <id> --wait-for-processing
./scripts/run.sh --reconcile-import-report --wait-for-processing
./scripts/verify-run.sh <RUN_ID>
./cloudahoy2flysto
```

## Configuration

Create a `.env` file from `.env.example` and fill in your credentials. The CLI infers upload URLs and API version automatically.

Optional:
- `CLOUD_AHOY_BASE_URL` (default `https://www.cloudahoy.com/api`)
- `CLOUD_AHOY_WEB_BASE_URL` (default `https://www.cloudahoy.com`)
- `CLOUD_AHOY_EMAIL` / `CLOUD_AHOY_PASSWORD` (web mode login)
- `CLOUD_AHOY_FLIGHTS_URL` (direct flights page URL if auto-detect fails)
- `CLOUD_AHOY_EXPORT_URL_TEMPLATE` (example: `https://www.cloudahoy.com/api/export.cgi?id={flight_id}`)
- `CLOUD_AHOY_EXPORT_FORMAT` (`gpx`, `foreflight`, `flightradar24`, `mvp50`, `g3x`, or `g1000`, default `g3x`)
- `CLOUD_AHOY_EXPORT_FORMATS` (comma-separated list, default `g3x,gpx`; first supported format is used for upload)
- `FLYSTO_BASE_URL` (default `https://www.flysto.net`)
- `FLYSTO_WEB_BASE_URL` (default `https://www.flysto.net`)
- `FLYSTO_EMAIL` / `FLYSTO_PASSWORD` (web mode login)
- `FLYSTO_UPLOAD_URL` (direct upload page URL if auto-detect fails)
- `FLYSTO_SESSION_COOKIE` (optional API auth cookie value for `USER_SESSION`; if omitted, email/password login is used)
- `FLYSTO_LOG_UPLOAD_URL` (optional override for API endpoint; defaults to `https://www.flysto.net/api/log-upload`)
- `FLYSTO_INCLUDE_METADATA` (`true`/`false`, attach metadata when using API)
- `FLYSTO_API_VERSION` (optional; inferred from FlySto bundle if omitted)
- `FLYSTO_MIN_REQUEST_INTERVAL` (optional seconds between FlySto API calls; default `0.1`)
- `FLYSTO_MAX_REQUEST_RETRIES` (optional FlySto request retries; default `2`)

### Run Artifacts
When using `./scripts/run.sh`, artifacts are grouped under `data/runs/<RUN_ID>/`:
- `review.json`
- `import_report.json`
- `cloudahoy_exports/`
- `migration.db`
- `docker.log`
`./scripts/run.sh` now runs the container detached and streams logs into `docker.log` to avoid truncation on long runs.

You can override the defaults with `RUN_ID`, `RUNS_DIR`, `REVIEW_PATH`, `IMPORT_REPORT`, `EXPORTS_DIR`, `STATE_PATH`, and `LOG_PATH`.
- `MODE` (`auto`, `web`, `hybrid`, or `api`, default `auto`; auto uses API only)
- `BROWSER_HEADLESS` (`true`/`false`)
- `DRY_RUN` (`true`/`false`)
- `MAX_FLIGHTS` (integer)
Note: `CLOUD_AHOY_API_KEY` and `FLYSTO_API_KEY` are not used yet.

CLI options:
- `--state-path` (default `data/migration.db`)
- `--force` to re-upload already migrated flights
- `--start-date` / `--end-date` to import a specific UTC date or range (YYYY-MM-DD or ISO8601)
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

## Run Checklist

See `docs/run-checklist.md` for the step-by-step run procedure and verification steps.


Discovery mode is only needed when the web apps change or an endpoint breaks; it logs in and records endpoint hints to `data/discovery/discovery.json`.

## Backend Roadmap (draft)

- MVP: single-user CLI + Docker
- Phase 2: hosted worker that runs scheduled migrations per account
- Phase 3: multi-tenant backend with billing (per-flight + bundles), admin dashboard, and audit logs

## Development

Preferred devcontainer usage without the devcontainer CLI:

```sh
docker build --target base -t skybridge-dev .
docker run --rm -it \
  -v "$PWD":/workspaces/skybridge \
  -w /workspaces/skybridge \
  skybridge-dev pytest
```

Devcontainer notes:
- Shell history is persisted in a named Docker volume (`/var/devcontainer/history`).
- Codex login is persisted via a named volume at `/home/vscode/.codex` and port 1455 is forwarded for the callback.
- Python deps are managed via `uv` (`pyproject.toml` + `uv.lock`), dev deps via `--extra dev`.
- Oh My Zsh includes `zsh-autosuggestions` by default for shell hinting.

Install the guided command globally (default `/usr/local/bin`):

```sh
make install
make uninstall
```

Override the install path:

```sh
make install PREFIX=$HOME/.local
```

Local execution without Docker is possible with:

```sh
python -m src.core.cli --review
python -m src.core.cli --approve-import
python -m src.core.cli --approve-import --review-id <id> --wait-for-processing
python -m src.core.cli --reconcile-import-report --wait-for-processing
```

Development runs should use the devcontainer scripts (`./scripts/run*.sh`) to guarantee required dependencies (like `rich`) and browser tooling. Local execution is best reserved for one-off debugging.

## Backend dev web (local dev)

Run the dev web locally (API + UI):

```sh
./scripts/run-backend-dev.sh
```

Then open http://localhost:8000 to use the dev web UI.

Local auth uses OIDC (Keycloak). Start Keycloak with Docker Compose or a separate container and sign in with the dev credentials:
- user: `demo`
- password: `demo-password`

Optional dev convenience: set `DEV_PREFILL_CREDENTIALS=1` and provide
`CLOUD_AHOY_EMAIL`, `CLOUD_AHOY_PASSWORD`, `FLYSTO_EMAIL`, `FLYSTO_PASSWORD`
to prefill the web UI inputs.

For a standalone Keycloak instance:

```sh
docker compose up --build keycloak
```

### HTTPS dev setup (recommended on macOS)

This uses Caddy + mkcert for trusted local HTTPS.

```sh
brew install mkcert
./scripts/setup-dev-https.sh
docker compose up --build
```

Open:
- https://skybridge.localhost (UI + API)
- https://auth.skybridge.localhost (Keycloak)
- https://storage.skybridge.localhost (MinIO S3 API)


### Docker Compose (API + worker + local data stores)

```sh
docker compose up --build
```

Services:
- `api` (FastAPI + UI) on http://localhost:8000
- `worker` (dev worker loop)
- `dynamodb` (local) on http://localhost:8001
- `minio` (S3-compatible) behind Caddy at https://storage.skybridge.localhost
- `keycloak` (OIDC dev auth) on http://localhost:8080
- `caddy` (HTTPS proxy) on https://skybridge.localhost, https://auth.skybridge.localhost, and https://storage.skybridge.localhost

The dev stack runs review/import via the worker (API queues jobs and issues one-time credential claims).

Test the API:

```sh
TOKEN="<paste access_token from Keycloak>"
curl -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"credentials":{"cloudahoy_username":"user","cloudahoy_password":"pass","flysto_username":"user","flysto_password":"pass"}}' \
  http://localhost:8000/jobs
```

Stop the stack:

```sh
docker compose down -v
```

Create a job and accept the review (requires an `Authorization` bearer token):

```sh
TOKEN="<paste access_token from Keycloak>"
curl -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \\
  -d '{"credentials":{"cloudahoy_username":"user","cloudahoy_password":"pass","flysto_username":"user","flysto_password":"pass"}}' \\
  http://localhost:8000/jobs

curl -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \\
  -d '{"credentials":{"cloudahoy_username":"user","cloudahoy_password":"pass","flysto_username":"user","flysto_password":"pass"}}' \\
  http://localhost:8000/jobs/<job_id>/review/accept
```

Artifacts are stored under `data/backend/jobs/<job_id>/` while the dev web uses local storage.
