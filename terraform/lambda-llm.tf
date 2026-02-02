# AWS Lambda Function for LLM Trending Products Orchestrator
# Main handler that coordinates Athena queries, Bedrock calls, and PDF generation

# Lambda Function
resource "aws_lambda_function" "orchestrator" {
  count = var.enable_llm_system ? 1 : 0

  function_name = "beauty-products-llm-orchestrator-${var.environment}"
  description   = "LLM Trending Products Report Generator orchestrator"
  
  # Code placeholder - will be updated via deployment
  # Note: Create lambda_placeholder.zip manually or deploy real code immediately after terraform apply
  # For Windows: Use PowerShell: Compress-Archive -Path (New-Item -ItemType File -Path lambda_placeholder.py -Force) -DestinationPath lambda_placeholder.zip
  # For Linux/Mac: echo 'def lambda_handler(event, context): return {"statusCode": 200}' > lambda_placeholder.py && zip lambda_placeholder.zip lambda_placeholder.py
  filename      = "${path.module}/lambda_placeholder.zip"
  handler       = "trending_products_orchestrator.lambda_handler"
  runtime       = "python3.10"
  
  role          = aws_iam_role.lambda_orchestrator[0].arn
  
  memory_size   = var.lambda_memory_size
  timeout       = var.lambda_timeout

  # Environment variables
  environment {
    variables = {
      ATHENA_WORKGROUP        = "beauty-products-athena-${var.environment}"
      ATHENA_DATABASE         = "beauty_products_db"
      ATHENA_RESULT_BUCKET    = aws_s3_bucket.athena_results.id
      BEDROCK_PRIMARY_MODEL   = var.bedrock_primary_model
      BEDROCK_FALLBACK_MODEL  = var.bedrock_fallback_model
      DYNAMODB_LOGS_TABLE     = aws_dynamodb_table.prompt_logs[0].name
      PDF_BUCKET              = aws_s3_bucket.pdfs[0].id
      ENVIRONMENT             = var.environment
      AWS_REGION_NAME         = var.aws_region
      SCRAPER_FUNCTION_NAME   = aws_lambda_function.scraper[0].function_name
      KNOWLEDGE_BASE_ID       = var.knowledge_base_id
    }
  }

  # Enable X-Ray tracing
  tracing_config {
    mode = "Active"
  }

  tags = {
    Name        = "llm-orchestrator-${var.environment}"
    Component   = "LLM-TrendingProducts"
    Environment = var.environment
  }
}

# IAM Role for Lambda
resource "aws_iam_role" "lambda_orchestrator" {
  count = var.enable_llm_system ? 1 : 0

  name = "beauty-products-llm-orchestrator-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "llm-orchestrator-role-${var.environment}"
    Component   = "LLM-TrendingProducts"
    Environment = var.environment
  }
}

# IAM Policy: READ-ONLY Athena Access
resource "aws_iam_policy" "lambda_athena" {
  count = var.enable_llm_system ? 1 : 0

  name        = "beauty-products-llm-athena-${var.environment}"
  description = "READ-ONLY Athena access for LLM orchestrator"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AthenaQueryExecution"
        Effect = "Allow"
        Action = [
          "athena:StartQueryExecution",
          "athena:GetQueryExecution",
          "athena:GetQueryResults",
          "athena:StopQueryExecution",
          "athena:GetWorkGroup"
        ]
        Resource = [
          "arn:aws:athena:${var.aws_region}:*:workgroup/beauty-products-athena-${var.environment}"
        ]
      }
    ]
  })
}

# IAM Policy: READ-ONLY Glue Catalog Access
resource "aws_iam_policy" "lambda_glue" {
  count = var.enable_llm_system ? 1 : 0

  name        = "beauty-products-llm-glue-${var.environment}"
  description = "READ-ONLY Glue Catalog access for LLM orchestrator"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "GlueCatalogReadOnly"
        Effect = "Allow"
        Action = [
          "glue:GetDatabase",
          "glue:GetTable",
          "glue:GetPartitions",
          "glue:GetPartition"
        ]
        Resource = [
          "arn:aws:glue:${var.aws_region}:*:catalog",
          "arn:aws:glue:${var.aws_region}:*:database/beauty_products_db",
          "arn:aws:glue:${var.aws_region}:*:table/beauty_products_db/*"
        ]
      }
    ]
  })
}

