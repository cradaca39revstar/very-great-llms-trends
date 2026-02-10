# CloudWatch Alarms and Monitoring for Beauty Products Data Lake
# Enhanced with structured JSON logging support and custom metrics

# =============================================================================
# SNS TOPICS AND SUBSCRIPTIONS
# =============================================================================

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

# =============================================================================
# CLOUDWATCH LOG GROUPS
# =============================================================================

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

# =============================================================================
# METRIC FILTERS FOR STRUCTURED JSON LOGS
# =============================================================================

# Metric filter for data changes (traceability requirement)
resource "aws_cloudwatch_log_metric_filter" "data_changes" {
  name           = "beauty-products-data-changes"
  log_group_name = aws_cloudwatch_log_group.glue_job.name
  pattern        = "{ $.event_type = \"DATA_CHANGE\" }"
  
  metric_transformation {
    name          = "DataChangeCount"
    namespace     = "BeautyProducts/DataChanges"
    value         = "1"
    default_value = "0"
  }
}

# Metric filter for errors (structured JSON format)
resource "aws_cloudwatch_log_metric_filter" "errors" {
  name           = "beauty-products-errors"
  log_group_name = aws_cloudwatch_log_group.glue_job.name
  pattern        = "{ $.level = \"ERROR\" }"
  
  metric_transformation {
    name          = "ErrorCount"
    namespace     = "BeautyProducts/DataQuality"
    value         = "1"
    default_value = "0"
  }
}

# Metric filter for quality alerts (structured JSON format)
resource "aws_cloudwatch_log_metric_filter" "quality_alerts" {
  name           = "beauty-products-quality-alerts"
  log_group_name = aws_cloudwatch_log_group.glue_job.name
  pattern        = "{ $.event_type = \"QUALITY_ALERT\" }"
  
  metric_transformation {
    name          = "QualityAlertCount"
    namespace     = "BeautyProducts/DataQuality"
    value         = "1"
    default_value = "0"
  }
}

# Metric filter for low quality score alert
resource "aws_cloudwatch_log_metric_filter" "low_quality" {
  name           = "beauty-products-low-quality"
  log_group_name = aws_cloudwatch_log_group.glue_job.name
  pattern        = "{ $.event_type = \"QUALITY_ALERT\" && $.details.alert_type = \"QUALITY_SCORE_LOW\" }"
  
  metric_transformation {
    name          = "LowQualityScoreCount"
    namespace     = "BeautyProducts/DataQuality"
    value         = "1"
    default_value = "0"
  }
}

# Metric filter for high error rate alert
resource "aws_cloudwatch_log_metric_filter" "high_error_rate" {
  name           = "beauty-products-high-error-rate"
  log_group_name = aws_cloudwatch_log_group.glue_job.name
  pattern        = "{ $.event_type = \"QUALITY_ALERT\" && $.details.alert_type = \"ERROR_RATE_HIGH\" }"
  
  metric_transformation {
    name          = "HighErrorRateCount"
    namespace     = "BeautyProducts/DataQuality"
    value         = "1"
    default_value = "0"
  }
}

# Metric filter for job summaries
resource "aws_cloudwatch_log_metric_filter" "job_summaries" {
  name           = "beauty-products-job-summaries"
  log_group_name = aws_cloudwatch_log_group.glue_job.name
  pattern        = "{ $.event_type = \"JOB_SUMMARY\" }"
  
  metric_transformation {
    name          = "JobCompletionCount"
    namespace     = "BeautyProducts/ETL"
    value         = "1"
    default_value = "0"
  }
}

# Metric filter for ETL steps
resource "aws_cloudwatch_log_metric_filter" "etl_steps" {
  name           = "beauty-products-etl-steps"
  log_group_name = aws_cloudwatch_log_group.glue_job.name
  pattern        = "{ $.event_type = \"ETL_STEP\" }"
  
  metric_transformation {
    name          = "ETLStepCount"
    namespace     = "BeautyProducts/ETL"
    value         = "1"
    default_value = "0"
  }
}

# =============================================================================
# CLOUDWATCH ALARMS
# =============================================================================

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

# Alarm for low data quality (from custom metric)
resource "aws_cloudwatch_metric_alarm" "avg_quality_score_low" {
  alarm_name          = "beauty-products-avg-quality-score-low"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "AvgQualityScore"
  namespace           = "BeautyProducts/DataQuality"
  period              = "3600"
  statistic           = "Average"
  threshold           = "0.80"
  alarm_description   = "Alert when average data quality score drops below 0.80"
  treat_missing_data  = "notBreaching"
  
  dimensions = {
    JobName = aws_glue_job.beauty_products_etl.name
  }
  
  alarm_actions = [aws_sns_topic.alerts.arn]
  
  tags = {
    Name        = "Beauty Products Low Quality Score Alarm"
    Environment = var.environment
    Project     = "BeautyProductsDataLake"
  }
}

