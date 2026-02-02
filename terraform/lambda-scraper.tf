# Scraper Lambda (internal; invoked by orchestrator only)
# Build and deploy code with: scripts/deploy-lambda-scraper.ps1

resource "aws_lambda_function" "scraper" {
  count = var.enable_llm_system ? 1 : 0

  function_name = "beauty-products-llm-scraper-${var.environment}"
  description   = "Web product scraper for URL, image, trends_text (invoked by LLM orchestrator)"
  filename      = "${path.module}/lambda_placeholder.zip"
  handler       = "web_product_scraper.lambda_handler"
  runtime       = "python3.10"
  role          = aws_iam_role.lambda_scraper[0].arn
  memory_size   = 256
  timeout       = 30

  environment {
    variables = {
      AWS_REGION_NAME       = var.aws_region
      BEDROCK_PRIMARY_MODEL = var.bedrock_primary_model
    }
  }

  tags = {
    Name        = "llm-scraper-${var.environment}"
    Component   = "LLM-TrendingProducts"
    Environment = var.environment
  }
}

resource "aws_iam_role" "lambda_scraper" {
  count = var.enable_llm_system ? 1 : 0

  name = "beauty-products-llm-scraper-role-${var.environment}"

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
    Name        = "llm-scraper-role-${var.environment}"
    Component   = "LLM-TrendingProducts"
    Environment = var.environment
  }
}

resource "aws_iam_policy" "lambda_scraper_logs" {
  count = var.enable_llm_system ? 1 : 0

  name        = "beauty-products-llm-scraper-logs-${var.environment}"
  description = "CloudWatch Logs for scraper Lambda"

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
          "arn:aws:logs:${var.aws_region}:*:log-group:/aws/lambda/beauty-products-llm-scraper-*"
        ]
      }
    ]
  })
}

resource "aws_iam_policy" "lambda_scraper_bedrock" {
  count = var.enable_llm_system ? 1 : 0

  name        = "beauty-products-llm-scraper-bedrock-${var.environment}"
  description = "Bedrock InvokeModel for scraper (candidate URL suggestion)"

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
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_scraper_logs" {
  count = var.enable_llm_system ? 1 : 0

  role       = aws_iam_role.lambda_scraper[0].name
  policy_arn = aws_iam_policy.lambda_scraper_logs[0].arn
}

resource "aws_iam_role_policy_attachment" "lambda_scraper_bedrock" {
  count = var.enable_llm_system ? 1 : 0

  role       = aws_iam_role.lambda_scraper[0].name
  policy_arn = aws_iam_policy.lambda_scraper_bedrock[0].arn
}

resource "aws_cloudwatch_log_group" "lambda_scraper" {
  count = var.enable_llm_system ? 1 : 0

  name              = "/aws/lambda/beauty-products-llm-scraper-${var.environment}"
  retention_in_days  = 30

  tags = {
    Name        = "llm-scraper-logs-${var.environment}"
    Component   = "LLM-TrendingProducts"
    Environment = var.environment
  }
}
