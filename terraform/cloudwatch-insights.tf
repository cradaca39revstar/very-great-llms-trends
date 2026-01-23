# CloudWatch Logs Insights Query Definitions for Beauty Products Data Lake
# These saved queries enable quick analysis of structured JSON logs

# =============================================================================
# DATA CHANGE QUERIES
# =============================================================================

# Query: All Data Changes
# Use: Track all data changes for traceability
resource "aws_cloudwatch_query_definition" "data_changes" {
  name = "BeautyProducts/DataChanges/AllChanges"

  log_group_names = [
    aws_cloudwatch_log_group.glue_job.name
  ]

  query_string = <<-EOT
    fields @timestamp, @message
    | parse @message '{"timestamp":"*","level":"*","domain":"*","job_run_id":"*","request_id":"*","message":"*","event_type":"*","details":*}' as timestamp, level, domain, job_run_id, request_id, message, event_type, details
    | filter event_type = "DATA_CHANGE"
    | sort @timestamp desc
    | limit 100
  EOT
}

# Query: Data Changes by Table
# Use: Filter data changes by specific table
resource "aws_cloudwatch_query_definition" "data_changes_by_table" {
  name = "BeautyProducts/DataChanges/ByTable"

  log_group_names = [
    aws_cloudwatch_log_group.glue_job.name
  ]

  query_string = <<-EOT
    fields @timestamp, @message
    | parse @message '{"timestamp":"*","level":"*","domain":"*","job_run_id":"*","request_id":"*","message":"*","event_type":"*","details":{"change_type":"*","table_name":"*","operation":"*"*}}' as timestamp, level, domain, job_run_id, request_id, message, event_type, change_type, table_name, operation, rest
    | filter event_type = "DATA_CHANGE"
    | stats count(*) as change_count by table_name, change_type, operation
    | sort change_count desc
  EOT
}

# Query: Data Changes Summary by Job Run
# Use: Get summary of all changes for a specific job run
resource "aws_cloudwatch_query_definition" "data_changes_by_job_run" {
  name = "BeautyProducts/DataChanges/ByJobRun"

  log_group_names = [
    aws_cloudwatch_log_group.glue_job.name
  ]

  query_string = <<-EOT
    fields @timestamp, @message
    | parse @message '{"timestamp":"*","level":"*","domain":"*","job_run_id":"*","request_id":"*","message":"*","event_type":"*"*}' as timestamp, level, domain, job_run_id, request_id, message, event_type, rest
    | filter event_type = "DATA_CHANGE"
    | stats count(*) as change_count by job_run_id
    | sort @timestamp desc
    | limit 50
  EOT
}

# =============================================================================
# ERROR AND WARNING QUERIES
# =============================================================================

# Query: All Errors
# Use: View all error logs for troubleshooting
resource "aws_cloudwatch_query_definition" "errors" {
  name = "BeautyProducts/Errors/AllErrors"

  log_group_names = [
    aws_cloudwatch_log_group.glue_job.name
  ]

  query_string = <<-EOT
    fields @timestamp, @message
    | parse @message '{"timestamp":"*","level":"*","domain":"*","job_run_id":"*","request_id":"*","message":"*","event_type":"*","error":{"type":"*","message":"*"*}}' as timestamp, level, domain, job_run_id, request_id, message, event_type, error_type, error_message, rest
    | filter level = "ERROR"
    | sort @timestamp desc
    | limit 50
  EOT
}

# Query: Errors by Type
# Use: Group errors by type for pattern analysis
resource "aws_cloudwatch_query_definition" "errors_by_type" {
  name = "BeautyProducts/Errors/ByType"

  log_group_names = [
    aws_cloudwatch_log_group.glue_job.name
  ]

  query_string = <<-EOT
    fields @timestamp, @message
    | parse @message '{"timestamp":"*","level":"*","domain":"*","job_run_id":"*","request_id":"*","message":"*","event_type":"*","error":{"type":"*","message":"*"*}}' as timestamp, level, domain, job_run_id, request_id, message, event_type, error_type, error_message, rest
    | filter level = "ERROR"
    | stats count(*) as error_count by error_type
    | sort error_count desc
  EOT
}

