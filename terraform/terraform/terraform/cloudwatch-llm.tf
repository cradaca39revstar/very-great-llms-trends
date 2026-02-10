# CloudWatch Dashboard and Alarms for LLM Trending Products System
# Monitoring for API Gateway, Lambda, Bedrock, and custom metrics

# ==============================================================================
# CLOUDWATCH DASHBOARD
# ==============================================================================

resource "aws_cloudwatch_dashboard" "llm_metrics" {
  count = var.enable_llm_system ? 1 : 0

  dashboard_name = "beauty-products-llm-trending-metrics-${var.environment}"

  dashboard_body = jsonencode({
    widgets = [
      # Request Volume
      {
        type = "metric"
        properties = {
          metrics = [
            ["BeautyProducts/LLM", "TrendingReportRequests", { stat = "Sum", label = "Total Requests" }],
            ["...", { stat = "Sum", label = "Successful" }],
            ["AWS/Lambda", "Errors", { stat = "Sum", label = "Failed" }]
          ]
          period  = 3600
          stat    = "Sum"
          region  = var.aws_region
          title   = "Request Volume (Hourly)"
          yAxis   = { left = { min = 0 } }
        }
      },
      # Average Latency
      {
        type = "metric"
        properties = {
          metrics = [
            ["BeautyProducts/LLM", "TotalReportDuration", { stat = "Average", label = "Avg Latency" }],
            ["...", { stat = "p95", label = "P95 Latency" }],
            [{ expression = "25000", label = "Target (25s)", color = "#2ca02c" }]
          ]
          period  = 300
          stat    = "Average"
          region  = var.aws_region
          title   = "Average Latency (ms)"
          yAxis   = { left = { min = 0 } }
          annotations = {
            horizontal = [{
              value = 30000
              label = "Alert Threshold"
              color = "#d62728"
            }]
          }
        }
      },
      # Latency Breakdown
      {
        type = "metric"
        properties = {
          metrics = [
            ["BeautyProducts/LLM", "AthenaQueryDuration", { stat = "Average", label = "Athena" }],
            [".", "BedrockCallDuration", { stat = "Average", label = "Bedrock" }],
            [".", "PDFGenerationDuration", { stat = "Average", label = "PDF Gen" }]
          ]
          period  = 300
          stat    = "Average"
          region  = var.aws_region
          title   = "Latency Breakdown (ms)"
          yAxis   = { left = { min = 0 } }
          view    = "timeSeries"
          stacked = true
        }
      },
      # Error Rate
      {
        type = "metric"
        properties = {
          metrics = [
            [{ expression = "(m2/m1)*100", label = "Error Rate %", id = "e1" }],
            ["BeautyProducts/LLM", "TrendingReportRequests", { id = "m1", visible = false }],
            ["AWS/Lambda", "Errors", { id = "m2", visible = false }]
          ]
          period  = 300
          stat    = "Sum"
          region  = var.aws_region
          title   = "Error Rate (%)"
          yAxis   = { left = { min = 0, max = 10 } }
          annotations = {
            horizontal = [{
              value = 5
              label = "Alert Threshold (5%)"
              color = "#d62728"
            }]
          }
        }
      },
      # Concurrent Executions
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/Lambda", "ConcurrentExecutions", { stat = "Maximum", label = "Current" }],
            [{ expression = "100", label = "Reserved Limit", color = "#ff7f0e" }]
          ]
          period  = 60
          stat    = "Maximum"
          region  = var.aws_region
          title   = "Lambda Concurrent Executions"
          yAxis   = { left = { min = 0 } }
        }
      },
      # Bedrock Model Usage
      {
        type = "metric"
        properties = {
          metrics = [
            ["BeautyProducts/LLM", "ClaudeInvocations", { stat = "Sum", label = "Claude 3.7" }],
            [".", "NovaInvocations", { stat = "Sum", label = "Nova" }],
            [".", "CohereInvocations", { stat = "Sum", label = "Cohere" }]
          ]
          period  = 3600
          stat    = "Sum"
          region  = var.aws_region
          title   = "Bedrock Model Usage (Hourly)"
          view    = "pie"
        }
      },
      # API Gateway Metrics
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/ApiGateway", "Count", { stat = "Sum", label = "Requests" }],
            [".", "4XXError", { stat = "Sum", label = "4XX Errors" }],
            [".", "5XXError", { stat = "Sum", label = "5XX Errors" }]
          ]
          period  = 300
          stat    = "Sum"
          region  = var.aws_region
          title   = "API Gateway Metrics"
          yAxis   = { left = { min = 0 } }
        }
      },
      # Lambda Duration vs Timeout
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/Lambda", "Duration", { stat = "Average", label = "Avg Duration" }],
            ["...", { stat = "Maximum", label = "Max Duration" }],
            [{ expression = "60000", label = "Timeout Limit", color = "#d62728" }]
          ]
          period  = 300
          stat    = "Average"
          region  = var.aws_region
          title   = "Lambda Duration vs Timeout (ms)"
          yAxis   = { left = { min = 0 } }
        }
      }
    ]
  })
}

