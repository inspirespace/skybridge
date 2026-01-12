locals {
  name_prefix = "${var.project_name}-${var.environment}"
  auth_issuer = "https://cognito-idp.${var.aws_region}.amazonaws.com/${aws_cognito_user_pool.users.id}"
  cors_origins = length(var.api_cors_origins) > 0 ? var.api_cors_origins : ["*"]
  lambda_zip = "${path.module}/lambda/backend-handlers.zip"
  lambda_zip_hash = filebase64sha256(local.lambda_zip)
  frontend_aliases = compact(concat([var.frontend_domain], var.frontend_aliases))
  lambda_env = {
    ENV                      = var.environment
    AUTH_MODE                = "oidc"
    AUTH_ISSUER_URL          = local.auth_issuer
    AUTH_BROWSER_ISSUER_URL  = local.auth_issuer
    AUTH_CLIENT_ID           = aws_cognito_user_pool_client.web.id
    AUTH_AUDIENCE            = aws_cognito_user_pool_client.web.id
    BACKEND_USE_WORKER       = "1"
    BACKEND_SQS_ENABLED      = "1"
    SQS_QUEUE_URL            = aws_sqs_queue.job_queue.url
    BACKEND_WORKER_TOKEN     = var.backend_worker_token
    BACKEND_DYNAMO_ENABLED   = "1"
    DYNAMO_JOBS_TABLE        = aws_dynamodb_table.jobs.name
    DYNAMO_CREDENTIALS_TABLE = aws_dynamodb_table.credentials.name
    BACKEND_S3_ENABLED       = "1"
    S3_BUCKET                = aws_s3_bucket.artifacts.bucket
    S3_PREFIX                = "jobs"
    S3_REGION                = var.aws_region
    S3_SSE                   = "true"
    AWS_REGION               = var.aws_region
    AUTH_TOKEN_URL           = local.frontend_auth_token_url
  }
}

locals {
  frontend_auth_domain = try(aws_cognito_user_pool_domain.hosted_ui[0].domain, "")
  frontend_auth_token_url = local.frontend_auth_domain != "" ? "https://${local.frontend_auth_domain}.auth.${var.aws_region}.amazoncognito.com/oauth2/token" : ""
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
      days = 7
    }
  }
}

