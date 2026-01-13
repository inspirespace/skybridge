# Terraform Infrastructure

Baseline Terraform for the Skybridge backend stack.

## Layout
- `main.tf`: core AWS services (S3, DynamoDB, SQS, Cognito, API Gateway).
- `variables.tf`: environment and tagging inputs.
- `outputs.tf`: key resource outputs.
- `envs/`: environment-specific tfvars.
- `backend.tf`: S3 backend (requires `backend.hcl` at init time).

## Usage
1) Build the Lambda package and place it at `infra/terraform/lambda/backend-handlers.zip`.
2) Run Terraform:

```bash
cd infra/terraform
terraform init -backend-config=backend.hcl
terraform fmt -check -recursive
terraform validate
terraform plan -var-file=envs/dev/terraform.tfvars
```

## Cognito Hosted UI (Prod)
Configure the SPA client and social IdPs via variables:
- `cognito_domain`, `cognito_callback_urls`, `cognito_logout_urls`
- `cognito_identity_providers` (e.g. `["Google","Facebook","SignInWithApple"]`)
- Provider secrets: `google_*`, `facebook_*`, `apple_*`
- `api_cors_origins` for the SPA domain(s)
- `backend_worker_token` shared secret for API/worker credential claims
- `frontend_domain` + optional `frontend_aliases` for CloudFront
- `frontend_price_class` to cap CloudFront costs
