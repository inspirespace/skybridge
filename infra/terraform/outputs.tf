output "artifact_bucket_name" {
  description = "S3 bucket for job artifacts."
  value       = aws_s3_bucket.artifacts.bucket
}

output "jobs_table_name" {
  description = "DynamoDB table for job metadata."
  value       = aws_dynamodb_table.jobs.name
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

output "lambda_handler_zip" {
  description = "Path to the Lambda handler zip package."
  value       = "${path.module}/lambda/backend-handlers.zip"
}

output "state_machine_arn" {
  description = "Step Functions state machine ARN."
  value       = aws_sfn_state_machine.migration.arn
}