# Query: Quality Alerts
# Use: View quality degradation alerts
resource "aws_cloudwatch_query_definition" "quality_alerts" {
  name = "BeautyProducts/Alerts/QualityAlerts"

  log_group_names = [
    aws_cloudwatch_log_group.glue_job.name
  ]

  query_string = <<-EOT
    fields @timestamp, @message
    | parse @message '{"timestamp":"*","level":"*","domain":"*","job_run_id":"*","request_id":"*","message":"*","event_type":"*","details":{"alert_type":"*","threshold":*,"actual_value":*}*}' as timestamp, level, domain, job_run_id, request_id, message, event_type, alert_type, threshold, actual_value, rest
    | filter event_type = "QUALITY_ALERT"
    | sort @timestamp desc
    | limit 50
  EOT
}

# =============================================================================
# ETL JOB QUERIES
# =============================================================================

# Query: Job Summaries
# Use: View job completion summaries
resource "aws_cloudwatch_query_definition" "job_summaries" {
  name = "BeautyProducts/Jobs/Summaries"

  log_group_names = [
    aws_cloudwatch_log_group.glue_job.name
  ]

  query_string = <<-EOT
    fields @timestamp, @message
    | parse @message '{"timestamp":"*","level":"*","domain":"*","job_run_id":"*","request_id":"*","message":"*","event_type":"*","details":{"total_records":*,"records_passed":*,"records_failed":*,"records_duplicates":*,"records_anomalies":*,"avg_quality_score":*,"pass_rate":*}*}' as timestamp, level, domain, job_run_id, request_id, message, event_type, total_records, records_passed, records_failed, records_duplicates, records_anomalies, avg_quality_score, pass_rate, rest
    | filter event_type = "JOB_SUMMARY"
    | sort @timestamp desc
    | limit 20
  EOT
}

# Query: ETL Steps
# Use: Track ETL step progress
resource "aws_cloudwatch_query_definition" "etl_steps" {
  name = "BeautyProducts/Jobs/ETLSteps"

  log_group_names = [
    aws_cloudwatch_log_group.glue_job.name
  ]

  query_string = <<-EOT
    fields @timestamp, @message
    | parse @message '{"timestamp":"*","level":"*","domain":"*","job_run_id":"*","request_id":"*","message":"*","event_type":"*","details":{"step_number":*,"step_name":"*","status":"*"}*}' as timestamp, level, domain, job_run_id, request_id, message, event_type, step_number, step_name, status, rest
    | filter event_type = "ETL_STEP"
    | sort @timestamp desc
    | limit 100
  EOT
}

# Query: Job Duration Analysis
# Use: Analyze job duration patterns
resource "aws_cloudwatch_query_definition" "job_duration" {
  name = "BeautyProducts/Jobs/DurationAnalysis"

  log_group_names = [
    aws_cloudwatch_log_group.glue_job.name
  ]

  query_string = <<-EOT
    fields @timestamp, @message
    | parse @message '{"timestamp":"*","level":"*","domain":"*","job_run_id":"*"*"details":{"total_records":*,"records_passed":*,"records_failed":*,"records_duplicates":*,"records_anomalies":*,"avg_quality_score":*,"pass_rate":*,"duration_seconds":*}*}' as timestamp, level, domain, job_run_id, rest1, total_records, records_passed, records_failed, records_duplicates, records_anomalies, avg_quality_score, pass_rate, duration_seconds, rest2
    | filter event_type = "JOB_SUMMARY"
    | stats avg(duration_seconds) as avg_duration, min(duration_seconds) as min_duration, max(duration_seconds) as max_duration by bin(1d)
  EOT
}