resource "aws_s3_bucket" "frontend" {
  bucket        = "${local.name_prefix}-frontend"
  force_destroy = false

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket                  = aws_s3_bucket.frontend.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  rule {
    object_ownership = "BucketOwnerPreferred"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
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

  global_secondary_index {
    name            = "job_id-index"
    hash_key        = "job_id"
    projection_type = "ALL"
  }
}

resource "aws_dynamodb_table" "credentials" {
  name         = "${local.name_prefix}-credentials"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "token"

  attribute {
    name = "token"
    type = "S"
  }

  ttl {
    attribute_name = "ttl_epoch"
    enabled        = true
  }
}

resource "aws_sqs_queue" "job_queue" {
  name                       = "${local.name_prefix}-job-queue"
  visibility_timeout_seconds = 900
}

resource "aws_cognito_user_pool" "users" {
  name = "${local.name_prefix}-users"
}

resource "aws_cognito_user_pool_client" "web" {
  name                                 = "${local.name_prefix}-web"
  user_pool_id                         = aws_cognito_user_pool.users.id
  generate_secret                      = false
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["openid", "email", "profile"]
  allowed_oauth_flows_user_pool_client = true
  callback_urls                        = var.cognito_callback_urls
  logout_urls                          = var.cognito_logout_urls
  supported_identity_providers         = concat(["COGNITO"], var.cognito_identity_providers)
  depends_on = [
    aws_cognito_identity_provider.google,
    aws_cognito_identity_provider.facebook,
    aws_cognito_identity_provider.apple
  ]
}

resource "aws_cognito_user_pool_domain" "hosted_ui" {
  count        = var.cognito_domain == "" ? 0 : 1
  domain       = var.cognito_domain
  user_pool_id = aws_cognito_user_pool.users.id
}

resource "aws_cognito_identity_provider" "google" {
  count         = var.google_client_id == "" ? 0 : 1
  user_pool_id  = aws_cognito_user_pool.users.id
  provider_name = "Google"
  provider_type = "Google"

  provider_details = {
    client_id        = var.google_client_id
    client_secret    = var.google_client_secret
    authorize_scopes = "openid email profile"
  }

  attribute_mapping = {
    email = "email"
    name  = "name"
  }
}

resource "aws_cognito_identity_provider" "facebook" {
  count         = var.facebook_client_id == "" ? 0 : 1
  user_pool_id  = aws_cognito_user_pool.users.id
  provider_name = "Facebook"
  provider_type = "Facebook"

  provider_details = {
    client_id        = var.facebook_client_id
    client_secret    = var.facebook_client_secret
    authorize_scopes = "email,public_profile"
  }

  attribute_mapping = {
    email = "email"
    name  = "name"
  }
}

resource "aws_cognito_identity_provider" "apple" {
  count         = var.apple_client_id == "" ? 0 : 1
  user_pool_id  = aws_cognito_user_pool.users.id
  provider_name = "SignInWithApple"
  provider_type = "SignInWithApple"

  provider_details = {
    client_id        = var.apple_client_id
    team_id          = var.apple_team_id
    key_id           = var.apple_key_id
    private_key      = var.apple_private_key
    authorize_scopes = "openid email name"
  }

  attribute_mapping = {
    email = "email"
    name  = "name"
  }
}

resource "aws_apigatewayv2_api" "http_api" {
  name          = "${local.name_prefix}-api"
  protocol_type = "HTTP"
  cors_configuration {
    allow_origins = local.cors_origins
    allow_methods = ["GET", "POST", "DELETE", "OPTIONS"]
    allow_headers = ["Authorization", "Content-Type", "X-User-Id"]
  }
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.http_api.id
  name        = "$default"
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_access.arn
    format = jsonencode({
      requestId  = "$context.requestId"
      ip         = "$context.identity.sourceIp"
      requestTime = "$context.requestTime"
      httpMethod = "$context.httpMethod"
      routeKey   = "$context.routeKey"
      status     = "$context.status"
      protocol   = "$context.protocol"
      responseLength = "$context.responseLength"
    })
  }
}

resource "aws_cloudwatch_log_group" "api_access" {
  name              = "/aws/apigateway/${local.name_prefix}-http-api"
  retention_in_days = var.log_retention_days
}

resource "aws_apigatewayv2_authorizer" "jwt" {
  api_id           = aws_apigatewayv2_api.http_api.id
  authorizer_type  = "JWT"
  identity_sources = ["$request.header.Authorization"]
  name             = "${local.name_prefix}-jwt"

  jwt_configuration {
    audience = [aws_cognito_user_pool_client.web.id]
    issuer   = local.auth_issuer
  }
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

resource "aws_iam_role_policy" "lambda_exec" {
  name = "${local.name_prefix}-lambda-exec"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ],
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow",
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:Query",
          "dynamodb:Scan",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem"
        ],
        Resource = [
          aws_dynamodb_table.jobs.arn,
          aws_dynamodb_table.credentials.arn
        ]
      },
      {
        Effect = "Allow",
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ],
        Resource = "${aws_s3_bucket.artifacts.arn}/*"
      },
      {
        Effect = "Allow",
        Action = ["s3:ListBucket"],
        Resource = aws_s3_bucket.artifacts.arn
      },
      {
        Effect = "Allow",
        Action = [
          "sqs:SendMessage",
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ],
        Resource = aws_sqs_queue.job_queue.arn
      }
    ]
  })
}

resource "aws_lambda_function" "create_job" {
  function_name = "${local.name_prefix}-create-job"
  role          = aws_iam_role.lambda_exec.arn
  handler       = "lambda_handlers.create_job_handler"
  runtime       = "python3.12"
  filename      = local.lambda_zip
  source_code_hash = local.lambda_zip_hash
  timeout       = 30
  environment {
    variables = local.lambda_env
  }
}

resource "aws_lambda_function" "list_jobs" {
  function_name = "${local.name_prefix}-list-jobs"
  role          = aws_iam_role.lambda_exec.arn
  handler       = "lambda_handlers.list_jobs_handler"
  runtime       = "python3.12"
  filename      = local.lambda_zip
  source_code_hash = local.lambda_zip_hash
  timeout       = 30
  environment {
    variables = local.lambda_env
  }
}

