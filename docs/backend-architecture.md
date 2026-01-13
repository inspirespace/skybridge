# Backend Architecture (Serverless)

## Overview
The backend is serverless. An API Lambda receives requests, enqueues work in SQS, and a worker Lambda processes review/import jobs. State is in DynamoDB and artifacts go to S3.

## Components
- **API Lambda** (`src/backend/lambda_handlers.py`): REST endpoints for auth, job creation, polling, and artifacts.
- **Worker Lambda** (`src/backend/worker_lambda.py`): processes SQS messages for review/import jobs.
- **Queue** (SQS): decouples API from long-running work.
- **State** (DynamoDB): job metadata + credential claims.
- **Artifacts** (S3): review/import outputs and logs.

## Local parity
`docker-compose.yml` runs local equivalents of production services so the flow matches AWS.
- Lambda API emulator (HTTP)
- Lambda worker process
- LocalStack (SQS)
- DynamoDB Local
- MinIO (S3)
- Keycloak (OIDC dev auth)

This mirrors production behavior: API enqueues jobs, worker processes them, state lives in DynamoDB, artifacts in S3.

## Runtime flow
1) UI starts a review job → API Lambda writes job state and enqueues SQS message.
2) Worker Lambda consumes SQS → runs the migration pipeline.
3) Worker updates DynamoDB and uploads artifacts to S3.
4) UI polls job status and downloads artifacts when ready.