# Alarm for high error rate (from custom metric)
resource "aws_cloudwatch_metric_alarm" "error_rate_high" {
  alarm_name          = "beauty-products-error-rate-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "ErrorRate"
  namespace           = "BeautyProducts/DataQuality"
  period              = "3600"
  statistic           = "Average"
  threshold           = "5"
  alarm_description   = "Alert when error rate exceeds 5%"
  treat_missing_data  = "notBreaching"
  
  dimensions = {
    JobName = aws_glue_job.beauty_products_etl.name
  }
  
  alarm_actions = [aws_sns_topic.alerts.arn]
  
  tags = {
    Name        = "Beauty Products High Error Rate Alarm"
    Environment = var.environment
    Project     = "BeautyProductsDataLake"
  }
}

# Alarm for quality alerts from logs
resource "aws_cloudwatch_metric_alarm" "quality_alert" {
  alarm_name          = "beauty-products-quality-alert"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "QualityAlertCount"
  namespace           = "BeautyProducts/DataQuality"
  period              = "3600"
  statistic           = "Sum"
  threshold           = "0"
  alarm_description   = "Alert when quality degradation is detected"
  treat_missing_data  = "notBreaching"
  
  alarm_actions = [aws_sns_topic.alerts.arn]
  
  tags = {
    Name        = "Beauty Products Quality Alert Alarm"
    Environment = var.environment
    Project     = "BeautyProductsDataLake"
  }
}

# Alarm for errors from logs
resource "aws_cloudwatch_metric_alarm" "error_count" {
  alarm_name          = "beauty-products-error-count"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "ErrorCount"
  namespace           = "BeautyProducts/DataQuality"
  period              = "3600"
  statistic           = "Sum"
  threshold           = "10"
  alarm_description   = "Alert when error count exceeds 10 in an hour"
  treat_missing_data  = "notBreaching"
  
  alarm_actions = [aws_sns_topic.alerts.arn]
  
  tags = {
    Name        = "Beauty Products Error Count Alarm"
    Environment = var.environment
    Project     = "BeautyProductsDataLake"
  }
}

# =============================================================================
# CLOUDWATCH DASHBOARD (Enhanced)
# =============================================================================

