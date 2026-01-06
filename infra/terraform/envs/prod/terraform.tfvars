environment = "prod"

# Cognito Hosted UI configuration
cognito_domain        = "skybridge-prod"
cognito_callback_urls = ["https://skybridge.example.com/auth/callback"]
cognito_logout_urls   = ["https://skybridge.example.com/"]

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
