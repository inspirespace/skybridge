# CloudAhoy to FlySto Migration CLI

A Dockerized CLI that migrates flights from CloudAhoy to FlySto. This repo is intentionally minimal so local dev only needs Docker.

## Quickstart

Build the image:

```sh
docker build -t cloudahoy2flysto .
```

Run a dry migration:

```sh
docker run --rm \
  --env-file .env \
  cloudahoy2flysto --dry-run --max-flights 5
```

## Configuration

Create a `.env` file from `.env.example` and fill in your API keys.

Required:
- `CLOUD_AHOY_API_KEY`
- `FLYSTO_API_KEY`

Optional:
- `CLOUD_AHOY_BASE_URL` (default `https://api.cloudahoy.com`)
- `FLYSTO_BASE_URL` (default `https://api.flysto.net`)
- `DRY_RUN` (`true`/`false`)
- `MAX_FLIGHTS` (integer)

CLI options:
- `--state-path` (default `data/migration.db`)
- `--force` to re-upload already migrated flights

## Status

Core CLI wiring and migration workflow are stubbed. The next step is to implement the CloudAhoy and FlySto API calls in:
- `src/cloudahoy/client.py`
- `src/flysto/client.py`

## SaaS Roadmap (draft)

- MVP: single-user CLI + Docker
- Phase 2: hosted worker that runs scheduled migrations per account
- Phase 3: multi-tenant SaaS with billing (per-flight + bundles), admin dashboard, and audit logs

## Development

Local execution without Docker is possible with:

```sh
python -m src.cli --dry-run
```

(No extra dependencies required.)
