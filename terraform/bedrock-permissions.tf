# AWS Bedrock Model Access and Permissions
# Configuration for foundation models used by LLM system

# IMPORTANT UPDATE (January 2026):
# The "Model access" page in AWS Console has been retired.
# Serverless foundation models are now automatically enabled when first invoked.
# No manual activation is required for most models.

# EXCEPTION FOR ANTHROPIC MODELS:
# For Anthropic models (including Claude 3.7 Sonnet), first-time users may need
# to submit use case details before accessing the model. This typically happens
# when you first invoke the model via API or in the Bedrock Playground.

# Required Model IDs (for reference):
# - anthropic.claude-3-7-sonnet-20240229-v1:0 (Primary)
# - amazon.nova-pro-v1:0 (Fallback)
# - cohere.command-r-plus-v1:0 (Alternative)

# How Model Access Works Now:
# 1. Models are automatically enabled when first invoked in your account
# 2. For Anthropic models, you may be prompted to provide use case details
#    when accessing via Bedrock Playground or API for the first time
# 3. Account administrators can control access via IAM policies and
#    Service Control Policies (SCPs) if needed

# To verify available models, use AWS CLI:
# aws bedrock list-foundation-models --region us-east-1 --query "modelSummaries[?contains(modelId, 'claude-3-7') || contains(modelId, 'nova-pro') || contains(modelId, 'command-r-plus')]"

# To test model access (will auto-enable if not already enabled):
# 1. Use Bedrock Playground in AWS Console: https://console.aws.amazon.com/bedrock/
# 2. Select a model from Model catalog
# 3. For Anthropic models, you may be prompted to provide use case details
# 4. Once enabled, the model is available account-wide

# IAM Policy Document for Bedrock Access (already included in lambda-llm.tf)
# This file serves as documentation of required Bedrock permissions

# Note: If you need Bedrock Knowledge Bases for web search:
# You'll need to create a Knowledge Base manually or via additional Terraform resources
# Knowledge Base with web search connector is region-specific and may not be available in all regions

# Bedrock Guardrails (Optional - Uncomment to enable)
# resource "aws_bedrock_guardrail" "content_filter" {
#   count = var.enable_llm_system ? 1 : 0
#
#   name        = "beauty-products-content-filter-${var.environment}"
#   description = "Content filtering for LLM trending products"
#
#   content_policy_config {
#     filters_config {
#       type     = "HATE"
#       input_strength  = "HIGH"
#       output_strength = "HIGH"
#     }
#     filters_config {
#       type     = "VIOLENCE"
#       input_strength  = "MEDIUM"
#       output_strength = "MEDIUM"
#     }
#     filters_config {
#       type     = "SEXUAL"
#       input_strength  = "HIGH"
#       output_strength = "HIGH"
#     }
#   }
#
#   blocked_input_messaging  = "I cannot process this request due to content policy."
#   blocked_outputs_messaging = "I cannot generate this response due to content policy."
#
#   tags = {
#     Name        = "content-filter-${var.environment}"
#     Component   = "LLM-TrendingProducts"
#     Environment = var.environment
#   }
# }

# CloudWatch Log Group for Bedrock invocations (optional)
resource "aws_cloudwatch_log_group" "bedrock_logs" {
  count = var.enable_llm_system ? 1 : 0

  name              = "/aws/bedrock/model-invocations-${var.environment}"
  retention_in_days = 30

  tags = {
    Name        = "bedrock-logs-${var.environment}"
    Component   = "LLM-TrendingProducts"
    Environment = var.environment
  }
}
