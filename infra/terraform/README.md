# Terraform Infrastructure (Milestone 2)

This directory provides the initial Terraform baseline for the Skybridge backend stack.

## Layout
- `main.tf`: core AWS services (S3, DynamoDB, SQS, Cognito, API Gateway, Step Functions).
- `variables.tf`: environment and tagging inputs.
- `outputs.tf`: key resource outputs.
- `envs/`: environment-specific tfvars.
- `backend.tf`: S3 backend (requires `backend.hcl` at init time).
- `backend.hcl.template`: backend config template (copy to `backend.hcl`).

## Cognito Hosted UI (Prod)
Configure the SPA client and social IdPs via variables:
- `cognito_domain`, `cognito_callback_urls`, `cognito_logout_urls`
- `cognito_identity_providers` (e.g. `["Google","Facebook","SignInWithApple"]`)
- Provider secrets: `google_*`, `facebook_*`, `apple_*`
- `api_cors_origins` for the SPA domain(s)
- `backend_worker_token` shared secret for API/worker credential claims
- `frontend_domain` + optional `frontend_aliases` for CloudFront
- `frontend_price_class` to cap CloudFront costs

## Usage (local)
```bash
cd infra/terraform
../../scripts/build-lambda.sh
terraform init -backend-config=backend.hcl
terraform fmt
terraform validate
terraform plan -var-file=envs/dev/terraform.tfvars
```

> Note: Backend runtime wiring (IAM, API stage, JWT auth, SQS worker) is included, but frontend hosting, DNS, and CI/CD still need to be added. `scripts/build-lambda.sh` now writes `dist/backend-handlers.zip` and copies it to `infra/terraform/lambda/backend-handlers.zip`.

## Prod Apply + Runtime Wiring
When you are ready to deploy to AWS, run:
```bash
cd infra/terraform
../../scripts/build-lambda.sh
terraform init -backend-config=backend.hcl
terraform apply -var-file=envs/prod/terraform.tfvars
```

Then wire the outputs into the API + worker runtime (Terraform already injects these env vars for Lambdas):
```bash
BACKEND_DYNAMO_ENABLED=1
DYNAMO_JOBS_TABLE=<jobs_table>
DYNAMO_CREDENTIALS_TABLE=<credentials_table>
BACKEND_SQS_ENABLED=1
SQS_QUEUE_URL=<queue_url>
```

The worker must use the same `BACKEND_WORKER_TOKEN` as the API in order to claim
credentials for queued jobs. Artifact retention is enforced via S3 lifecycle rules
(7 days) configured by this Terraform module.

## Frontend Hosting + DNS (Namecheap)
- Build the frontend: `npm --prefix src/frontend run build` (or via devcontainer).
- Sync `src/frontend/dist` to the frontend bucket:
  `aws s3 sync src/frontend/dist s3://<frontend_bucket_name> --delete`
- After `terraform apply`, read `acm_validation_records` and add the CNAME records in Namecheap.
- ACM for CloudFront lives in `us-east-1`; certificate validation can take a few minutes after DNS changes.
- Once ACM validates, the CloudFront distribution will serve the domain.
- Add a CNAME for `skybridge` → `<cloudfront_domain_name>` in Namecheap.

## Repeatable deployment
- `SKYBRIDGE_AUTO_APPROVE=1 ./scripts/deploy-prod.sh` builds Lambdas, applies Terraform, builds the frontend, syncs to S3, and invalidates CloudFront.
