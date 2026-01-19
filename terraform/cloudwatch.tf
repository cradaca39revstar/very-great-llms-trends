# CloudWatch Alarms and Monitoring for Beauty Products Data Lake

# SNS Topic for alerts
resource "aws_sns_topic" "alerts" {
  name = "beauty-products-alerts"
  
  tags = {
    Name        = "Beauty Products Data Lake Alerts"
    Environment = var.environment
    Project     = "BeautyProductsDataLake"
  }
}

# SNS Topic subscription (email)
resource "aws_sns_topic_subscription" "email_alert" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# CloudWatch Log Group for Glue job
resource "aws_cloudwatch_log_group" "glue_job" {
  name              = "/aws-glue/jobs/${aws_glue_job.beauty_products_etl.name}"
  retention_in_days = 30
  
  tags = {
    Name        = "Glue Job Logs - Beauty Products"
    Environment = var.environment
    Project     = "BeautyProductsDataLake"
  }
}

# Alarm for Glue job failures
resource "aws_cloudwatch_metric_alarm" "job_failure" {
  alarm_name          = "beauty-products-job-failure"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "glue.driver.aggregate.numFailedTasks"
  namespace           = "Glue"
  period              = "300"
  statistic           = "Sum"
  threshold           = "0"
  alarm_description   = "Alert when Glue ETL job fails"
  treat_missing_data  = "notBreaching"
  
  dimensions = {
    JobName = aws_glue_job.beauty_products_etl.name
  }
  
  alarm_actions = [aws_sns_topic.alerts.arn]
  
  tags = {
    Name        = "Beauty Products Job Failure Alarm"
    Environment = var.environment
    Project     = "BeautyProductsDataLake"
  }
}

# Custom metric filter for low data quality
resource "aws_cloudwatch_log_metric_filter" "low_quality" {
  name           = "beauty-products-low-quality"
  log_group_name = aws_cloudwatch_log_group.glue_job.name
  pattern        = "[timestamp, requestid, level, message = \"*QUALITY_SCORE_LOW*\"]"
  
  metric_transformation {
    name      = "LowQualityScoreCount"
    namespace = "BeautyProducts/DataQuality"
    value     = "1"
  }
}

# Alarm for low data quality average
resource "aws_cloudwatch_metric_alarm" "low_quality" {
  alarm_name          = "beauty-products-low-quality"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "LowQualityScoreCount"
  namespace           = "BeautyProducts/DataQuality"
  period              = "3600"
  statistic           = "Average"
  threshold           = "0.80"
  alarm_description   = "Alert when average data quality score drops below 0.80"
  treat_missing_data  = "notBreaching"
  
  alarm_actions = [aws_sns_topic.alerts.arn]
  
  tags = {
    Name        = "Beauty Products Low Quality Alarm"
    Environment = var.environment
    Project     = "BeautyProductsDataLake"
  }
}

# Custom metric filter for high error rate
resource "aws_cloudwatch_log_metric_filter" "high_error_rate" {
  name           = "beauty-products-high-error-rate"
  log_group_name = aws_cloudwatch_log_group.glue_job.name
  pattern        = "[timestamp, requestid, level, message = \"*ERROR_RATE_HIGH*\"]"
  
  metric_transformation {
    name      = "HighErrorRateCount"
    namespace = "BeautyProducts/DataQuality"
    value     = "1"
  }
}

# Alarm for high error rate
resource "aws_cloudwatch_metric_alarm" "high_error_rate" {
  alarm_name          = "beauty-products-high-error-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "HighErrorRateCount"
  namespace           = "BeautyProducts/DataQuality"
  period              = "3600"
  statistic           = "Sum"
  threshold           = "5"
  alarm_description   = "Alert when error record count exceeds 5% of total"
  treat_missing_data  = "notBreaching"
  
  alarm_actions = [aws_sns_topic.alerts.arn]
  
  tags = {
    Name        = "Beauty Products High Error Rate Alarm"
    Environment = var.environment
    Project     = "BeautyProductsDataLake"
  }
}

# CloudWatch Dashboard
resource "aws_cloudwatch_dashboard" "pipeline_metrics" {
  dashboard_name = "beauty-products-pipeline-metrics"
  
  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/Glue", "glue.driver.aggregate.numCompletedTasks", { stat = "Sum", label = "Completed Tasks" }],
            [".", "glue.driver.aggregate.numFailedTasks", { stat = "Sum", label = "Failed Tasks" }]
          ]
          period = 300
          stat   = "Sum"
          region = data.aws_region.current.name
          title  = "Glue Job Task Status"
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            ["BeautyProducts/DataQuality", "LowQualityScoreCount", { stat = "Average" }]
          ]
          period = 3600
          stat   = "Average"
          region = data.aws_region.current.name
          title  = "Data Quality Score Trend"
        }
      },
      {
        type = "log"
        properties = {
          query   = <<-EOT
            SOURCE '${aws_cloudwatch_log_group.glue_job.name}'
            | fields @timestamp, @message
            | filter @message like /ERROR/
            | sort @timestamp desc
            | limit 20
          EOT
          region  = data.aws_region.current.name
          title   = "Recent Errors"
        }
      }
    ]
  })
}
