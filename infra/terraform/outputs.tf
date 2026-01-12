output "artifact_bucket_name" {
  description = "S3 bucket for job artifacts."
  value       = aws_s3_bucket.artifacts.bucket
}

output "jobs_table_name" {
  description = "DynamoDB table for job metadata."
  value       = aws_dynamodb_table.jobs.name
}

output "credentials_table_name" {
  description = "DynamoDB table for short-lived credentials."
  value       = aws_dynamodb_table.credentials.name
}

output "user_pool_id" {
  description = "Cognito user pool ID."
  value       = aws_cognito_user_pool.users.id
}

output "user_pool_client_id" {
  description = "Cognito user pool app client ID."
  value       = aws_cognito_user_pool_client.web.id
}

output "user_pool_domain" {
  description = "Cognito hosted UI domain (if configured)."
  value       = try(aws_cognito_user_pool_domain.hosted_ui[0].domain, null)
}

output "api_id" {
  description = "API Gateway HTTP API ID."
  value       = aws_apigatewayv2_api.http_api.id
}

output "api_base_url" {
  description = "API Gateway base URL."
  value       = aws_apigatewayv2_api.http_api.api_endpoint
}

output "auth_issuer_url" {
  description = "OIDC issuer URL for Cognito."
  value       = "https://cognito-idp.${var.aws_region}.amazonaws.com/${aws_cognito_user_pool.users.id}"
}

output "frontend_bucket_name" {
  description = "S3 bucket for frontend assets."
  value       = aws_s3_bucket.frontend.bucket
}

output "cloudfront_domain_name" {
  description = "CloudFront distribution domain name."
  value       = aws_cloudfront_distribution.frontend.domain_name
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID."
  value       = aws_cloudfront_distribution.frontend.id
}

output "acm_validation_records" {
  description = "DNS validation records for the frontend ACM certificate."
  value = var.frontend_domain == "" ? [] : [
    for option in aws_acm_certificate.frontend[0].domain_validation_options : {
      name  = option.resource_record_name
      type  = option.resource_record_type
      value = option.resource_record_value
    }
  ]
}

output "job_queue_url" {
  description = "SQS queue URL for job orchestration."
  value       = aws_sqs_queue.job_queue.url
}

output "lambda_handler_zip" {
  description = "Path to the Lambda handler zip package."
  value       = "${path.module}/lambda/backend-handlers.zip"
}

output "state_machine_arn" {
  description = "Step Functions state machine ARN."
  value       = aws_sfn_state_machine.migration.arn
}
