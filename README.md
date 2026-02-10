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
docker compose up --build
```

Open https://skybridge.localhost and sign in using the Firebase Auth emulator popup (Google/Apple/Facebook buttons). The emulator UI is available at https://emulator.skybridge.localhost.
The Firebase Functions/Hosting emulators run inside the `firebase-emulator` service.
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

The frontend logo, favicon set, and manifest icons are generated from `design/logo/skybridge-logo-2048x2048.webp`.
The generator requires either ImageMagick (`magick`) or macOS `sips`.

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
- `FIREBASE_PROJECT_ID` (Firebase project id)
- `FIREBASE_SERVICE_ACCOUNT` (service account JSON)

Manual deploy:

```sh
npm --prefix src/frontend run build
firebase deploy --only functions,hosting --project <project_id>
```

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
