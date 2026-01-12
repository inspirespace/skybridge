# Production Launch Checklist

## 1) AWS prerequisites
- [ ] S3 bucket for Terraform state exists.
- [ ] DynamoDB table for Terraform locks exists.
- [ ] IAM role for GitHub Actions OIDC exists (if using CI).

## 2) Terraform backend
- [ ] Copy `infra/terraform/backend.hcl.template` → `infra/terraform/backend.hcl`.
- [ ] Update bucket/key/region/table values.

## 3) Production configuration
- [ ] Set `backend_worker_token` in `infra/terraform/envs/prod/terraform.tfvars`.
- [ ] Set `cognito_callback_urls` and `cognito_logout_urls` to `https://skybridge.inspirespace.co/...`.
- [ ] Set `api_cors_origins = ["https://skybridge.inspirespace.co"]`.
- [ ] Set `frontend_domain = "skybridge.inspirespace.co"`.
- [ ] Optional: configure social IdP credentials (Google/Apple/Facebook).

## 4) Deploy infra + lambdas
- [ ] Run `./scripts/build-lambda.sh`.
- [ ] Run `cd infra/terraform && terraform init -backend-config=backend.hcl`.
- [ ] Run `terraform apply -var-file=envs/prod/terraform.tfvars`.

## 5) DNS (Namecheap)
- [ ] Add ACM validation CNAMEs from `acm_validation_records`.
- [ ] Add CNAME `skybridge` → `<cloudfront_domain_name>`.
- [ ] Wait for ACM validation (re-run `terraform apply` if needed).

## 6) Frontend
- [ ] Build with production env vars (see `docs/deployment-aws.md`).
- [ ] Sync `src/frontend/dist` to S3 bucket from `frontend_bucket_name`.
- [ ] Invalidate CloudFront distribution.

## 7) Verification
- [ ] Sign in via Cognito Hosted UI.
- [ ] Create job → review completes.
- [ ] Accept review → import completes.
- [ ] Download artifacts zip.
- [ ] Verify S3 lifecycle + DynamoDB TTL configured.

## 8) CI (optional)
- [ ] Set GitHub Actions secrets (see `docs/deployment-aws.md`).
- [ ] Run workflow `.github/workflows/deploy-prod.yml`.
