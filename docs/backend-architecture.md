# Backend Architecture (Serverless)

## Overview
The backend is serverless. In production, the stack targets Firebase (Functions 2nd gen + Firestore + Storage + Auth) with Pub/Sub for queueing. The API receives requests, enqueues work, and a worker processes review/import jobs. State lives in Firestore and artifacts go to Storage.

## Components
- **API (Functions 2nd gen)** (`functions/main.py`): HTTP function that maps requests to Lambda handlers.
- **Worker (Functions 2nd gen)** (`functions/main.py`): Pub/Sub-triggered function for review/import jobs.
- **Queue** (Pub/Sub): decouples API from long-running work.
- **State** (Firestore): job metadata + credential claims.
- **Artifacts** (Cloud Storage): review/import outputs and logs.

## Local parity
`docker-compose.yml` runs local equivalents of production services so the flow matches Firebase.
- Firebase Functions emulator (HTTP API + worker)
- Firebase emulators (Auth, Firestore, Pub/Sub, Storage)

This mirrors the Firebase flow for local dev: API publishes Pub/Sub messages, worker processes them, state lives in Firestore, artifacts in Storage.

## Runtime flow (Firebase)
1) UI starts a review job → Functions API writes job state and publishes Pub/Sub message.
2) Functions worker consumes Pub/Sub → runs the migration pipeline.
3) Worker updates Firestore and uploads artifacts to Storage.
4) UI polls job status and downloads artifacts when ready.

## Runtime flow (Local)
1) UI starts a review job → API writes job state and publishes Pub/Sub message.
2) Worker consumes Pub/Sub → runs the migration pipeline.
3) Worker updates Firestore and uploads artifacts to Storage emulator.
4) UI polls job status and downloads artifacts when ready.
