# DynamoDB Table for LLM Prompt Logging and Audit Trail
# Stores all user queries, prompts, responses, and execution metadata

resource "aws_dynamodb_table" "prompt_logs" {
  count = var.enable_llm_system ? 1 : 0

  name           = "beauty-products-prompt-logs-${var.environment}"
  billing_mode   = "PAY_PER_REQUEST" # On-demand pricing
  hash_key       = "request_id"
  range_key      = "timestamp"

  # Primary key attributes
  attribute {
    name = "request_id"
    type = "S" # String - UUID
  }

  attribute {
    name = "timestamp"
    type = "S" # String - ISO 8601 format
  }

  attribute {
    name = "user_id"
    type = "S" # String - User identifier from Cognito
  }

  # Global Secondary Index for querying by user
  global_secondary_index {
    name            = "user_id-index"
    hash_key        = "user_id"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  # Enable point-in-time recovery
  point_in_time_recovery {
    enabled = true
  }

  # Server-side encryption (AWS-managed keys)
  server_side_encryption {
    enabled = true
  }

  # TTL for automatic deletion (optional - 90 days)
  ttl {
    attribute_name = "ttl_expiry"
    enabled        = true
  }

  tags = {
    Name        = "prompt-logs-${var.environment}"
    Component   = "LLM-TrendingProducts"
    Environment = var.environment
    Purpose     = "AuditTrail"
  }
}

# CloudWatch Alarm for DynamoDB throttling
resource "aws_cloudwatch_metric_alarm" "dynamodb_throttle" {
  count = var.enable_llm_system ? 1 : 0

  alarm_name          = "beauty-products-llm-dynamodb-throttle-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "UserErrors"
  namespace           = "AWS/DynamoDB"
  period              = "300"
  statistic           = "Sum"
  threshold           = "5"
  alarm_description   = "DynamoDB prompt logs table is being throttled"
  treat_missing_data  = "notBreaching"

  dimensions = {
    TableName = aws_dynamodb_table.prompt_logs[0].name
  }

  alarm_actions = [] # Will be populated if SNS topic exists

  tags = {
    Name        = "dynamodb-throttle-alarm-${var.environment}"
    Component   = "LLM-TrendingProducts"
    Environment = var.environment
  }
}
