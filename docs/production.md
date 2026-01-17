# Production essentials

This is a checklist of what production needs, not a step-by-step deployment guide.

## Required Firebase resources
- **Firebase Auth** with Google/Apple/Facebook providers.
- **Firestore** collections:
  - Jobs collection: documents keyed by `job_id`, with `user_id` field indexed.
  - Credentials collection: documents keyed by `token` with TTL configured.
- **Cloud Scheduler** (auto-created by Functions schedule) for daily TTL cleanup.
- **Firebase Storage** bucket for job artifacts (add a lifecycle rule; 7 days suggested).
- **Pub/Sub** topic for review/import jobs (Functions 2nd gen trigger).
- **Firebase Hosting** for SPA + API rewrites.
  - `/api/**` rewrites to the `api` function (see `firebase.json`).

## Required backend environment (Firebase Functions)
- `AUTH_MODE=firebase`
- `AUTH_ISSUER_URL=https://securetoken.google.com/<project_id>`
- `AUTH_JWKS_URL=https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com`
- `AUTH_AUDIENCE=<project_id>`
- `BACKEND_ENCRYPTION_KEY=<32-byte urlsafe base64 key>`
- `BACKEND_USE_WORKER=1`
- `BACKEND_PUBSUB_ENABLED=1`
- `PUBSUB_TOPIC=<topic name>`
- `BACKEND_FIRESTORE_ENABLED=1`
- `FIRESTORE_JOBS_COLLECTION=skybridge-jobs`
- `FIRESTORE_CREDENTIALS_COLLECTION=skybridge-credentials`
- `BACKEND_GCS_ENABLED=1`
- `GCS_BUCKET=<bucket>`
- `GCS_PREFIX=jobs`
- `GCS_LOCATION=<region>`
- `GCP_PROJECT_ID=<project_id>`
- `CORS_ALLOW_ORIGINS=<comma separated origins>`

## Frontend build configuration (Firebase)
- `VITE_API_BASE_URL` points at your Firebase Hosting domain.
- `VITE_AUTH_MODE=firebase`
- `VITE_FIREBASE_API_KEY=<web api key>`
- `VITE_FIREBASE_AUTH_DOMAIN=<project-id>.firebaseapp.com`
- `VITE_FIREBASE_PROJECT_ID=<project_id>`
- `VITE_FIREBASE_APP_ID=<web app id>`
## Deploy
- `npm --prefix src/frontend run build`
- `firebase deploy --only functions,hosting`
Functions source lives in `functions/` and uses `functions/requirements.txt` for dependencies.

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

## Security defaults
- Firestore rules only allow authenticated reads of job documents owned by the current UID; all writes are server-only.
- Storage rules deny all client access (artifacts are served via the API).
- Do not set `AUTH_EMULATOR_TRUST_TOKENS` outside local emulators.
