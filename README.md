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

### Fresh clone quickstart (zero-config flow)

Run this once after cloning (or when switching to a new Firebase project):

```sh
npm install -g firebase-tools
firebase login
firebase use --add
```

Notes:
- `firebase use --add` persists your selected project in `.firebaserc` (`projects.default`), which all local scripts/tasks use automatically.
- If you already know the id, you can run `firebase use <project-id>` instead.

```sh
docker compose --profile dev up --build
```
When running from inside the VS Code devcontainer, prefer:
```sh
./scripts/docker-compose.sh --profile dev up -d --build
```

Open https://skybridge.localhost and sign in using passwordless email link flow. The Auth emulator simulates email links locally, and the emulator UI is available at https://emulator.skybridge.localhost.
The Firebase Functions/Hosting emulators run inside the `firebase-emulator` service.
Emulator import/export data is stored in `.firebase-emulator/exports` (legacy `firebase-export-*` folders are moved there automatically).
Auth emulator parity note:
- By default (`FIREBASE_REQUIRE_EMAIL_LINK_SIGNIN=1`), emulator startup enforces the same email-link sign-in mode as production (`signIn.email.enabled=true`, `passwordRequired=false`) via `.firebase-emulator/exports/auth_export/config.json`.

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

CI and local deploy share the same implementation path:
- both invoke `./scripts/firebase-deploy.sh`
- the workflow only provides runtime/tooling and trigger wiring

Manual deploy (zero-config: uses `.firebaserc` default project and prompts login if needed):

```sh
./scripts/firebase-deploy.sh
```

VS Code equivalent:
- Run task: `Firebase: Deploy`

First deploy behavior (out of the box):
- If you are not logged in, the script prompts and runs `firebase login --reauth`.
- If Firebase Auth email-link mode is not enabled, deploy preflight auto-enables it by default.
- If frontend Firebase web config is missing, deploy preflight auto-resolves it from Firebase web app config (and creates a WEB app when required).

Deploy preflight note:
- If `APP_CHECK_ENFORCE=1`, CI deploys fail fast unless frontend App Check config is present (`VITE_FIREBASE_APP_CHECK_ENABLED=1` and `VITE_FIREBASE_APP_CHECK_SITE_KEY`).
- Local deploys print a warning and continue.
- In `firebase` auth mode without emulator, deploy fails fast if frontend Firebase web config is incomplete (`VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_APP_ID`, `VITE_FIREBASE_PROJECT_ID`). The deploy script attempts best-effort auto-resolution from Firebase Web App SDK config.
- If your project has multiple Firebase web apps, set `FIREBASE_WEB_APP_ID` to force which app is used for SDK config resolution during deploy preflight.
- In `firebase` auth mode without emulator, deploy preflight also verifies passwordless email-link provider config (`signIn.email.enabled=true`, `signIn.email.passwordRequired=false`) when `FIREBASE_REQUIRE_EMAIL_LINK_SIGNIN=1` (default). Auto-enable is ON by default (`FIREBASE_AUTO_ENABLE_EMAIL_LINK_SIGNIN=1` when unset) and can be disabled explicitly with `FIREBASE_AUTO_ENABLE_EMAIL_LINK_SIGNIN=0`.
- Deploy preflight also aligns Firebase Auth email branding by setting the Google Cloud project display name (used as `%APP_NAME%` fallback in Auth emails) from `FIREBASE_AUTH_EMAIL_APP_NAME` (defaults to `Skybridge`).
- Deploy preflight also applies a zero-config Firebase Auth email-template branding fallback (default ON via `FIREBASE_AUTO_PATCH_EMAIL_TEMPLATE_BRANDING=1`) so email-link messages use branded copy even when `%APP_NAME%` resolves to a project/site identifier.
- Auth provider verification/auto-enable uses either Google ADC (`GOOGLE_APPLICATION_CREDENTIALS`) or Firebase CLI login token cache (`firebase login`). In CI this is enforced; local runs warn and continue only when neither source is available.
- Deploy preflight also verifies Firebase Auth `authorizedDomains` for email-link `continueUrl` hosts. Custom Hosting domains are enforced as required; default project domains are treated as best-effort (warning-only) because Firebase may allow them implicitly without listing them in API output. Add explicit domains via `FIREBASE_AUTHORIZED_DOMAINS` (comma-separated) when needed.
- Authorized-domain enforcement is strict by default (`FIREBASE_REQUIRE_AUTHORIZED_DOMAINS=1` unless explicitly overridden).

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