# =============================================================================
# DATA QUALITY QUERIES
# =============================================================================

# Query: Quality Score Trends
# Use: Track quality score over time
resource "aws_cloudwatch_query_definition" "quality_trends" {
  name = "BeautyProducts/Quality/ScoreTrends"

  log_group_names = [
    aws_cloudwatch_log_group.glue_job.name
  ]

  query_string = <<-EOT
    fields @timestamp, @message
    | parse @message '{"timestamp":"*","level":"*","domain":"*","job_run_id":"*"*"avg_quality_score":*,"pass_rate":*}*}' as timestamp, level, domain, job_run_id, rest1, avg_quality_score, pass_rate, rest2
    | filter event_type = "JOB_SUMMARY"
    | stats avg(avg_quality_score) as avg_score, avg(pass_rate) as avg_pass_rate by bin(1d)
    | sort @timestamp desc
  EOT
}

# Query: Quality Issues Distribution
# Use: Analyze distribution of quality issues
resource "aws_cloudwatch_query_definition" "quality_issues" {
  name = "BeautyProducts/Quality/IssuesDistribution"

  log_group_names = [
    aws_cloudwatch_log_group.glue_job.name
  ]

  query_string = <<-EOT
    fields @timestamp, @message
    | parse @message '*"quality_flags":"*"*' as prefix, quality_flags, suffix
    | filter quality_flags != ""
    | stats count(*) as issue_count by quality_flags
    | sort issue_count desc
  EOT
}

# Query: Records by Quality Tier
# Use: Analyze records distribution by quality tier
resource "aws_cloudwatch_query_definition" "records_by_quality" {
  name = "BeautyProducts/Quality/RecordsByTier"

  log_group_names = [
    aws_cloudwatch_log_group.glue_job.name
  ]

  query_string = <<-EOT
    fields @timestamp, @message
    | parse @message '{"timestamp":"*","level":"*","domain":"*","job_run_id":"*"*"details":{"total_records":*,"records_passed":*,"records_failed":*,"records_warned":*}*}' as timestamp, level, domain, job_run_id, rest1, total_records, records_passed, records_failed, records_warned, rest2
    | filter event_type = "JOB_SUMMARY"
    | stats sum(records_passed) as total_passed, sum(records_warned) as total_warned, sum(records_failed) as total_failed by bin(1d)
  EOT
}

# =============================================================================
# TRACEABILITY QUERIES
# =============================================================================

# Query: Full Audit Trail by Job Run
# Use: Get complete audit trail for a job run
resource "aws_cloudwatch_query_definition" "audit_trail" {
  name = "BeautyProducts/Audit/FullTrailByJobRun"

  log_group_names = [
    aws_cloudwatch_log_group.glue_job.name
  ]

  query_string = <<-EOT
    fields @timestamp, @message
    | parse @message '{"timestamp":"*","level":"*","domain":"*","job_run_id":"*","request_id":"*","message":"*","event_type":"*"*}' as timestamp, level, domain, job_run_id, request_id, message, event_type, rest
    | sort @timestamp asc
    | limit 500
  EOT
}

# Query: Recent Activity
# Use: View recent activity across all event types
resource "aws_cloudwatch_query_definition" "recent_activity" {
  name = "BeautyProducts/Audit/RecentActivity"

  log_group_names = [
    aws_cloudwatch_log_group.glue_job.name
  ]

  query_string = <<-EOT
    fields @timestamp, @message
    | parse @message '{"timestamp":"*","level":"*","domain":"*","job_run_id":"*","request_id":"*","message":"*","event_type":"*"*}' as timestamp, level, domain, job_run_id, request_id, message, event_type, rest
    | filter event_type in ["DATA_CHANGE", "JOB_INIT", "JOB_SUMMARY", "ERROR", "QUALITY_ALERT"]
    | sort @timestamp desc
    | limit 100
  EOT
}