# IAM Policy: READ-ONLY S3 Access to Curated Data
resource "aws_iam_policy" "lambda_s3_read" {
  count = var.enable_llm_system ? 1 : 0

  name        = "beauty-products-llm-s3-read-${var.environment}"
  description = "READ-ONLY S3 access to curated data for LLM orchestrator"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3CuratedDataReadOnly"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::very-great-products-processed-us-east-1-${var.environment}",
          "arn:aws:s3:::very-great-products-processed-us-east-1-${var.environment}/curated/*"
        ]
      },
      {
        Sid    = "S3AthenaResults"
        Effect = "Allow"
        Action = [
          "s3:GetBucketLocation",
          "s3:GetObject",
          "s3:ListBucket",
          "s3:PutObject"
        ]
        Resource = [
          aws_s3_bucket.athena_results.arn,
          "${aws_s3_bucket.athena_results.arn}/*"
        ]
      }
    ]
  })
}

# IAM Policy: WRITE S3 Access to PDF Bucket
resource "aws_iam_policy" "lambda_s3_write_pdf" {
  count = var.enable_llm_system ? 1 : 0

  name        = "beauty-products-llm-s3-pdf-${var.environment}"
  description = "S3 write access to PDF bucket for LLM orchestrator"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3PDFBucketWrite"
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:PutObjectAcl",
          "s3:GetObject"
        ]
        Resource = [
          "arn:aws:s3:::${aws_s3_bucket.pdfs[0].id}",
          "arn:aws:s3:::${aws_s3_bucket.pdfs[0].id}/*"
        ]
      }
    ]
  })
}

# IAM Policy: Bedrock Model Invocation
resource "aws_iam_policy" "lambda_bedrock" {
  count = var.enable_llm_system ? 1 : 0

  name        = "beauty-products-llm-bedrock-${var.environment}"
  description = "Bedrock model invocation for LLM orchestrator"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "BedrockInvokeModel"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = [
          "arn:aws:bedrock:${var.aws_region}::foundation-model/anthropic.claude-3-5-sonnet-*",
          "arn:aws:bedrock:${var.aws_region}::foundation-model/anthropic.claude-3-7-sonnet-*",
          "arn:aws:bedrock:${var.aws_region}::foundation-model/anthropic.claude-sonnet-4*",
          "arn:aws:bedrock:${var.aws_region}::foundation-model/amazon.nova-*",
          "arn:aws:bedrock:${var.aws_region}::foundation-model/cohere.command-*"
        ]
      },
      {
        Sid    = "BedrockKnowledgeBase"
        Effect = "Allow"
        Action = [
          "bedrock:RetrieveAndGenerate",
          "bedrock:Retrieve"
        ]
        Resource = "*"
      }
    ]
  })
}

# IAM Policy: DynamoDB Access for Prompt Logging
resource "aws_iam_policy" "lambda_dynamodb" {
  count = var.enable_llm_system ? 1 : 0

  name        = "beauty-products-llm-dynamodb-${var.environment}"
  description = "DynamoDB access for prompt logging"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "DynamoDBPromptLogging"
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:Query",
          "dynamodb:GetItem"
        ]
        Resource = [
          aws_dynamodb_table.prompt_logs[0].arn,
          "${aws_dynamodb_table.prompt_logs[0].arn}/index/*"
        ]
      }
    ]
  })
}

# IAM Policy: CloudWatch Logs
resource "aws_iam_policy" "lambda_cloudwatch" {
  count = var.enable_llm_system ? 1 : 0

  name        = "beauty-products-llm-cloudwatch-${var.environment}"
  description = "CloudWatch Logs access for LLM orchestrator"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = [
          "arn:aws:logs:${var.aws_region}:*:log-group:/aws/lambda/beauty-products-llm-*"
        ]
      },
      {
        Sid    = "CloudWatchMetrics"
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "cloudwatch:namespace" = "BeautyProducts/LLM"
          }
        }
      }
    ]
  })
}

# IAM Policy: X-Ray Tracing
resource "aws_iam_policy" "lambda_xray" {
  count = var.enable_llm_system ? 1 : 0

  name        = "beauty-products-llm-xray-${var.environment}"
  description = "X-Ray tracing for LLM orchestrator"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "XRayTracing"
        Effect = "Allow"
        Action = [
          "xray:PutTraceSegments",
          "xray:PutTelemetryRecords"
        ]
        Resource = "*"
      }
    ]
  })
}

