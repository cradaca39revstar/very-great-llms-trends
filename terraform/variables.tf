# Variables for Beauty Products Data Lake Infrastructure

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "poc"
}

variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-east-1"
}

variable "alert_email" {
  description = "Email address for CloudWatch alerts"
  type        = string
  default     = "data-team@example.com"
}

variable "alert_phone_number" {
  description = "Phone number for SMS alerts (optional)"
  type        = string
  default     = ""
}

variable "project_name" {
  description = "Project name for tagging"
  type        = string
  default     = "BeautyProductsDataLake"
}

variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}

# =============================================================================
# LLM TRENDING PRODUCTS SYSTEM VARIABLES
# =============================================================================

variable "enable_llm_system" {
  description = "Enable LLM Trending Products Report Generator system"
  type        = bool
  default     = true
}

variable "cognito_domain_prefix" {
  description = "Cognito domain prefix for hosted UI (must be unique across AWS)"
  type        = string
  default     = "beauty-products-trending"
}

variable "lambda_memory_size" {
  description = "Lambda memory size in MB for LLM orchestrator"
  type        = number
  default     = 1024
  validation {
    condition     = var.lambda_memory_size >= 512 && var.lambda_memory_size <= 10240
    error_message = "Lambda memory must be between 512 and 10240 MB."
  }
}

variable "lambda_timeout" {
  description = "Lambda timeout in seconds for LLM orchestrator"
  type        = number
  default     = 60
  validation {
    condition     = var.lambda_timeout >= 30 && var.lambda_timeout <= 900
    error_message = "Lambda timeout must be between 30 and 900 seconds."
  }
}

variable "bedrock_primary_model" {
  description = "Primary Bedrock model ID for AI generation"
  type        = string
  default     = "anthropic.claude-3-7-sonnet-20240229-v1:0"
}

variable "bedrock_fallback_model" {
  description = "Fallback Bedrock model ID for AI generation"
  type        = string
  default     = "amazon.nova-pro-v1:0"
}

variable "pdf_expiration_days" {
  description = "Number of days before PDF reports are automatically deleted"
  type        = number
  default     = 7
  validation {
    condition     = var.pdf_expiration_days >= 1 && var.pdf_expiration_days <= 365
    error_message = "PDF expiration must be between 1 and 365 days."
  }
}

variable "knowledge_base_id" {
  description = "Optional Bedrock Knowledge Base ID for product URL/image retrieval (Option A)"
  type        = string
  default     = ""
}

variable "brave_search_api_key" {
  description = "Optional Brave Search API key for scraper URL discovery (free tier: 2000 queries/month). When set, used before DuckDuckGo/Google/Bedrock."
  type        = string
  default     = ""
  sensitive   = true
}

variable "enable_scraper_lambda" {
  description = "Enable scraper Lambda (V2 uses AI-generated products + Titan images; set to false to disable legacy scraper)."
  type        = bool
  default     = false
}