resource "aws_cloudwatch_dashboard" "pipeline_metrics" {
  dashboard_name = "beauty-products-pipeline-metrics"
  
  dashboard_body = jsonencode({
    widgets = [
      # Row 1: Job Status Overview
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 8
        height = 6
        properties = {
          metrics = [
            ["AWS/Glue", "glue.driver.aggregate.numCompletedTasks", "JobName", aws_glue_job.beauty_products_etl.name, { stat = "Sum", label = "Completed Tasks", color = "#2ca02c" }],
            [".", "glue.driver.aggregate.numFailedTasks", ".", ".", { stat = "Sum", label = "Failed Tasks", color = "#d62728" }]
          ]
          period = 300
          stat   = "Sum"
          region = data.aws_region.current.name
          title  = "Glue Job Task Status"
          view   = "timeSeries"
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 0
        width  = 8
        height = 6
        properties = {
          metrics = [
            ["BeautyProducts/ETL", "JobCompletionCount", { stat = "Sum", label = "Jobs Completed", color = "#1f77b4" }]
          ]
          period = 3600
          stat   = "Sum"
          region = data.aws_region.current.name
          title  = "Job Completions (Hourly)"
          view   = "timeSeries"
        }
      },
      {
        type   = "metric"
        x      = 16
        y      = 0
        width  = 8
        height = 6
        properties = {
          metrics = [
            ["BeautyProducts/DataChanges", "DataChangeCount", { stat = "Sum", label = "Data Changes", color = "#9467bd" }]
          ]
          period = 3600
          stat   = "Sum"
          region = data.aws_region.current.name
          title  = "Data Changes Logged (Hourly)"
          view   = "timeSeries"
        }
      },
      
      # Row 2: Data Quality Metrics
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 8
        height = 6
        properties = {
          metrics = [
            ["BeautyProducts/DataQuality", "AvgQualityScore", "JobName", aws_glue_job.beauty_products_etl.name, { stat = "Average", label = "Avg Quality Score", color = "#2ca02c" }]
          ]
          period = 3600
          stat   = "Average"
          region = data.aws_region.current.name
          title  = "Average Quality Score"
          view   = "timeSeries"
          yAxis  = {
            left = {
              min = 0
              max = 1
            }
          }
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 6
        width  = 8
        height = 6
        properties = {
          metrics = [
            ["BeautyProducts/DataQuality", "PassRate", "JobName", aws_glue_job.beauty_products_etl.name, { stat = "Average", label = "Pass Rate %", color = "#1f77b4" }]
          ]
          period = 3600
          stat   = "Average"
          region = data.aws_region.current.name
          title  = "Pass Rate (%)"
          view   = "timeSeries"
          yAxis  = {
            left = {
              min = 0
              max = 100
            }
          }
        }
      },
      {
        type   = "metric"
        x      = 16
        y      = 6
        width  = 8
        height = 6
        properties = {
          metrics = [
            ["BeautyProducts/DataQuality", "ErrorRate", "JobName", aws_glue_job.beauty_products_etl.name, { stat = "Average", label = "Error Rate %", color = "#d62728" }]
          ]
          period = 3600
          stat   = "Average"
          region = data.aws_region.current.name
          title  = "Error Rate (%)"
          view   = "timeSeries"
          yAxis  = {
            left = {
              min = 0
              max = 20
            }
          }
        }
      },
      
      # Row 3: Record Counts
      {
        type   = "metric"
        x      = 0
        y      = 12
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["BeautyProducts/DataQuality", "RecordsPassed", "JobName", aws_glue_job.beauty_products_etl.name, { stat = "Sum", label = "Passed", color = "#2ca02c" }],
            [".", "RecordsWarned", ".", ".", { stat = "Sum", label = "Warned", color = "#ff7f0e" }],
            [".", "RecordsFailed", ".", ".", { stat = "Sum", label = "Failed", color = "#d62728" }],
            [".", "RecordsDuplicates", ".", ".", { stat = "Sum", label = "Duplicates", color = "#9467bd" }]
          ]
          period = 3600
          stat   = "Sum"
          region = data.aws_region.current.name
          title  = "Records by Quality Tier"
          view   = "timeSeries"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 12
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["BeautyProducts/DataQuality", "QualityAlertCount", { stat = "Sum", label = "Quality Alerts", color = "#d62728" }],
            [".", "ErrorCount", { stat = "Sum", label = "Errors", color = "#ff7f0e" }]
          ]
          period = 3600
          stat   = "Sum"
          region = data.aws_region.current.name
          title  = "Alerts and Errors"
          view   = "timeSeries"
        }
      },
      
      # Row 4: Logs
      {
        type   = "log"
        x      = 0
        y      = 18
        width  = 12
        height = 6
        properties = {
          query  = <<-EOT
            SOURCE '${aws_cloudwatch_log_group.glue_job.name}'
            | fields @timestamp, @message
            | parse @message '{"timestamp":"*","level":"*","domain":"*","job_run_id":"*","request_id":"*","message":"*","event_type":"*"*}' as ts, level, domain, job_run_id, request_id, message, event_type, rest
            | filter level = "ERROR"
            | sort @timestamp desc
            | limit 20
          EOT
          region = data.aws_region.current.name
          title  = "Recent Errors (Structured Logs)"
        }
      },
      {
        type   = "log"
        x      = 12
        y      = 18
        width  = 12
        height = 6
        properties = {
          query  = <<-EOT
            SOURCE '${aws_cloudwatch_log_group.glue_job.name}'
            | fields @timestamp, @message
            | parse @message '{"timestamp":"*","level":"*","domain":"*","job_run_id":"*","request_id":"*","message":"*","event_type":"*"*}' as ts, level, domain, job_run_id, request_id, message, event_type, rest
            | filter event_type = "DATA_CHANGE"
            | sort @timestamp desc
            | limit 20
          EOT
          region = data.aws_region.current.name
          title  = "Recent Data Changes (Traceability)"
        }
      },
      
      # Row 5: Job Summary
      {
        type   = "log"
        x      = 0
        y      = 24
        width  = 24
        height = 6
        properties = {
          query  = <<-EOT
            SOURCE '${aws_cloudwatch_log_group.glue_job.name}'
            | fields @timestamp, @message
            | parse @message '{"timestamp":"*","level":"*","domain":"*","job_run_id":"*","request_id":"*","message":"*","event_type":"*","details":{"total_records":*,"records_passed":*,"records_warned":*,"records_failed":*,"records_duplicates":*,"records_anomalies":*,"avg_quality_score":*,"pass_rate":*,"duration_seconds":*}}' as ts, level, domain, job_run_id, request_id, message, event_type, total_records, records_passed, records_warned, records_failed, records_duplicates, records_anomalies, avg_quality_score, pass_rate, duration_seconds
            | filter event_type = "JOB_SUMMARY"
            | sort @timestamp desc
            | limit 10
          EOT
          region = data.aws_region.current.name
          title  = "Job Summaries (Structured)"
        }
      }
    ]
  })
}
