# Terraform Infrastructure (Milestone 2)

This directory provides the initial Terraform scaffolding for the Skybridge backend stack.

## Layout
- `main.tf`: core AWS services (S3, DynamoDB, Cognito, API Gateway, Step Functions).
- `variables.tf`: environment and tagging inputs.
- `outputs.tf`: key resource outputs.
- `envs/`: environment-specific tfvars.

## Usage (local)
```bash
cd infra/terraform
../../scripts/build-lambda.sh
terraform init
terraform fmt
terraform validate
terraform plan -var-file=envs/dev/terraform.tfvars
```

> Note: This is a scaffold; IAM policies, deployments, and full runtime wiring still need to be added. Lambda packaging outputs to `dist/backend-handlers.zip` and should be copied to `infra/terraform/lambda/` as part of your deployment pipeline.
