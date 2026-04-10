# Production essentials

This is a checklist of what production needs, not a step-by-step deployment guide.

## Required Firebase resources
- **Firebase Auth** with Email/Password plus Email link (passwordless) enabled.
- **Firestore** collections:
  - Jobs collection: documents keyed by `job_id`, with `user_id` field indexed.
  - Credentials collection: documents keyed by `token` with TTL configured.
- **Cloud Scheduler** (auto-created by Functions schedule) for daily TTL cleanup.
- **Firebase Storage** bucket for job artifacts (add a lifecycle rule; 7 days suggested).
- **Pub/Sub** topic `skybridge-job-queue` for review/import jobs (Functions 2nd gen trigger; fixed by code, not a runtime toggle).
- **Firebase Hosting** for SPA + API rewrites.
  - `/api/**` rewrites to the `api` function (see `firebase.json`).

## Required backend environment (Firebase Functions)
These values are managed by the shared deploy script. Do not configure them manually in the Firebase console.
- `BACKEND_PRODUCTION=true` (enables production security guards)
- `APP_CHECK_ENFORCE=1` when Firebase App Check is configured for the deployed web app
- `BACKEND_ENCRYPTION_KEY=<32-byte urlsafe base64 key>`
- `FIRESTORE_JOBS_COLLECTION=skybridge-jobs`
- `FIRESTORE_CREDENTIALS_COLLECTION=skybridge-credentials`
- `FIRESTORE_DATABASE_LOCATION=<location>` optional override for first-time deploy auto-creation of the default Firestore database; defaults to `FIREBASE_REGION`
- `FIRESTORE_DATABASE_CREATE_MAX_WAIT_SECONDS=<seconds>` optional override for how long deploy should wait when Firebase temporarily blocks reusing a just-deleted default database id; defaults to `900`
- `GCS_PREFIX=jobs`
- `CORS_ALLOW_ORIGINS=<comma separated origins>` (never use `*` in production)

## Frontend build configuration (Firebase)
- `VITE_API_BASE_URL` is optional; default is same-origin `/api` (recommended with Firebase Hosting rewrites).
- `VITE_FIREBASE_API_KEY=<web api key>`
- `VITE_FIREBASE_APP_ID=<web app id>`
- `VITE_FIREBASE_APP_CHECK_ENABLED=1` when App Check is enabled
- `VITE_FIREBASE_APP_CHECK_SITE_KEY=<reCAPTCHA v3 site key>` when App Check is enabled
- `VITE_FIREBASE_PROJECT_ID` / `VITE_FIREBASE_AUTH_DOMAIN` are optional; by default they are derived from `.firebaserc`.
- `VITE_FIRESTORE_JOBS_COLLECTION` and `VITE_RETENTION_DAYS` are optional; defaults come from backend globals (`FIRESTORE_JOBS_COLLECTION`, `BACKEND_RETENTION_DAYS`).
- `GCS_BUCKET` is optional override only; deploy auto-populates it from the Firebase Web SDK `storageBucket` when available and otherwise verifies/discovers a real project bucket via the Storage API. If the Firebase-configured default bucket is missing, deploy auto-creates it in `FIREBASE_STORAGE_BUCKET_LOCATION` or `FIREBASE_REGION`; when that Firebase-style name is unavailable, deploy falls back to a normal project-owned artifact bucket name and reuses that existing bucket on later deploys by writing it into managed `GCS_BUCKET`. At runtime the backend falls back to `FIREBASE_CONFIG.storageBucket`, then existing project-bucket discovery, then the default Firebase bucket derived from the active project id.
- Deploy preflight (`scripts/firebase-deploy.sh`) fails fast if required Firebase web config is missing in non-emulator Firebase mode and will attempt best-effort auto-resolution from `firebase apps:sdkconfig` (first WEB app in the project).
- Optional: set `FIREBASE_WEB_APP_ID` to force which Firebase WEB app deploy preflight should use for sdkconfig lookup.
- Deploy auto-creates the default Cloud Firestore database `(default)` when it is missing from the target project, because production job state and credential claims are stored there.
- If Firebase reports that `(default)` is temporarily unavailable for recreation after deletion, deploy waits and retries automatically up to `FIRESTORE_DATABASE_CREATE_MAX_WAIT_SECONDS`.
- Deploy preflight also validates passwordless email-link sign-in mode (`signIn.email.enabled=true`, `signIn.email.passwordRequired=false`) when `FIREBASE_REQUIRE_EMAIL_LINK_SIGNIN=1` (default).
- Deploy preflight prints a manual Firebase Auth setup overview (sign-in method, email template branding name, custom sender domain, authorized domains) and keeps template naming/configuration manual in Firebase Console.
- Firebase Console currently requires Google sign-in provider to be enabled before Auth template "Public-facing name" can be edited.
- Optional: `FIREBASE_AUTH_EMAIL_APP_NAME` sets the friendly app name shown in that setup overview (default `Skybridge`).
- Auth preflight verification uses Google ADC (`GOOGLE_APPLICATION_CREDENTIALS`) and falls back to Firebase CLI login token cache.
- Provider flags are managed from `.github/firebase-deploy.defaults.json`.

## Managed deploy inputs
- Required GitHub secrets:
  - `FIREBASE_SERVICE_ACCOUNT`
  - `BACKEND_ENCRYPTION_KEY`
