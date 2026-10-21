# Local development

Prerequisites: Docker + Docker Compose, VS Code (Dev Containers recommended), and the Dev Containers CLI (required for automation):

```sh
npm install -g @devcontainers/cli
```

## Fresh clone quickstart (zero-config flow)

Run this once after cloning (or when switching to a new Firebase project):

```sh
npm install -g firebase-tools
firebase login
firebase use --add
```

- `firebase use --add` persists your selected project in `.firebaserc` (`projects.default`), which all local scripts/tasks use automatically.
- If you already know the id, you can run `firebase use <project-id>` instead.

### Local HTTPS certificates

Local HTTPS is terminated by the Caddy container using the certificates in `docker/https/certs`. Run `mkcert` once to generate them:

```sh
brew install mkcert
mkcert -install
mkdir -p docker/https/certs
mkcert -cert-file docker/https/certs/skybridge.localhost.pem -key-file docker/https/certs/skybridge.localhost-key.pem skybridge.localhost "*.skybridge.localhost"
```

On macOS, `.localhost` already resolves to `127.0.0.1`, so no hosts file change is needed. If your OS does not resolve `*.localhost`, add these entries to `/etc/hosts`:

```
127.0.0.1 skybridge.localhost
127.0.0.1 auth.skybridge.localhost
127.0.0.1 firestore.skybridge.localhost
127.0.0.1 emulator.skybridge.localhost
```

## Running the stack

```sh
docker compose --profile dev up --build
```

When running from inside the VS Code devcontainer, prefer:

```sh
./scripts/docker-compose.sh --profile dev up -d --build
```

Open https://skybridge.localhost and sign in using the passwordless email-link flow. The Auth emulator simulates email links locally, and the emulator UI is available at https://emulator.skybridge.localhost.

- The Firebase Functions/Hosting emulators run inside the `firebase-emulator` service.
- Emulator import/export data is stored in `.firebase-emulator/exports` (legacy `firebase-export-*` folders are moved there automatically).
- Backend runtime path is Firebase Functions only (`functions/main.py`) for both production and local emulator runs.
- `mock-cloudahoy` and `mock-flysto` are dev-only helper services used by mock mode (`DEV_USE_MOCKS=1`) and are not production runtime components.

Auth emulator parity: by default (`FIREBASE_REQUIRE_EMAIL_LINK_SIGNIN=1`), emulator startup enforces the same email-link sign-in mode as production (`signIn.email.enabled=true`, `passwordRequired=false`) via `.firebase-emulator/exports/auth_export/config.json`.

### Production-like local profile

To mirror production serving behavior locally (static bundle via Firebase Hosting emulator), use:

```sh
docker compose --profile prod up --build
```

Devcontainer equivalent:

```sh
./scripts/docker-compose.sh --profile prod up -d --build
```

This remains emulator-backed for Firebase services. It exercises the production-like Hosting/Functions path locally, but it will not surface missing remote Firebase resources such as an uncreated production Firestore database.

## Logo assets

The frontend logo, favicon set, web manifest icons, and social preview image (`src/frontend/public/social-preview.png`, 1280x640) are generated from `design/logo/skybridge-logo-2048x2048.webp`.
The generator requires ImageMagick (`magick` or `convert`); the devcontainer installs ImageMagick by default.

```sh
npm --prefix src/frontend run logo:generate
```

To use a different source file for one-off generation:

```sh
npm --prefix src/frontend run logo:generate -- path/to/new-logo.webp
```
