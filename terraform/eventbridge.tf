# EventBridge Scheduler for Glue ETL Job

# EventBridge rule to trigger Glue job daily
resource "aws_cloudwatch_event_rule" "daily_etl" {
  name                = "beauty-products-daily-etl"
  description         = "Trigger Beauty Products ETL job daily at 2 AM UTC"
  schedule_expression = "cron(0 2 * * ? *)"
  
  tags = {
    Name        = "Beauty Products Daily ETL Schedule"
    Environment = var.environment
    Project     = "BeautyProductsDataLake"
  }
}

# Target for EventBridge rule
resource "aws_cloudwatch_event_target" "glue_job" {
  rule      = aws_cloudwatch_event_rule.daily_etl.name
  target_id = "TriggerGlueJob"
  arn       = "arn:aws:glue:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:job/${aws_glue_job.beauty_products_etl.name}"
  role_arn  = aws_iam_role.eventbridge_glue.arn
}

# IAM role for EventBridge to trigger Glue
resource "aws_iam_role" "eventbridge_glue" {
  name = "EventBridgeGlueRole-BeautyProducts"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "events.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "EventBridge Glue Trigger Role"
    Environment = var.environment
    Project     = "BeautyProductsDataLake"
  }
}

# Policy for EventBridge to start Glue jobs
resource "aws_iam_role_policy" "eventbridge_glue_policy" {
  name = "EventBridgeGlueStartJobPolicy"
  role = aws_iam_role.eventbridge_glue.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "glue:StartJobRun"
        ]
        Resource = aws_glue_job.beauty_products_etl.arn
      }
    ]
  })
}

# Get current AWS region
data "aws_region" "current" {}
