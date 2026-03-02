# AWS Bedrock Model Access and Permissions
# Configuration for foundation models used by LLM system

# UPDATE (January 2026):
# The system uses Amazon Nova Pro (amazon.nova-pro-v1:0) in us-east-1 only.
# Serverless foundation models are automatically enabled when first invoked.
# No manual activation is required.

# Model in Use:
# - amazon.nova-pro-v1:0 (Primary and fallback; us-east-1 only)
# Why Nova Pro: AWS Bedrock now requires inference profiles for newer Claude
# models (3.5/4/4.5), which route traffic across regions. Using Nova Pro with
# direct foundation model ID keeps all inference in us-east-1.

# To verify model availability:
# aws bedrock list-foundation-models --region us-east-1 --query "modelSummaries[?modelId=='amazon.nova-pro-v1:0']"

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
