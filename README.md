# Skybridge

Skybridge migrates CloudAhoy flight history into FlySto.
This repository is 100% AI written.

## CLI guide

The CLI is the interactive, guided migration tool. It walks you through review → approve → import from the terminal.

```sh
./cloudahoy2flysto
```

## Local dev

Prerequisites: Docker + Docker Compose, VS Code (Dev Containers recommended), and the Dev Containers CLI (required for automation).
Install the Dev Containers CLI with:

```
npm install -g @devcontainers/cli
```

```sh
docker compose --profile dev up --build
```
When running from inside the VS Code devcontainer, prefer:
```sh
./scripts/docker-compose.sh --profile dev up -d --build
```

Open https://skybridge.localhost and sign in using the Firebase Auth emulator popup (Google/Apple/Facebook buttons). The emulator UI is available at https://emulator.skybridge.localhost.
The Firebase Functions/Hosting emulators run inside the `firebase-emulator` service.
Emulator import/export data is stored in `.firebase-emulator/exports` (legacy `firebase-export-*` folders are moved there automatically).

To mirror production serving behavior locally (static bundle via Firebase Hosting emulator), use:

```sh
docker compose --profile prod up --build
```
Devcontainer equivalent:
```sh
./scripts/docker-compose.sh --profile prod up -d --build
```
On macOS, `.localhost` already resolves to `127.0.0.1`, so no hosts file change is needed. If your OS does not resolve `*.localhost`, add these entries to `/etc/hosts`:

```
127.0.0.1 skybridge.localhost
127.0.0.1 auth.skybridge.localhost
127.0.0.1 firestore.skybridge.localhost
127.0.0.1 emulator.skybridge.localhost
```

Local HTTPS is terminated by the Caddy container using the certificates in `docker/https/certs`. Run `mkcert` once to generate them:

```
brew install mkcert
mkcert -install
mkdir -p docker/https/certs
mkcert -cert-file docker/https/certs/skybridge.localhost.pem -key-file docker/https/certs/skybridge.localhost-key.pem skybridge.localhost "*.skybridge.localhost"
```

### Logo assets

The frontend logo, favicon set, web manifest icons, and social preview image (`src/frontend/public/social-preview.png`, 1280x640) are generated from `design/logo/skybridge-logo-2048x2048.webp`.
The generator requires ImageMagick (`magick` or `convert`); the devcontainer installs ImageMagick by default.

```sh
npm --prefix src/frontend run logo:generate
```

To use a different source file for one-off generation:

```sh
npm --prefix src/frontend run logo:generate -- path/to/new-logo.webp
```

## Deploy (Firebase)

CI deploys live from `main` via GitHub Actions (`.github/workflows/firebase-deploy.yml`).
Required repository secrets:
- `FIREBASE_SERVICE_ACCOUNT` (service account JSON)

Manual deploy (zero-config: uses `.firebaserc` default project and prompts login if needed):

```sh
./scripts/firebase-deploy.sh
```

Deploy preflight note:
- If `APP_CHECK_ENFORCE=1`, CI deploys fail fast unless frontend App Check config is present (`VITE_FIREBASE_APP_CHECK_ENABLED=1` and `VITE_FIREBASE_APP_CHECK_SITE_KEY`).
- Local deploys print a warning and continue.
- In `firebase` auth mode without emulator, deploy fails fast if frontend Firebase web config is incomplete (`VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_APP_ID`, `VITE_FIREBASE_PROJECT_ID`). The deploy script attempts best-effort auto-resolution from Firebase Web App SDK config.

Clear Firebase resources while keeping the project (zero-config from `.firebaserc`):

```sh
./scripts/firebase-clear-project.sh
```

Frontend dependency install during deploy/devcontainer startup is handled by `scripts/npm-ci-frontend.sh`, which uses npm nested install strategy and one automatic retry to mitigate intermittent npm unpack `ENOENT`/tarball failures.
Deploys are also gated by `npm --prefix src/frontend run test:runtime-smoke`, which fails fast on frontend runtime errors before any remote Firebase changes.

Project id and region come from `.firebaserc` (`projects.default` and `config.region`).
Default Functions region is `europe-west1`.
You can override per-run with `FIREBASE_REGION`.
Production checklist is in `docs/production.md`.

## Docs

- [Documentation index](docs/_index.md)
- [Backend architecture](docs/backend-architecture.md)
- [Codebase overview](docs/codebase-overview.md)
- [Frontend architecture](docs/frontend.md)
- [Testing](docs/testing.md)
- [Production](docs/production.md)

## License

Apache-2.0. See [LICENSE](LICENSE).
