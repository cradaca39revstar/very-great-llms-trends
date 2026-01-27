# AWS API Gateway for LLM Trending Products System
# REST API with Cognito authorization

# API Gateway REST API
resource "aws_api_gateway_rest_api" "llm" {
  count = var.enable_llm_system ? 1 : 0

  name        = "beauty-products-trending-api-${var.environment}"
  description = "API for LLM Trending Products Report Generator"

  endpoint_configuration {
    types = ["REGIONAL"]
  }

  tags = {
    Name        = "beauty-products-trending-api-${var.environment}"
    Component   = "LLM-TrendingProducts"
    Environment = var.environment
  }
}

# Cognito Authorizer
resource "aws_api_gateway_authorizer" "cognito" {
  count = var.enable_llm_system ? 1 : 0

  name          = "cognito-authorizer"
  type          = "COGNITO_USER_POOLS"
  rest_api_id   = aws_api_gateway_rest_api.llm[0].id
  provider_arns = [aws_cognito_user_pool.llm[0].arn]
}

# /trending-products resource
resource "aws_api_gateway_resource" "trending_products" {
  count = var.enable_llm_system ? 1 : 0

  rest_api_id = aws_api_gateway_rest_api.llm[0].id
  parent_id   = aws_api_gateway_rest_api.llm[0].root_resource_id
  path_part   = "trending-products"
}

# /trending-products/query resource
resource "aws_api_gateway_resource" "query" {
  count = var.enable_llm_system ? 1 : 0

  rest_api_id = aws_api_gateway_rest_api.llm[0].id
  parent_id   = aws_api_gateway_resource.trending_products[0].id
  path_part   = "query"
}

# POST method with Cognito authorization
resource "aws_api_gateway_method" "post_query" {
  count = var.enable_llm_system ? 1 : 0

  rest_api_id   = aws_api_gateway_rest_api.llm[0].id
  resource_id   = aws_api_gateway_resource.query[0].id
  http_method   = "POST"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito[0].id

  request_parameters = {
    "method.request.header.Authorization" = true
  }
}

# Lambda integration
resource "aws_api_gateway_integration" "lambda" {
  count = var.enable_llm_system ? 1 : 0

  rest_api_id             = aws_api_gateway_rest_api.llm[0].id
  resource_id             = aws_api_gateway_resource.query[0].id
  http_method             = aws_api_gateway_method.post_query[0].http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.orchestrator[0].invoke_arn
}

# OPTIONS method for CORS preflight
resource "aws_api_gateway_method" "options_query" {
  count = var.enable_llm_system ? 1 : 0

  rest_api_id   = aws_api_gateway_rest_api.llm[0].id
  resource_id   = aws_api_gateway_resource.query[0].id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

# CORS integration
resource "aws_api_gateway_integration" "options" {
  count = var.enable_llm_system ? 1 : 0

  rest_api_id = aws_api_gateway_rest_api.llm[0].id
  resource_id = aws_api_gateway_resource.query[0].id
  http_method = aws_api_gateway_method.options_query[0].http_method
  type        = "MOCK"

  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

# CORS response
resource "aws_api_gateway_method_response" "options_200" {
  count = var.enable_llm_system ? 1 : 0

  rest_api_id = aws_api_gateway_rest_api.llm[0].id
  resource_id = aws_api_gateway_resource.query[0].id
  http_method = aws_api_gateway_method.options_query[0].http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_integration_response" "options" {
  count = var.enable_llm_system ? 1 : 0

  rest_api_id = aws_api_gateway_rest_api.llm[0].id
  resource_id = aws_api_gateway_resource.query[0].id
  http_method = aws_api_gateway_method.options_query[0].http_method
  status_code = aws_api_gateway_method_response.options_200[0].status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'POST,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }

  depends_on = [aws_api_gateway_integration.options]
}

# POST method response (for CORS)
resource "aws_api_gateway_method_response" "post_200" {
  count = var.enable_llm_system ? 1 : 0

  rest_api_id = aws_api_gateway_rest_api.llm[0].id
  resource_id = aws_api_gateway_resource.query[0].id
  http_method = aws_api_gateway_method.post_query[0].http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin" = true
  }

  response_models = {
    "application/json" = "Empty"
  }
}

# Lambda permission for API Gateway
resource "aws_lambda_permission" "api_gateway" {
  count = var.enable_llm_system ? 1 : 0

  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.orchestrator[0].function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.llm[0].execution_arn}/*/*"
}

# API Gateway deployment
resource "aws_api_gateway_deployment" "llm" {
  count = var.enable_llm_system ? 1 : 0

  rest_api_id = aws_api_gateway_rest_api.llm[0].id

  # Force redeployment on changes
  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.query[0].id,
      aws_api_gateway_method.post_query[0].id,
      aws_api_gateway_integration.lambda[0].id,
      aws_api_gateway_method.options_query[0].id,
      aws_api_gateway_integration.options[0].id
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [
    aws_api_gateway_integration.lambda,
    aws_api_gateway_integration.options
  ]
}

# API Gateway Stage
resource "aws_api_gateway_stage" "llm" {
  count = var.enable_llm_system ? 1 : 0

  deployment_id = aws_api_gateway_deployment.llm[0].id
  rest_api_id   = aws_api_gateway_rest_api.llm[0].id
  stage_name    = var.environment

  # Enable CloudWatch logs
  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway[0].arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      caller         = "$context.identity.caller"
      user           = "$context.identity.user"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      resourcePath   = "$context.resourcePath"
      status         = "$context.status"
      protocol       = "$context.protocol"
      responseLength = "$context.responseLength"
      errorMessage   = "$context.error.message"
    })
  }

  # Enable X-Ray tracing
  xray_tracing_enabled = true

  tags = {
    Name        = "beauty-products-trending-api-${var.environment}"
    Component   = "LLM-TrendingProducts"
    Environment = var.environment
  }
}

# CloudWatch Log Group for API Gateway
resource "aws_cloudwatch_log_group" "api_gateway" {
  count = var.enable_llm_system ? 1 : 0

  name              = "/aws/apigateway/beauty-products-trending-${var.environment}"
  retention_in_days = 90

  tags = {
    Name        = "api-gateway-logs-${var.environment}"
    Component   = "LLM-TrendingProducts"
    Environment = var.environment
  }
}

# Method settings (optional - for throttling)
resource "aws_api_gateway_method_settings" "all" {
  count = var.enable_llm_system ? 1 : 0

  rest_api_id = aws_api_gateway_rest_api.llm[0].id
  stage_name  = aws_api_gateway_stage.llm[0].stage_name
  method_path = "*/*"

  settings {
    metrics_enabled    = true
    logging_level      = "INFO"
    data_trace_enabled = false

    # Throttling
    throttling_burst_limit = 100
    throttling_rate_limit  = 50
  }
}
