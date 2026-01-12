environment = "prod"
aws_region  = "eu-west-1"

# CORS origins for the API (production SPA)
api_cors_origins = ["https://skybridge.inspirespace.co"]
frontend_domain  = "skybridge.inspirespace.co"

# Worker token shared by API + worker Lambda (set via tfvars or CI secrets)
backend_worker_token = "REPLACE_ME"

# Cognito Hosted UI configuration
cognito_domain        = "skybridge-inspirespace"
cognito_callback_urls = ["https://skybridge.inspirespace.co/auth/callback"]
cognito_logout_urls   = ["https://skybridge.inspirespace.co/"]

# Enable IdPs by name (match Cognito provider names)
# cognito_identity_providers = ["Google", "Facebook", "SignInWithApple"]

# Provider credentials (set via tfvars or CI secrets)
# google_client_id = ""
# google_client_secret = ""
# facebook_client_id = ""
# facebook_client_secret = ""
# apple_client_id = ""
# apple_team_id = ""
# apple_key_id = ""
# apple_private_key = ""