resource "aws_lambda_function" "get_job" {
  function_name = "${local.name_prefix}-get-job"
  role          = aws_iam_role.lambda_exec.arn
  handler       = "lambda_handlers.get_job_handler"
  runtime       = "python3.12"
  filename      = local.lambda_zip
  source_code_hash = local.lambda_zip_hash
  timeout       = 30
  environment {
    variables = local.lambda_env
  }
}

resource "aws_lambda_function" "accept_review" {
  function_name = "${local.name_prefix}-accept-review"
  role          = aws_iam_role.lambda_exec.arn
  handler       = "lambda_handlers.accept_review_handler"
  runtime       = "python3.12"
  filename      = local.lambda_zip
  source_code_hash = local.lambda_zip_hash
  timeout       = 30
  environment {
    variables = local.lambda_env
  }
}

resource "aws_lambda_function" "list_artifacts" {
  function_name = "${local.name_prefix}-list-artifacts"
  role          = aws_iam_role.lambda_exec.arn
  handler       = "lambda_handlers.list_artifacts_handler"
  runtime       = "python3.12"
  filename      = local.lambda_zip
  source_code_hash = local.lambda_zip_hash
  timeout       = 30
  environment {
    variables = local.lambda_env
  }
}

resource "aws_lambda_function" "read_artifact" {
  function_name = "${local.name_prefix}-read-artifact"
  role          = aws_iam_role.lambda_exec.arn
  handler       = "lambda_handlers.read_artifact_handler"
  runtime       = "python3.12"
  filename      = local.lambda_zip
  source_code_hash = local.lambda_zip_hash
  timeout       = 30
  environment {
    variables = local.lambda_env
  }
}

resource "aws_lambda_function" "delete_job" {
  function_name = "${local.name_prefix}-delete-job"
  role          = aws_iam_role.lambda_exec.arn
  handler       = "lambda_handlers.delete_job_handler"
  runtime       = "python3.12"
  filename      = local.lambda_zip
  source_code_hash = local.lambda_zip_hash
  timeout       = 30
  environment {
    variables = local.lambda_env
  }
}

resource "aws_lambda_function" "validate_credentials" {
  function_name = "${local.name_prefix}-validate-credentials"
  role          = aws_iam_role.lambda_exec.arn
  handler       = "lambda_handlers.validate_credentials_handler"
  runtime       = "python3.12"
  filename      = local.lambda_zip
  source_code_hash = local.lambda_zip_hash
  timeout       = 30
  environment {
    variables = local.lambda_env
  }
}

resource "aws_lambda_function" "auth_token" {
  function_name = "${local.name_prefix}-auth-token"
  role          = aws_iam_role.lambda_exec.arn
  handler       = "lambda_handlers.auth_token_handler"
  runtime       = "python3.12"
  filename      = local.lambda_zip
  source_code_hash = local.lambda_zip_hash
  timeout       = 30
  environment {
    variables = local.lambda_env
  }
}

resource "aws_lambda_function" "download_artifacts_zip" {
  function_name = "${local.name_prefix}-download-artifacts-zip"
  role          = aws_iam_role.lambda_exec.arn
  handler       = "lambda_handlers.download_artifacts_zip_handler"
  runtime       = "python3.12"
  filename      = local.lambda_zip
  source_code_hash = local.lambda_zip_hash
  timeout       = 60
  environment {
    variables = local.lambda_env
  }
}

resource "aws_lambda_function" "worker" {
  function_name = "${local.name_prefix}-worker"
  role          = aws_iam_role.lambda_exec.arn
  handler       = "lambda_handlers.sqs_worker_handler"
  runtime       = "python3.12"
  filename      = local.lambda_zip
  source_code_hash = local.lambda_zip_hash
  timeout       = 900
  environment {
    variables = local.lambda_env
  }
}

resource "aws_lambda_event_source_mapping" "worker_sqs" {
  event_source_arn = aws_sqs_queue.job_queue.arn
  function_name    = aws_lambda_function.worker.arn
  batch_size       = 1
}

