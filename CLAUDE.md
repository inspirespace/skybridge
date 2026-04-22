# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Skybridge migrates CloudAhoy flight history into FlySto. Serverless Python backend (Firebase Functions 2nd gen, Python 3.11), React 19 SPA, Firestore + Cloud Storage + Pub/Sub. There is also a CLI (`./cloudahoy2flysto`) that wraps the same migration logic.

## Commands

### Local Development
```sh
docker compose up --build   # Full stack: Firebase emulators, API, worker, frontend, HTTPS proxy
./scripts/docker-compose.sh --profile dev up -d --build   # From inside the devcontainer
```
Open https://skybridge.localhost (macOS resolves `*.localhost` automatically). Requires mkcert certs in `docker/https/certs/` — see README.

### Backend Tests (Python)
Backend deps live in the project's `.venv` inside the devcontainer — system Python is missing `pydantic`, `pyjwt`, etc.
```sh
devcontainer exec --workspace-folder . bash -c '. .venv/bin/activate && pytest'                    # All tests
devcontainer exec --workspace-folder . bash -c '. .venv/bin/activate && pytest tests/test_foo.py'  # Single file
devcontainer exec --workspace-folder . bash -c '. .venv/bin/activate && pytest -k pattern'         # Name filter
```

### Frontend Tests (Vitest + Playwright)
```sh
devcontainer exec --workspace-folder . npm --prefix src/frontend run test -- --run       # Unit tests (no watch)
devcontainer exec --workspace-folder . npm --prefix src/frontend run test:e2e            # Playwright E2E
```
Frontend tests mock `src/api/client.ts` — when adding/changing an API function, update the `vi.mock(...)` setup in `App.test.tsx` / `App.more.test.tsx` or they will break.

### Build & Lint
```sh
npm --prefix src/frontend run build  # `tsc -b && vite build`
npm --prefix src/frontend run lint   # ESLint (pre-existing errors exist — only fix regressions from your change)
```
The deploy runs the frontend build; TypeScript errors will block deploy.

### Deploy
```sh
./scripts/firebase-deploy.sh   # Zero-config, uses .firebaserc default project
```
CI deploys are manual (`workflow_dispatch`) via `.github/workflows/firebase-deploy.yml`. Both paths call `scripts/firebase-deploy.sh`.

## Architecture

### Two Cloud Run services
Firebase Functions 2nd gen deploys two services behind the scenes:
- **`api`** — HTTP handler (`functions/main.py` → `lambda_handlers.py`). Default timeout 60 s; **any code path that can exceed 60 s must be offloaded** (see Downloads below).
- **`worker`** — Pub/Sub subscriber (`functions/main.py worker()`), `timeout_sec=540`, memory from `BACKEND_WORKER_MEMORY_MB` (code default 256, managed-deploy default 512). All long-running migration work runs here.

### Job lifecycle (Firestore state machine)
Job status progresses: `review_queued` → `review_running` → `review_ready` → (user approves) → `import_queued` → `import_running` → `completed` | `failed`.

- The API writes state and publishes a Pub/Sub message; the worker consumes it and mutates the Firestore job in-place.
- Every long operation ticks `job.heartbeat_at` and `job.updated_at`. The `api` service inspects staleness on every `/jobs/{id}` poll:
  - `QUEUE_STALE_TIMEOUT_SECONDS = 120` for `*_queued` (worker never picked up the message).
  - `RUNNING_STALE_TIMEOUT_SECONDS = 210` for `*_running` (worker stopped making progress).
- On stale detection for an `import_running` job, the API **first** calls `reconcile_completed_import_from_report` — if `import-report.json` shows every flight as `ok`/`skipped`, the job is upgraded to `completed` instead of `failed`. This is the safety net for OOM/SIGKILL during finalization.
- If that doesn't fire, `_auto_retry_stale_job` re-enqueues the job up to `BACKEND_STALE_AUTO_RETRY_LIMIT` (default 2) times, bumping `worker_retry_count`.

### Import finalization (the tricky part)
`JobService.accept_review` (in `src/backend/service.py`) runs a per-flight upload loop, then four serial reconcile passes inside a `_BackgroundHeartbeat` context:
1. `verify_import_report` — resolves FlySto log IDs for each uploaded flight.
2. `reconcile_aircraft_from_report` — ensures aircraft registration is assigned.
3. `reconcile_crew_from_report` — assigns crew annotations.
4. `reconcile_metadata_from_report` — applies remarks/tags via `log-annotations` PUTs.
5. **Second** `reconcile_crew_from_report(..., skip_if_reconciled=False)` — FlySto can clear crew during post-processing, so we reapply after `_maybe_wait_for_processing` drains their queue.

Key patterns here — changing any of these without understanding the full flow will break retries or blow the 256 MiB budget:
- **Shared in-memory payload**: the report is loaded once as `finalization_payload` and threaded through all passes via the `payload=` kwarg. Avoids re-parsing the report 4× and re-writing 4×.
- **Per-item idempotency**: each item gets `aircraft_reconciled` / `crew_reconciled` / `metadata_reconciled` = True after its remote call succeeds. On auto-retry, passes skip already-done items via `skip_if_reconciled`. The second crew pass explicitly opts out.
- **Per-item `heartbeat` callback**: fires at the top of each item loop. Not enough on its own because a single FlySto PUT can block 60 s × retries — so the whole block is also wrapped in `_BackgroundHeartbeat`, a daemon thread that ticks `heartbeat_at` every 30 s regardless of main-thread state.
- **Per-item `progress` callback**: emits a `ProgressEvent` every 5 items (`"Reconciling metadata (23/46)"`) so the UI's "Last update" ticks visibly. Per-item would spam Firestore; per-phase is too coarse.

