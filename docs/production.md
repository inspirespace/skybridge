# Production essentials

This is a checklist of what production needs, not a step-by-step deployment guide.

## Required Firebase resources
- **Firebase Auth** with Google/Apple/Facebook providers.
- **Firestore** collections:
  - Jobs collection: documents keyed by `job_id`, with `user_id` field indexed.
  - Credentials collection: documents keyed by `token` with TTL configured.
- **Cloud Scheduler** (auto-created by Functions schedule) for daily TTL cleanup.
- **Firebase Storage** bucket for job artifacts (add a lifecycle rule; 7 days suggested).
- **Pub/Sub** topic `skybridge-job-queue` for review/import jobs (Functions 2nd gen trigger; fixed by code, not a runtime toggle).
- **Firebase Hosting** for SPA + API rewrites.
  - `/api/**` rewrites to the `api` function (see `firebase.json`).

## Required backend environment (Firebase Functions)
- `BACKEND_PRODUCTION=true` (enables production security guards)
- `AUTH_MODE=firebase`
- `APP_CHECK_ENFORCE=1` (rejects API requests without valid Firebase App Check token)
- `BACKEND_ENCRYPTION_KEY=<32-byte urlsafe base64 key>`
- `BACKEND_FIRESTORE_ENABLED=1`
- `FIRESTORE_JOBS_COLLECTION=skybridge-jobs`
- `FIRESTORE_CREDENTIALS_COLLECTION=skybridge-credentials`
- `BACKEND_GCS_ENABLED=1`
- `GCS_BUCKET=<bucket>`
- `GCS_PREFIX=jobs`
- `CORS_ALLOW_ORIGINS=<comma separated origins>` (never use `*` in production)

## Optional backend auth overrides
- `AUTH_ISSUER_URL` / `AUTH_AUDIENCE` / `AUTH_JWKS_URL` are optional in Firebase auth mode.
- Defaults are derived from project id (`.firebaserc` locally, runtime metadata in deployed functions).

## Frontend build configuration (Firebase)
- `VITE_API_BASE_URL` is optional; default is same-origin `/api` (recommended with Firebase Hosting rewrites).
- `VITE_AUTH_MODE=firebase` (optional; defaults from `AUTH_MODE`)
- `VITE_FIREBASE_API_KEY=<web api key>`
- `VITE_FIREBASE_APP_ID=<web app id>`
- `VITE_FIREBASE_APP_CHECK_ENABLED=1`
- `VITE_FIREBASE_APP_CHECK_SITE_KEY=<reCAPTCHA v3 site key>`
- `VITE_FIREBASE_PROJECT_ID` / `VITE_FIREBASE_AUTH_DOMAIN` are optional; by default they are derived from `.firebaserc`.
- `VITE_FIRESTORE_JOBS_COLLECTION` and `VITE_RETENTION_DAYS` are optional; defaults come from backend globals (`FIRESTORE_JOBS_COLLECTION`, `BACKEND_RETENTION_DAYS`).
- Deploy preflight (`scripts/firebase-deploy.sh`) fails fast if required Firebase web config is missing in non-emulator Firebase mode and will attempt best-effort auto-resolution from `firebase apps:sdkconfig` (first WEB app in the project).
- Optional: set `FIREBASE_WEB_APP_ID` to force which Firebase WEB app deploy preflight should use for sdkconfig lookup.
- Deploy preflight also validates passwordless email-link sign-in mode (`signIn.email.enabled=true`, `signIn.email.passwordRequired=false`) when `FIREBASE_REQUIRE_EMAIL_LINK_SIGNIN=1` (default).
- Deploy preflight prints a manual Firebase Auth setup overview (sign-in method, email template branding name, authorized domains) and keeps template naming/configuration manual in Firebase Console.
- Firebase Console currently requires Google sign-in provider to be enabled before Auth template "Public-facing name" can be edited.
- Optional: `FIREBASE_AUTH_EMAIL_APP_NAME` sets the friendly app name shown in that setup overview (default `Skybridge`).
- Auth preflight verification uses Google ADC (`GOOGLE_APPLICATION_CREDENTIALS`) and falls back to Firebase CLI login token cache.
## Deploy
- `npm --prefix src/frontend run build`
- `./scripts/firebase-deploy.sh`
Functions source lives in `functions/` and uses `functions/requirements.txt` for dependencies.
- Project id and region defaults come from `.firebaserc` (`projects.default`, `config.region`).
- Default Functions region is `europe-west1`.
- You can override per deploy with `FIREBASE_REGION`.

## Custom domain setup (Firebase Hosting)
Custom domains are configured in the Firebase console (not via `firebase deploy`).

1. Deploy hosting to the target project first:
   - `./scripts/firebase-deploy.sh`
2. Open Firebase Console: Hosting for your project.
3. Click **Add custom domain** and enter your host (for example `skybridge.inspirespace.co`).
4. Add the DNS records Firebase shows (typically TXT for ownership plus CNAME for a subdomain) at your DNS provider.
5. Remove conflicting DNS records for the same host (`A`/`AAAA`/`CNAME` pointing elsewhere).
6. Wait for verification and SSL provisioning to complete (can take up to 24 hours).

Notes:
- Use only one canonical hostname for production and include it in `CORS_ALLOW_ORIGINS`.
- Keep `VITE_API_BASE_URL` as `/api` (or, if overridden, point it at the same Firebase Hosting domain users access).
- Firebase Hosting is global CDN-backed; there is no dedicated EU-only Hosting region setting.

## Storage lifecycle rule
Job artifacts must expire automatically. Apply a lifecycle rule to your storage bucket:
- Example JSON: `docs/firebase-storage-lifecycle.json`
- Apply with gcloud:
  - `gcloud storage buckets update gs://<bucket> --lifecycle-file=docs/firebase-storage-lifecycle.json`

## Production smoke test checklist
- Sign in with each enabled provider (Google/Apple/Facebook/Microsoft) and email link.
- Start a review, confirm progress updates without reload.
- Approve import, confirm progress updates without reload.
- Download artifacts zip from the results screen.
- Delete results; verify job disappears on reload.

## Firebase Auth setup notes
- Enable Google/Apple/Facebook providers in the Firebase console.
- Apple sign-in requires an Apple Developer Program membership and a Services ID.
- Enable Email/Password and Email link (passwordless) in **Authentication -> Sign-in method**.
- Enable Google sign-in provider if you need to edit **Public-facing name** in Auth email templates.
- Set a friendly sender/app name and subject/body copy in **Authentication -> Templates -> Email address sign-in** (for example `Skybridge`).
- Add all continue-url hostnames in **Authentication -> Settings -> Authorized domains** (including custom Hosting domains).

## Security defaults
- Firestore rules only allow authenticated reads of job documents owned by the current UID; all writes are server-only.
- Storage rules deny all client access (artifacts are served via the API).
- API can require Firebase App Check tokens (`APP_CHECK_ENFORCE=1`) to reduce abuse/phishing/billing-risk traffic.
- Rate limiting is applied to `/auth/token` and `/credentials/validate` endpoints (10 requests/minute per IP).
- Internal errors are logged but not exposed to clients.
- Security headers (CSP, X-Frame-Options, X-Content-Type-Options) are configured in `firebase.json`.

## Security environment variables
- `BACKEND_PRODUCTION=true` — **Required in production.** Prevents emulator token bypass regardless of other settings.
- `AUTH_EMULATOR_TRUST_TOKENS` — Never set outside local emulators; the `BACKEND_PRODUCTION` flag blocks it anyway.
- `CORS_ALLOW_ORIGINS` — Set to your production domain(s); a warning is logged if `*` is used in production.