resource "aws_cloudwatch_log_group" "lambda_create_job" {
  name              = "/aws/lambda/${aws_lambda_function.create_job.function_name}"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "lambda_list_jobs" {
  name              = "/aws/lambda/${aws_lambda_function.list_jobs.function_name}"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "lambda_get_job" {
  name              = "/aws/lambda/${aws_lambda_function.get_job.function_name}"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "lambda_accept_review" {
  name              = "/aws/lambda/${aws_lambda_function.accept_review.function_name}"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "lambda_list_artifacts" {
  name              = "/aws/lambda/${aws_lambda_function.list_artifacts.function_name}"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "lambda_read_artifact" {
  name              = "/aws/lambda/${aws_lambda_function.read_artifact.function_name}"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "lambda_delete_job" {
  name              = "/aws/lambda/${aws_lambda_function.delete_job.function_name}"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "lambda_validate_credentials" {
  name              = "/aws/lambda/${aws_lambda_function.validate_credentials.function_name}"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "lambda_auth_token" {
  name              = "/aws/lambda/${aws_lambda_function.auth_token.function_name}"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "lambda_download_artifacts_zip" {
  name              = "/aws/lambda/${aws_lambda_function.download_artifacts_zip.function_name}"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "lambda_worker" {
  name              = "/aws/lambda/${aws_lambda_function.worker.function_name}"
  retention_in_days = var.log_retention_days
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

resource "aws_apigatewayv2_integration" "validate_credentials" {
  api_id                 = aws_apigatewayv2_api.http_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.validate_credentials.invoke_arn
  integration_method     = "POST"
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "auth_token" {
  api_id                 = aws_apigatewayv2_api.http_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.auth_token.invoke_arn
  integration_method     = "POST"
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "download_artifacts_zip" {
  api_id                 = aws_apigatewayv2_api.http_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.download_artifacts_zip.invoke_arn
  integration_method     = "GET"
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "create_job" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "POST /jobs"
  target    = "integrations/${aws_apigatewayv2_integration.create_job.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

resource "aws_apigatewayv2_route" "list_jobs" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "GET /jobs"
  target    = "integrations/${aws_apigatewayv2_integration.list_jobs.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

resource "aws_apigatewayv2_route" "get_job" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "GET /jobs/{job_id}"
  target    = "integrations/${aws_apigatewayv2_integration.get_job.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

resource "aws_apigatewayv2_route" "accept_review" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "POST /jobs/{job_id}/review/accept"
  target    = "integrations/${aws_apigatewayv2_integration.accept_review.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

resource "aws_apigatewayv2_route" "list_artifacts" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "GET /jobs/{job_id}/artifacts"
  target    = "integrations/${aws_apigatewayv2_integration.list_artifacts.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

resource "aws_apigatewayv2_route" "read_artifact" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "GET /jobs/{job_id}/artifacts/{artifact_name}"
  target    = "integrations/${aws_apigatewayv2_integration.read_artifact.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

resource "aws_apigatewayv2_route" "delete_job" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "DELETE /jobs/{job_id}"
  target    = "integrations/${aws_apigatewayv2_integration.delete_job.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

resource "aws_apigatewayv2_route" "validate_credentials" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "POST /credentials/validate"
  target    = "integrations/${aws_apigatewayv2_integration.validate_credentials.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

resource "aws_apigatewayv2_route" "auth_token" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "POST /auth/token"
  target    = "integrations/${aws_apigatewayv2_integration.auth_token.id}"
  authorization_type = "NONE"
}

resource "aws_apigatewayv2_route" "download_artifacts_zip" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "GET /jobs/{job_id}/artifacts.zip"
  target    = "integrations/${aws_apigatewayv2_integration.download_artifacts_zip.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

resource "aws_lambda_permission" "create_job" {
  statement_id  = "AllowApiGatewayInvokeCreateJob"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.create_job.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http_api.execution_arn}/*/*"
}

resource "aws_lambda_permission" "list_jobs" {
  statement_id  = "AllowApiGatewayInvokeListJobs"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.list_jobs.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http_api.execution_arn}/*/*"
}

resource "aws_lambda_permission" "get_job" {
  statement_id  = "AllowApiGatewayInvokeGetJob"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.get_job.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http_api.execution_arn}/*/*"
}

resource "aws_lambda_permission" "accept_review" {
  statement_id  = "AllowApiGatewayInvokeAcceptReview"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.accept_review.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http_api.execution_arn}/*/*"
}

resource "aws_lambda_permission" "list_artifacts" {
  statement_id  = "AllowApiGatewayInvokeListArtifacts"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.list_artifacts.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http_api.execution_arn}/*/*"
}

resource "aws_lambda_permission" "read_artifact" {
  statement_id  = "AllowApiGatewayInvokeReadArtifact"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.read_artifact.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http_api.execution_arn}/*/*"
}

resource "aws_lambda_permission" "delete_job" {
  statement_id  = "AllowApiGatewayInvokeDeleteJob"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.delete_job.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http_api.execution_arn}/*/*"
}

resource "aws_lambda_permission" "validate_credentials" {
  statement_id  = "AllowApiGatewayInvokeValidateCredentials"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.validate_credentials.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http_api.execution_arn}/*/*"
}

resource "aws_lambda_permission" "auth_token" {
  statement_id  = "AllowApiGatewayInvokeAuthToken"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.auth_token.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http_api.execution_arn}/*/*"
}

resource "aws_lambda_permission" "download_artifacts_zip" {
  statement_id  = "AllowApiGatewayInvokeArtifactsZip"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.download_artifacts_zip.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http_api.execution_arn}/*/*"
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

resource "aws_cloudfront_origin_access_control" "frontend" {
  name                              = "${local.name_prefix}-frontend"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_function" "spa_rewrite" {
  name    = "${local.name_prefix}-spa-rewrite"
  runtime = "cloudfront-js-1.0"
  comment = "Rewrite /app/* SPA routes to /app/index.html"
  publish = true
  code = <<EOF
function handler(event) {
  var request = event.request;
  var uri = request.uri;
  if (uri === "/app" || uri === "/app/") {
    request.uri = "/app/index.html";
    return request;
  }
  if (uri.startsWith("/app/") && uri.indexOf(".") === -1) {
    request.uri = "/app/index.html";
  }
  return request;
}
EOF
}

resource "aws_acm_certificate" "frontend" {
  provider          = aws.us_east_1
  count             = var.frontend_domain == "" ? 0 : 1
  domain_name       = var.frontend_domain
  validation_method = "DNS"
  subject_alternative_names = var.frontend_aliases
}

resource "aws_cloudfront_distribution" "frontend" {
  enabled             = true
  is_ipv6_enabled     = true
  comment             = "${local.name_prefix} frontend"
  default_root_object = "index.html"
  price_class         = var.frontend_price_class
  aliases             = local.frontend_aliases

  origin {
    domain_name              = aws_s3_bucket.frontend.bucket_regional_domain_name
    origin_id                = "frontend-s3"
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend.id
  }

  default_cache_behavior {
    allowed_methods  = ["GET", "HEAD", "OPTIONS"]
    cached_methods   = ["GET", "HEAD", "OPTIONS"]
    target_origin_id = "frontend-s3"
    viewer_protocol_policy = "redirect-to-https"
    cache_policy_id  = "658327ea-f89d-4fab-a63d-7e88639e58f6"
    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.spa_rewrite.arn
    }
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn            = var.frontend_domain == "" ? null : aws_acm_certificate.frontend[0].arn
    cloudfront_default_certificate = var.frontend_domain == "" ? true : false
    ssl_support_method             = var.frontend_domain == "" ? null : "sni-only"
    minimum_protocol_version       = "TLSv1.2_2021"
  }

  depends_on = [
    aws_s3_bucket_public_access_block.frontend,
  ]
}

resource "aws_s3_bucket_policy" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Sid = "AllowCloudFrontServiceRead",
        Effect = "Allow",
        Principal = {
          Service = "cloudfront.amazonaws.com"
        },
        Action = ["s3:GetObject"],
        Resource = "${aws_s3_bucket.frontend.arn}/*",
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = aws_cloudfront_distribution.frontend.arn
          }
        }
      }
    ]
  })
}
