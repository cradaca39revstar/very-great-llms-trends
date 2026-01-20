# EventBridge Scheduler for Glue ETL Workflow

# Glue Workflow for Beauty Products ETL Pipeline
resource "aws_glue_workflow" "beauty_products_pipeline" {
  name        = "beauty-products-etl-workflow"
  description = "Orchestrates Beauty Products ETL job and future pipeline steps"
  
  max_concurrent_runs = 1
  
  tags = {
    Name        = "Beauty Products ETL Workflow"
    Environment = var.environment
    Project     = "BeautyProductsDataLake"
  }
}

# Glue Trigger (EVENT type) - Start trigger for the workflow
resource "aws_glue_trigger" "workflow_start" {
  name          = "beauty-products-workflow-start-trigger"
  type          = "EVENT"
  workflow_name = aws_glue_workflow.beauty_products_pipeline.name
  
  actions {
    job_name = aws_glue_job.beauty_products_etl.name
  }
  
  # Note: EVENT triggers cannot be enabled on creation via Terraform
  # Will be enabled when EventBridge sends first event
  enabled = false
  
  tags = {
    Name        = "Beauty Products Workflow Start Trigger"
    Environment = var.environment
    Project     = "BeautyProductsDataLake"
  }
}

# EventBridge rule to trigger workflow daily
resource "aws_cloudwatch_event_rule" "daily_etl" {
  name                = "beauty-products-daily-etl"
  description         = "Trigger Beauty Products ETL workflow daily at 2 AM UTC"
  schedule_expression = "cron(0 2 * * ? *)"
  
  tags = {
    Name        = "Beauty Products Daily ETL Schedule"
    Environment = var.environment
    Project     = "BeautyProductsDataLake"
  }
}

# Target for EventBridge rule - Glue Workflow
resource "aws_cloudwatch_event_target" "glue_workflow" {
  rule      = aws_cloudwatch_event_rule.daily_etl.name
  target_id = "TriggerGlueWorkflow"
  arn       = aws_glue_workflow.beauty_products_pipeline.arn
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

# Policy for EventBridge to start Glue workflows
resource "aws_iam_role_policy" "eventbridge_glue_policy" {
  name = "EventBridgeGlueStartWorkflowPolicy"
  role = aws_iam_role.eventbridge_glue.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "glue:StartWorkflowRun",
          "glue:StartTrigger"
        ]
        Resource = [
          aws_glue_workflow.beauty_products_pipeline.arn,
          aws_glue_trigger.workflow_start.arn
        ]
      }
    ]
  })
}

# Get current AWS region
data "aws_region" "current" {}
