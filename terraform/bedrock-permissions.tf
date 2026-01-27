# AWS Bedrock Model Access and Permissions
# Configuration for foundation models used by LLM system

# Note: Bedrock model access must be manually enabled in AWS Console first
# Navigate to: AWS Console → Bedrock → Model access → Request access
# Models needed: Claude 3.7 Sonnet, Amazon Nova, Cohere Command R+

# Note: Terraform cannot programmatically request Bedrock model access
# Model access must be enabled manually in AWS Console before deployment
# 
# To verify model access after manual enablement, use AWS CLI:
# aws bedrock list-foundation-models --region us-east-1 --query "modelSummaries[?contains(modelId, 'claude-3-7')]"
#
# Or check in AWS Console: Bedrock → Model access

# IAM Policy Document for Bedrock Access (already included in lambda-llm.tf)
# This file serves as documentation of required Bedrock permissions

# Required Model IDs (for reference):
# - anthropic.claude-3-7-sonnet-20240229-v1:0 (Primary)
# - amazon.nova-pro-v1:0 (Fallback)
# - cohere.command-r-plus-v1:0 (Alternative)

# Manual Steps Required Before Deployment:
# 1. Log into AWS Console
# 2. Navigate to: Bedrock → Model access
# 3. Click "Request model access" or "Manage model access"
# 4. Enable the following models:
#    - Anthropic Claude 3.7 Sonnet
#    - Amazon Nova Pro
#    - Cohere Command R+
# 5. Wait for access approval (typically instant for Nova, may take time for Claude/Cohere)
# 6. Verify access is granted before running terraform apply

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