# IAM Policy: Lake Formation GetDataAccess (required for Athena queries on LF-protected tables)
resource "aws_iam_policy" "lambda_lakeformation" {
  count = var.enable_llm_system ? 1 : 0

  name        = "beauty-products-llm-lakeformation-${var.environment}"
  description = "Lake Formation GetDataAccess for Athena queries on curated_beauty_products"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "LakeFormationGetDataAccess"
        Effect = "Allow"
        Action = [
          "lakeformation:GetDataAccess"
        ]
        Resource = "*"
      }
    ]
  })
}

# IAM Policy: Invoke Scraper Lambda (internal, no public API)
resource "aws_iam_policy" "lambda_invoke_scraper" {
  count = var.enable_llm_system ? 1 : 0

  name        = "beauty-products-llm-invoke-scraper-${var.environment}"
  description = "Allow orchestrator to invoke scraper Lambda"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "InvokeScraperLambda"
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = [
          aws_lambda_function.scraper[0].arn
        ]
      }
    ]
  })
}

# Attach all policies to Lambda role
resource "aws_iam_role_policy_attachment" "lambda_athena" {
  count = var.enable_llm_system ? 1 : 0

  role       = aws_iam_role.lambda_orchestrator[0].name
  policy_arn = aws_iam_policy.lambda_athena[0].arn
}

resource "aws_iam_role_policy_attachment" "lambda_glue" {
  count = var.enable_llm_system ? 1 : 0

  role       = aws_iam_role.lambda_orchestrator[0].name
  policy_arn = aws_iam_policy.lambda_glue[0].arn
}

resource "aws_iam_role_policy_attachment" "lambda_s3_read" {
  count = var.enable_llm_system ? 1 : 0

  role       = aws_iam_role.lambda_orchestrator[0].name
  policy_arn = aws_iam_policy.lambda_s3_read[0].arn
}

resource "aws_iam_role_policy_attachment" "lambda_s3_write_pdf" {
  count = var.enable_llm_system ? 1 : 0

  role       = aws_iam_role.lambda_orchestrator[0].name
  policy_arn = aws_iam_policy.lambda_s3_write_pdf[0].arn
}

resource "aws_iam_role_policy_attachment" "lambda_bedrock" {
  count = var.enable_llm_system ? 1 : 0

  role       = aws_iam_role.lambda_orchestrator[0].name
  policy_arn = aws_iam_policy.lambda_bedrock[0].arn
}

resource "aws_iam_role_policy_attachment" "lambda_dynamodb" {
  count = var.enable_llm_system ? 1 : 0

  role       = aws_iam_role.lambda_orchestrator[0].name
  policy_arn = aws_iam_policy.lambda_dynamodb[0].arn
}

resource "aws_iam_role_policy_attachment" "lambda_cloudwatch" {
  count = var.enable_llm_system ? 1 : 0

  role       = aws_iam_role.lambda_orchestrator[0].name
  policy_arn = aws_iam_policy.lambda_cloudwatch[0].arn
}

resource "aws_iam_role_policy_attachment" "lambda_xray" {
  count = var.enable_llm_system ? 1 : 0

  role       = aws_iam_role.lambda_orchestrator[0].name
  policy_arn = aws_iam_policy.lambda_xray[0].arn
}

resource "aws_iam_role_policy_attachment" "lambda_lakeformation" {
  count = var.enable_llm_system ? 1 : 0

  role       = aws_iam_role.lambda_orchestrator[0].name
  policy_arn = aws_iam_policy.lambda_lakeformation[0].arn
}

resource "aws_iam_role_policy_attachment" "lambda_invoke_scraper" {
  count = var.enable_llm_system ? 1 : 0

  role       = aws_iam_role.lambda_orchestrator[0].name
  policy_arn = aws_iam_policy.lambda_invoke_scraper[0].arn
}

# CloudWatch Log Group for Lambda
resource "aws_cloudwatch_log_group" "lambda_orchestrator" {
  count = var.enable_llm_system ? 1 : 0

  name              = "/aws/lambda/beauty-products-llm-orchestrator-${var.environment}"
  retention_in_days = 30

  tags = {
    Name        = "llm-orchestrator-logs-${var.environment}"
    Component   = "LLM-TrendingProducts"
    Environment = var.environment
  }
}
