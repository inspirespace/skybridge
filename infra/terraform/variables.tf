variable "project_name" {
  description = "Project name prefix for resources."
  type        = string
  default     = "skybridge"
}

variable "environment" {
  description = "Deployment environment (dev/staging/prod)."
  type        = string
}

variable "aws_region" {
  description = "AWS region for deployment."
  type        = string
  default     = "us-east-1"
}

variable "tags" {
  description = "Tags applied to all supported resources."
  type        = map(string)
  default     = {}
}

variable "cognito_domain" {
  description = "Cognito hosted UI domain prefix (optional)."
  type        = string
  default     = ""
}

variable "cognito_callback_urls" {
  description = "OAuth callback URLs for Cognito app client."
  type        = list(string)
  default     = []
}

variable "cognito_logout_urls" {
  description = "OAuth logout URLs for Cognito app client."
  type        = list(string)
  default     = []
}

variable "cognito_identity_providers" {
  description = "Enabled identity providers for the Cognito app client."
  type        = list(string)
  default     = []
}

variable "google_client_id" {
  description = "Google OAuth client ID for Cognito IdP."
  type        = string
  default     = ""
}

variable "google_client_secret" {
  description = "Google OAuth client secret for Cognito IdP."
  type        = string
  default     = ""
  sensitive   = true
}

variable "facebook_client_id" {
  description = "Facebook OAuth client ID for Cognito IdP."
  type        = string
  default     = ""
}

variable "facebook_client_secret" {
  description = "Facebook OAuth client secret for Cognito IdP."
  type        = string
  default     = ""
  sensitive   = true
}

variable "apple_client_id" {
  description = "Apple Services ID for Cognito IdP."
  type        = string
  default     = ""
}

variable "apple_team_id" {
  description = "Apple Team ID for Cognito IdP."
  type        = string
  default     = ""
}

variable "apple_key_id" {
  description = "Apple Key ID for Cognito IdP."
  type        = string
  default     = ""
}

variable "apple_private_key" {
  description = "Apple private key for Cognito IdP."
  type        = string
  default     = ""
  sensitive   = true
}
