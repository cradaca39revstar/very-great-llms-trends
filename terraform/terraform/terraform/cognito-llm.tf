# AWS Cognito User Pool for LLM Trending Products System
# Authentication and authorization for chatbot users

resource "aws_cognito_user_pool" "llm" {
  count = var.enable_llm_system ? 1 : 0

  name = "beauty-products-trending-users-${var.environment}"

  # Username configuration
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  # Password policy
  password_policy {
    minimum_length                   = 8
    require_uppercase                = true
    require_lowercase                = true
    require_numbers                  = true
    require_symbols                  = true
    temporary_password_validity_days = 7
  }

  # Email verification
  verification_message_template {
    default_email_option = "CONFIRM_WITH_CODE"
    email_subject        = "Your Beauty Products Trending Reports verification code"
    email_message        = "Your verification code is {####}"
  }

  # Account recovery
  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  # User attributes
  schema {
    attribute_data_type      = "String"
    name                     = "email"
    required                 = true
    mutable                  = true
    developer_only_attribute = false

    string_attribute_constraints {
      min_length = 1
      max_length = 256
    }
  }

  # MFA configuration (optional, disabled by default)
  mfa_configuration = "OFF"

  # Email configuration
  email_configuration {
    email_sending_account = "COGNITO_DEFAULT"
  }

  # Advanced security (optional)
  user_pool_add_ons {
    advanced_security_mode = "AUDIT"
  }

  tags = {
    Name        = "beauty-products-trending-users-${var.environment}"
    Component   = "LLM-TrendingProducts"
    Environment = var.environment
  }
}

# Cognito User Pool Client for API Gateway
resource "aws_cognito_user_pool_client" "llm" {
  count = var.enable_llm_system ? 1 : 0

  name         = "beauty-products-trending-client-${var.environment}"
  user_pool_id = aws_cognito_user_pool.llm[0].id

  # Token configuration
  access_token_validity  = 1 # 1 hour
  id_token_validity      = 1 # 1 hour
  refresh_token_validity = 30 # 30 days

  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }

  # OAuth configuration
  generate_secret = false # For web/mobile clients
  explicit_auth_flows = [
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
    "ALLOW_USER_SRP_AUTH"
  ]

  # Prevent user existence errors
  prevent_user_existence_errors = "ENABLED"

  # Read and write attributes
  read_attributes = [
    "email",
    "email_verified"
  ]

  write_attributes = [
    "email"
  ]
}

# Cognito User Pool Domain (optional - for hosted UI)
resource "aws_cognito_user_pool_domain" "llm" {
  count = var.enable_llm_system ? 1 : 0

  domain       = "${var.cognito_domain_prefix}-${var.environment}"
  user_pool_id = aws_cognito_user_pool.llm[0].id
}

# Outputs for reference
output "cognito_user_pool_endpoint" {
  description = "Cognito User Pool endpoint"
  value       = var.enable_llm_system ? aws_cognito_user_pool.llm[0].endpoint : null
}

output "cognito_user_pool_arn" {
  description = "Cognito User Pool ARN"
  value       = var.enable_llm_system ? aws_cognito_user_pool.llm[0].arn : null
}
