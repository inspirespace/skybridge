locals {
  name_prefix = "${var.project_name}-${var.environment}"
}

resource "aws_s3_bucket" "artifacts" {
  bucket        = "${local.name_prefix}-artifacts"
  force_destroy = false

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  rule {
    id     = "expire-job-artifacts"
    status = "Enabled"

    expiration {
      days = 30
    }
  }
}

resource "aws_dynamodb_table" "jobs" {
  name         = "${local.name_prefix}-jobs"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "user_id"
  range_key    = "job_id"

  attribute {
    name = "user_id"
    type = "S"
  }

  attribute {
    name = "job_id"
    type = "S"
  }

  ttl {
    attribute_name = "ttl_epoch"
    enabled        = true
  }
}

resource "aws_cognito_user_pool" "users" {
  name = "${local.name_prefix}-users"
}

resource "aws_apigatewayv2_api" "http_api" {
  name          = "${local.name_prefix}-api"
  protocol_type = "HTTP"
}

resource "aws_iam_role" "lambda_exec" {
  name = "${local.name_prefix}-lambda-exec"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = "sts:AssumeRole",
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_lambda_function" "create_job" {
  function_name = "${local.name_prefix}-create-job"
  role          = aws_iam_role.lambda_exec.arn
  handler       = "lambda_handlers.create_job_handler"
  runtime       = "python3.12"
  filename      = "${path.module}/lambda/backend-handlers.zip"
  timeout       = 30
}

resource "aws_lambda_function" "list_jobs" {
  function_name = "${local.name_prefix}-list-jobs"
  role          = aws_iam_role.lambda_exec.arn
  handler       = "lambda_handlers.list_jobs_handler"
  runtime       = "python3.12"
  filename      = "${path.module}/lambda/backend-handlers.zip"
  timeout       = 30
}

resource "aws_lambda_function" "get_job" {
  function_name = "${local.name_prefix}-get-job"
  role          = aws_iam_role.lambda_exec.arn
  handler       = "lambda_handlers.get_job_handler"
  runtime       = "python3.12"
  filename      = "${path.module}/lambda/backend-handlers.zip"
  timeout       = 30
}

resource "aws_lambda_function" "accept_review" {
  function_name = "${local.name_prefix}-accept-review"
  role          = aws_iam_role.lambda_exec.arn
  handler       = "lambda_handlers.accept_review_handler"
  runtime       = "python3.12"
  filename      = "${path.module}/lambda/backend-handlers.zip"
  timeout       = 30
}

resource "aws_lambda_function" "list_artifacts" {
  function_name = "${local.name_prefix}-list-artifacts"
  role          = aws_iam_role.lambda_exec.arn
  handler       = "lambda_handlers.list_artifacts_handler"
  runtime       = "python3.12"
  filename      = "${path.module}/lambda/backend-handlers.zip"
  timeout       = 30
}

resource "aws_lambda_function" "read_artifact" {
  function_name = "${local.name_prefix}-read-artifact"
  role          = aws_iam_role.lambda_exec.arn
  handler       = "lambda_handlers.read_artifact_handler"
  runtime       = "python3.12"
  filename      = "${path.module}/lambda/backend-handlers.zip"
  timeout       = 30
}

resource "aws_lambda_function" "delete_job" {
  function_name = "${local.name_prefix}-delete-job"
  role          = aws_iam_role.lambda_exec.arn
  handler       = "lambda_handlers.delete_job_handler"
  runtime       = "python3.12"
  filename      = "${path.module}/lambda/backend-handlers.zip"
  timeout       = 30
}

resource "aws_apigatewayv2_integration" "create_job" {
  api_id                 = aws_apigatewayv2_api.http_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.create_job.invoke_arn
  integration_method     = "POST"
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "list_jobs" {
  api_id                 = aws_apigatewayv2_api.http_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.list_jobs.invoke_arn
  integration_method     = "GET"
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "get_job" {
  api_id                 = aws_apigatewayv2_api.http_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.get_job.invoke_arn
  integration_method     = "GET"
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "accept_review" {
  api_id                 = aws_apigatewayv2_api.http_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.accept_review.invoke_arn
  integration_method     = "POST"
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "list_artifacts" {
  api_id                 = aws_apigatewayv2_api.http_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.list_artifacts.invoke_arn
  integration_method     = "GET"
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "read_artifact" {
  api_id                 = aws_apigatewayv2_api.http_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.read_artifact.invoke_arn
  integration_method     = "GET"
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "delete_job" {
  api_id                 = aws_apigatewayv2_api.http_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.delete_job.invoke_arn
  integration_method     = "DELETE"
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "create_job" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "POST /jobs"
  target    = "integrations/${aws_apigatewayv2_integration.create_job.id}"
}

resource "aws_apigatewayv2_route" "list_jobs" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "GET /jobs"
  target    = "integrations/${aws_apigatewayv2_integration.list_jobs.id}"
}

resource "aws_apigatewayv2_route" "get_job" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "GET /jobs/{job_id}"
  target    = "integrations/${aws_apigatewayv2_integration.get_job.id}"
}

resource "aws_apigatewayv2_route" "accept_review" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "POST /jobs/{job_id}/review/accept"
  target    = "integrations/${aws_apigatewayv2_integration.accept_review.id}"
}

resource "aws_apigatewayv2_route" "list_artifacts" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "GET /jobs/{job_id}/artifacts"
  target    = "integrations/${aws_apigatewayv2_integration.list_artifacts.id}"
}

resource "aws_apigatewayv2_route" "read_artifact" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "GET /jobs/{job_id}/artifacts/{artifact_name}"
  target    = "integrations/${aws_apigatewayv2_integration.read_artifact.id}"
}

resource "aws_apigatewayv2_route" "delete_job" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "DELETE /jobs/{job_id}"
  target    = "integrations/${aws_apigatewayv2_integration.delete_job.id}"
}

resource "aws_iam_role" "step_functions" {
  name = "${local.name_prefix}-step-functions-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = "sts:AssumeRole",
        Principal = {
          Service = "states.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_sfn_state_machine" "migration" {
  name     = "${local.name_prefix}-migration"
  role_arn = aws_iam_role.step_functions.arn

  definition = jsonencode({
    Comment = "Skybridge migration state machine (placeholder)",
    StartAt = "Review",
    States = {
      Review = {
        Type = "Pass",
        End  = true
      }
    }
  })
}