- Optional GitHub secrets:
  - `FIREBASE_WEB_APP_ID` when the Firebase project has more than one web app
  - `FIREBASE_APP_CHECK_SITE_KEY` when App Check is enabled
- Checked-in defaults:
  - `.github/firebase-deploy.defaults.json`
- Generated during deploy:
  - `functions/.env.<project_id>` for app-owned backend settings only (`BACKEND_*`, `APP_CHECK_ENFORCE`, Firestore collection names, CORS)
  - `src/frontend/.env.production`
- Source of truth for project/region defaults:
  - `.firebaserc` plus deploy/runtime `FIREBASE_PROJECT_ID` / `FIREBASE_REGION` exports
## Deploy
- `npm --prefix src/frontend run build`
- `./scripts/firebase-deploy.sh`
Functions source lives in `functions/` and uses `functions/requirements.txt` for dependencies.
The shared deploy script publishes Functions, Hosting, and Firestore configuration from `firebase.json`.
- Project id and region defaults come from `.firebaserc` (`projects.default`, `config.region`).
- Default Functions region is `europe-west1`.
- You can override per deploy with `FIREBASE_REGION`.
- On the first deploy to a project with no Firestore database, the script creates `(default)` automatically. Override the creation location with `FIRESTORE_DATABASE_LOCATION` when needed; otherwise it uses `FIREBASE_REGION`.
- If `(default)` was deleted just before deploy, Firebase can keep the id in a short cooldown window. The deploy script handles that by waiting and retrying instead of failing immediately.

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

## Custom email sender domain (Firebase Auth templates)
Firebase Auth email template sender domains are also configured manually in the Firebase console; `firebase deploy` does not create or verify them.

1. Open Firebase Console: **Authentication -> Templates**.
2. Open **Email address sign-in** (or another Auth email template you use) and click **Customize domain**.
3. Enter a dedicated sender subdomain you control, for example `auth.example.com` or `mail.example.com`.
4. Add the DNS records Firebase shows at your DNS provider.
   - Firebase generates the exact records per project/domain.
   - Expect a mix of TXT records (SPF + Firebase verification) and DKIM CNAME records.
5. Wait for Firebase verification to complete. The Console warns this can take up to 48 hours.
6. After verification, keep that sender domain selected for your Auth email templates.

Notes:
- This is separate from **Authentication -> Settings -> Authorized domains** used for email-link `continueUrl` hosts.
- This is also separate from the Firebase Hosting custom domain for your app site.
- Use a dedicated mail/auth subdomain instead of reusing the same host that serves your app.

## Storage lifecycle rule
Job artifacts must expire automatically. Apply a lifecycle rule to your storage bucket:
- Example JSON: `docs/firebase-storage-lifecycle.json`
- Apply with gcloud:
  - `gcloud storage buckets update gs://<bucket> --lifecycle-file=docs/firebase-storage-lifecycle.json`

## Production smoke test checklist
- Sign in with email link and each provider you explicitly enabled for this deployment.
- Start a review, confirm progress updates without reload.
- Approve import, confirm progress updates without reload.
- Download artifacts zip from the results screen.
- Delete results; verify job disappears on reload.

## Firebase Auth setup notes
- Default deploy config keeps Google/Apple/Facebook/Microsoft disabled; enable only the providers you want to expose.
- Apple sign-in requires an Apple Developer Program membership and a Services ID.
- Enable Email/Password and Email link (passwordless) in **Authentication -> Sign-in method**.
- Enable Google sign-in provider if you need to edit **Public-facing name** in Auth email templates.
- Set a friendly sender/app name and subject/body copy in **Authentication -> Templates -> Email address sign-in** (for example `Skybridge`).
- For branded production emails, also configure **Authentication -> Templates -> Email address sign-in -> Customize domain** and complete the DNS verification in your DNS provider.
- Add all continue-url hostnames in **Authentication -> Settings -> Authorized domains** (including custom Hosting domains).
- Keep the Hosting CSP compatible with Firebase Auth helpers on custom domains: allow the auth iframe domains (`https://*.firebaseapp.com`, `https://*.web.app`) plus Google helper/recaptcha origins used by `/__/auth/*` (`https://apis.google.com`, `https://www.google.com`, `https://www.gstatic.com`).

## Security defaults
- Firestore rules only allow authenticated reads of job documents owned by the current UID; all writes are server-only.
- Storage rules deny all client access (artifacts are served via the API).
- API can require Firebase App Check tokens (`APP_CHECK_ENFORCE=1`) to reduce abuse/phishing/billing-risk traffic.
- Rate limiting is applied to `/credentials/validate` (10 requests/minute per IP).
- Internal errors are logged but not exposed to clients.
- Security headers (CSP, X-Frame-Options, X-Content-Type-Options) are configured in `firebase.json`; the CSP intentionally includes Firebase Auth helper origins required for custom-domain sign-in flows.

## Security environment variables
- `BACKEND_PRODUCTION=true` — **Required in production.** Prevents emulator token bypass regardless of other settings.
- `AUTH_EMULATOR_TRUST_TOKENS` — Never set outside local emulators; the `BACKEND_PRODUCTION` flag blocks it anyway.
- `CORS_ALLOW_ORIGINS` — Set to your production domain(s); a warning is logged if `*` is used in production.
