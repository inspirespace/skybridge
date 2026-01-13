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

Open https://skybridge.localhost and sign in with `demo` / `demo-password`.
On macOS, `.localhost` already resolves to `127.0.0.1`, so no hosts file change is needed. If your OS does not resolve `*.localhost`, add these entries to `/etc/hosts`:

```
127.0.0.1 skybridge.localhost
127.0.0.1 auth.skybridge.localhost
127.0.0.1 storage.skybridge.localhost
```

Local HTTPS is terminated by the Caddy container using the certificates in `docker/https/certs`. Run `mkcert` once to generate them:

```
brew install mkcert
mkcert -install
mkdir -p docker/https/certs
mkcert -cert-file docker/https/certs/skybridge.pem -key-file docker/https/certs/skybridge-key.pem skybridge.localhost auth.skybridge.localhost storage.skybridge.localhost
```

## Docs

- [Documentation index](docs/_index.md)
- [Backend architecture](docs/backend-architecture.md)
- [Codebase overview](docs/codebase-overview.md)
- [Frontend architecture](docs/frontend.md)
- [Testing](docs/testing.md)
- [Production](docs/production.md)