# ==============================================================================
# CLOUDWATCH ALARMS
# ==============================================================================

# Alarm 1: High Latency (WARNING)
resource "aws_cloudwatch_metric_alarm" "high_latency" {
  count = var.enable_llm_system ? 1 : 0

  alarm_name          = "beauty-products-llm-high-latency-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "3"
  metric_name         = "TotalReportDuration"
  namespace           = "BeautyProducts/LLM"
  period              = "300" # 5 minutes
  statistic           = "Average"
  threshold           = "30000" # 30 seconds
  alarm_description   = "LLM system average latency exceeds 30 seconds"
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]

  tags = {
    Name        = "llm-high-latency-${var.environment}"
    Component   = "LLM-TrendingProducts"
    Environment = var.environment
    Severity    = "WARNING"
  }
}

# Alarm 2: High Error Rate (CRITICAL)
resource "aws_cloudwatch_metric_alarm" "high_error_rate" {
  count = var.enable_llm_system ? 1 : 0

  alarm_name          = "beauty-products-llm-high-error-rate-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  threshold           = "5" # 5%
  alarm_description   = "LLM system error rate exceeds 5%"
  treat_missing_data  = "notBreaching"

  metric_query {
    id          = "error_rate"
    expression  = "(errors/requests)*100"
    label       = "Error Rate %"
    return_data = true
  }

  metric_query {
    id = "errors"
    metric {
      metric_name = "Errors"
      namespace   = "AWS/Lambda"
      period      = 300
      stat        = "Sum"
      dimensions = {
        FunctionName = aws_lambda_function.orchestrator[0].function_name
      }
    }
    return_data = false
  }

  metric_query {
    id = "requests"
    metric {
      metric_name = "Invocations"
      namespace   = "AWS/Lambda"
      period      = 300
      stat        = "Sum"
      dimensions = {
        FunctionName = aws_lambda_function.orchestrator[0].function_name
      }
    }
    return_data = false
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]

  tags = {
    Name        = "llm-high-error-rate-${var.environment}"
    Component   = "LLM-TrendingProducts"
    Environment = var.environment
    Severity    = "CRITICAL"
  }
}

# Alarm 3: Bedrock Throttling (CRITICAL)
resource "aws_cloudwatch_metric_alarm" "bedrock_throttling" {
  count = var.enable_llm_system ? 1 : 0

  alarm_name          = "beauty-products-llm-bedrock-throttling-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "BedrockThrottledRequests"
  namespace           = "BeautyProducts/LLM"
  period              = "300" # 5 minutes
  statistic           = "Sum"
  threshold           = "20"
  alarm_description   = "Bedrock API throttling detected (>20 throttles in 5 minutes)"
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]

  tags = {
    Name        = "llm-bedrock-throttling-${var.environment}"
    Component   = "LLM-TrendingProducts"
    Environment = var.environment
    Severity    = "CRITICAL"
  }
}

# Alarm 4: Lambda Function Errors (CRITICAL)
resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  count = var.enable_llm_system ? 1 : 0

  alarm_name          = "beauty-products-llm-lambda-errors-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Sum"
  threshold           = "10"
  alarm_description   = "Lambda function has more than 10 errors in 5 minutes"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.orchestrator[0].function_name
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]

  tags = {
    Name        = "llm-lambda-errors-${var.environment}"
    Component   = "LLM-TrendingProducts"
    Environment = var.environment
    Severity    = "CRITICAL"
  }
}

# Alarm 5: Lambda Concurrent Execution Near Limit (WARNING)
resource "aws_cloudwatch_metric_alarm" "lambda_concurrent_high" {
  count = var.enable_llm_system ? 1 : 0

  alarm_name          = "beauty-products-llm-high-concurrency-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "ConcurrentExecutions"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Maximum"
  threshold           = "80" # 80% of reserved 100
  alarm_description   = "Lambda concurrent executions approaching limit"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.orchestrator[0].function_name
  }

  alarm_actions = [aws_sns_topic.alerts.arn]

  tags = {
    Name        = "llm-high-concurrency-${var.environment}"
    Component   = "LLM-TrendingProducts"
    Environment = var.environment
    Severity    = "WARNING"
  }
}

# Alarm 6: API Gateway 5XX Errors (WARNING)
resource "aws_cloudwatch_metric_alarm" "api_gateway_5xx" {
  count = var.enable_llm_system ? 1 : 0

  alarm_name          = "beauty-products-llm-api-5xx-errors-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "5XXError"
  namespace           = "AWS/ApiGateway"
  period              = "300"
  statistic           = "Sum"
  threshold           = "5"
  alarm_description   = "API Gateway returning 5XX errors"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ApiName = aws_api_gateway_rest_api.llm[0].name
  }

  alarm_actions = [aws_sns_topic.alerts.arn]

  tags = {
    Name        = "llm-api-5xx-errors-${var.environment}"
    Component   = "LLM-TrendingProducts"
    Environment = var.environment
    Severity    = "WARNING"
  }
}