### 256 MiB worker budget
The worker memory default is 256 MiB by intent (`BACKEND_WORKER_MEMORY_MB`). Several patterns exist specifically to stay under it — don't remove them casually:
- `FlyStoClient.upload_flight` streams the upload zip from a tempfile (via `ZipFile.write`), not in-memory bytes. `_request` seeks seekable bodies on retry.
- `FlyStoClient.trim_caches(keep=8)` is called after each flight iteration to bound `log_cache` / `upload_cache` / `log_source_cache`.
- `service.py _release_detail_exports(detail)` unlinks CloudAhoy export files after they're in object storage, before the next `fetch_flight`.
- Per-item FlySto log lookups inside finalization use `logs_limit=50` (not 250/500) because the persisted log-id short-circuits the scan in the vast majority of cases.

### Download flow
The "Download files" button does NOT build a zip on click — that was hitting the Cloudflare 100 s edge timeout for multi-flight imports. Instead:
1. At the end of `accept_review`, the worker calls `_build_and_upload_artifacts_archive` which streams `artifacts.zip` into GCS at `{prefix}/{user_id}/{job_id}/artifacts.zip`.
2. `download_artifacts_zip_handler`:
   - If `Accept: application/json` (the SPA sends this), returns `{download_url, filename}` pointing at a V4 signed URL — browser downloads directly from GCS.
   - Otherwise 302-redirects to the same signed URL (works for plain anchor clicks).
   - Falls back to streaming bytes through the function if signing is unavailable (IAM missing).
   - Falls back to zipping the local exports dir when there's no object store at all (local dev).

**Required IAM for signed URLs**: the runtime service account needs `roles/iam.serviceAccountTokenCreator` on itself. `scripts/firebase-deploy.sh preflight_compute_sa_signer_role` grants this automatically via the IAM REST API; if the deploy user lacks `roles/resourcemanager.projectIamAdmin`, the preflight prints the exact manual `gcloud` command. See `docs/production.md` "Required IAM — download signed URLs".

### Repository layout
- `src/core/` — framework-agnostic migration code + CLI (`cli.py`, `guided.py`, `migration.py`, `models.py`), CloudAhoy client (`cloudahoy/`), FlySto client (`flysto/`), web session helpers (`web/`).
- `src/backend/` — Firebase-aware layer: HTTP handlers (`lambda_handlers.py`), orchestration (`service.py`), Firestore store (`store.py`), GCS wrapper (`object_store.py`), auth (`auth.py`, `credential_store.py`), Pub/Sub glue (`queue.py`), local mock services (`mocks/`).
- `src/frontend/` — Vite SPA (`src/App.tsx`), API client (`src/api/client.ts`), static pages (landing/privacy/imprint at top-level HTML files).
- `functions/` — Firebase Functions entry points (`main.py` defines both the HTTP function and the Pub/Sub `worker`).
- `tests/` — all backend pytest tests (flat, not nested under `src/`).

### Key entry points when tracing a change
- CLI: `./cloudahoy2flysto` → `src/core/guided.py` / `src/core/cli.py`.
- API: `functions/main.py` routes → `src/backend/lambda_handlers.py` → `JobService` in `src/backend/service.py`.
- Worker: `functions/main.py worker()` → `lambda_handlers._process_queue_payload` → `JobService.generate_review` / `accept_review`.
- Migration logic (callable from both CLI and worker): `src/core/migration.py` + `src/core/flysto/client.py`.

### Tech stack
- **Frontend**: React 19, Vite, TypeScript, Tailwind CSS, Shadcn/ui.
- **Backend**: Firebase Functions 2nd gen (Python 3.11), Firestore, Cloud Storage, Pub/Sub, google-cloud-storage + google-auth.
- **Backend dev/test helpers**: FastAPI is imported for its exception type + the local mock CloudAhoy/FlySto services; it is NOT the production runtime.
- **Testing**: pytest (backend), Vitest + Playwright (frontend).
- **Package management**: uv for Python, npm for frontend.

## Observability

Worker logs during an active import (useful when debugging slow finalization):
```sh
gcloud logging read \
  'resource.type="cloud_run_revision" AND resource.labels.service_name="worker"' \
  --project skybridge-inspirespace \
  --limit 100 --order desc --freshness=10m \
  --format='table(timestamp.date(tz=LOCAL), severity, textPayload)'
```
For a specific job, add `AND textPayload =~ "<job_uuid>"`. In the web UI: https://console.cloud.google.com/logs/query with `resource.labels.service_name="worker"` and the "Stream logs" toggle on.

## Development Guidelines

- Run tests in the devcontainer — Playwright/Node versions and the Python venv are consistent there.
- Use Conventional Commits (`feat:`, `fix:`, `chore:`). Commit messages explain *why* (see recent `git log --oneline` for style — root-cause-first, fix-second).
- PRs follow `CONTRIBUTING.md`: Goal / Scope / Testing / Risk / Screenshots (light + dark for UI). Don't commit screenshot binaries; attach to PR instead.
- Worker memory is 256 MiB by intent — treat it as a hard constraint when touching `src/core/migration.py`, `src/core/flysto/client.py`, or the finalization loop in `service.py`.

## Documentation

Detailed docs in `docs/`:
- `backend-architecture.md` — serverless flow, Firestore/Storage/Pub/Sub design.
- `codebase-overview.md` — fast onboarding map.
- `frontend.md` — frontend entry points, Firebase Auth setup.
- `production.md` — environment variables, Firebase resources, **IAM requirements for signed URLs**, deploy checklist.
- `testing.md` — test commands and devcontainer usage.
