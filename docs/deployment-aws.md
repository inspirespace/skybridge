# AWS Deployment Guide (Free-Tier Oriented)

This guide covers a production-ready AWS deployment using Lambda + API Gateway + SQS + DynamoDB + S3 + Cognito, plus CloudFront + S3 for the frontend. It assumes DNS remains with Namecheap and the domain is `skybridge.inspirespace.co`.

## Prerequisites
- AWS account with access to IAM, Lambda, API Gateway, SQS, DynamoDB, S3, CloudFront, ACM, and Cognito.
- AWS CLI authenticated (`aws configure` or IAM role).
- Terraform >= 1.5.
- Node.js + npm for frontend build.
- Python 3.10+ for Lambda packaging.

## One-time setup (external providers)
1) Create social IdP apps (if desired):
   - Google OAuth Client ID + Secret
   - Apple Services ID + Key + Team ID
   - Facebook App ID + Secret
2) Keep the credentials ready for Terraform variables.

## Configure Terraform variables
Update `infra/terraform/envs/prod/terraform.tfvars` with:
- `backend_worker_token` (shared secret)
- `cognito_identity_providers` + provider credentials
- `cognito_callback_urls` + `cognito_logout_urls`
- `api_cors_origins` = `["https://skybridge.inspirespace.co"]`
- `frontend_domain` = `skybridge.inspirespace.co`

## Terraform state backend
`infra/terraform/backend.tf` is configured for an S3 backend. Provide backend settings at init time:
```
terraform init -backend-config=backend.hcl
```
Example `backend.hcl`:
```
bucket         = "skybridge-terraform-state"
key            = "prod/terraform.tfstate"
region         = "eu-west-1"
dynamodb_table = "skybridge-terraform-locks"
```

## Build the Lambda package
```
./scripts/build-lambda.sh
```

## Deploy infrastructure
```
cd infra/terraform
terraform init
terraform apply -var-file=envs/prod/terraform.tfvars
```

Terraform outputs:
- `api_base_url`
- `auth_issuer_url`
- `user_pool_client_id`
- `user_pool_domain`
- `frontend_bucket_name`
- `cloudfront_domain_name`
- `cloudfront_distribution_id`
- `acm_validation_records`

## Namecheap DNS
1) Add the ACM validation CNAME records from `acm_validation_records`.
2) Add CNAME:
   - Host: `skybridge`
   - Target: `<cloudfront_domain_name>`

ACM validation may take several minutes. CloudFront will serve the domain after validation completes.
If CloudFront fails to create due to pending validation, re-run `terraform apply` after the DNS records are live.

## Build the frontend for production
Use environment variables from Terraform outputs:
```
VITE_API_BASE_URL=<api_base_url>
VITE_AUTH_MODE=oidc
VITE_AUTH_ISSUER_URL=<auth_issuer_url>
VITE_AUTH_CLIENT_ID=<user_pool_client_id>
VITE_AUTH_PROVIDER_PARAM=identity_provider
VITE_AUTH_REDIRECT_PATH=/app/auth/callback
VITE_AUTH_LOGOUT_URL=https://<user_pool_domain>.auth.eu-west-1.amazonaws.com/logout
```

Build:
```
npm --prefix src/frontend run build
```

## Upload frontend assets
```
aws s3 sync src/frontend/dist s3://<frontend_bucket_name> --delete
aws cloudfront create-invalidation --distribution-id <cloudfront_distribution_id> --paths "/*"
```

## One-command deploy script
For repeatable deploys (CI-ready), use:
```
SKYBRIDGE_AUTO_APPROVE=1 ./scripts/deploy-prod.sh
```
Optional env vars:
- `TF_VARS_FILE` to point at a different tfvars file.
- `TF_BACKEND_CONFIG_FILE` to point at an S3 backend config file.
- `SKIP_INVALIDATION=1` to skip CloudFront invalidation.

## GitHub Actions (recommended)
Workflow: `.github/workflows/deploy-prod.yml`

Required secrets:
- `AWS_ROLE_ARN` (OIDC role to assume)
- `TF_STATE_BUCKET`
- `TF_STATE_KEY`
- `TF_STATE_REGION`
- `TF_STATE_DDB_TABLE`
- `BACKEND_WORKER_TOKEN`

Optional secrets:
- `COGNITO_IDPS` (JSON list, e.g. `["Google","SignInWithApple","Facebook"]`; default `[]`)
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
- `APPLE_CLIENT_ID`, `APPLE_TEAM_ID`, `APPLE_KEY_ID`, `APPLE_PRIVATE_KEY`
- `FACEBOOK_CLIENT_ID`, `FACEBOOK_CLIENT_SECRET`

## Local dev with Lambda-style worker
To run a local worker that uses the Lambda handler logic:
```
BACKEND_SQS_ENABLED=1 SQS_QUEUE_URL=<local-or-aws-queue-url> ./scripts/run-lambda-worker-local.sh
```

## Verification checklist
- Sign in via Cognito Hosted UI.
- Create a job, review completes, import completes.
- Artifacts appear in S3 and expire after 7 days.
- CloudFront serves `https://skybridge.inspirespace.co`.
