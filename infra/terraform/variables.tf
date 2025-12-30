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
