# Outputs for Beauty Products Data Lake Infrastructure

output "raw_bucket_name" {
  value       = aws_s3_bucket.raw.id
  description = "Name of the raw data S3 bucket"
}

output "curated_bucket_name" {
  value       = aws_s3_bucket.curated.id
  description = "Name of the curated data S3 bucket"
}

output "metadata_bucket_name" {
  value       = aws_s3_bucket.metadata.id
  description = "Name of the metadata S3 bucket"
}

output "glue_scripts_bucket_name" {
  value       = aws_s3_bucket.glue_scripts.id
  description = "Name of the Glue scripts S3 bucket"
}

output "glue_database_name" {
  value       = aws_glue_catalog_database.beauty_products.name
  description = "Name of the Glue Data Catalog database"
}

output "glue_metadata_database_name" {
  value       = aws_glue_catalog_database.metadata.name
  description = "Name of the Glue metadata database"
}

output "glue_etl_role_arn" {
  value       = aws_iam_role.glue_etl.arn
  description = "ARN of the Glue ETL IAM role"
}

output "athena_query_role_arn" {
  value       = aws_iam_role.athena_query.arn
  description = "ARN of the Athena query IAM role"
}

output "athena_workgroup_name" {
  value       = aws_athena_workgroup.main.name
  description = "Name of the Athena workgroup for querying (use in Console or CLI --work-group)"
}

output "athena_workgroup_result_location" {
  value       = aws_athena_workgroup.main.configuration[0].result_configuration[0].output_location
  description = "S3 path where Athena query results are stored"
}

output "cloudwatch_dashboard_url" {
  value       = "https://console.aws.amazon.com/cloudwatch/home?region=${data.aws_region.current.name}#dashboards:name=${aws_cloudwatch_dashboard.pipeline_metrics.dashboard_name}"
  description = "URL to CloudWatch dashboard"
}

output "glue_job_url" {
  value       = "https://console.aws.amazon.com/glue/home?region=${data.aws_region.current.name}#/v2/etl-jobs/view/${aws_glue_job.beauty_products_etl.name}"
  description = "URL to Glue job in AWS Console"
}

output "glue_workflow_name" {
  value       = aws_glue_workflow.beauty_products_pipeline.name
  description = "Name of the Glue ETL workflow"
}

output "glue_workflow_url" {
  value       = "https://console.aws.amazon.com/glue/home?region=${data.aws_region.current.name}#/v2/etl-configuration/workflows/view/${aws_glue_workflow.beauty_products_pipeline.name}"
  description = "URL to Glue workflow in AWS Console"
}

output "lake_formation_service_role_arn" {
  value       = aws_iam_role.lake_formation_service.arn
  description = "ARN of the Lake Formation service role"
}

output "lake_formation_console_url" {
  value       = "https://console.aws.amazon.com/lakeformation/home?region=${data.aws_region.current.name}#"
  description = "URL to Lake Formation console"
}

# =============================================================================
# LLM TRENDING PRODUCTS SYSTEM OUTPUTS
# =============================================================================

output "api_gateway_url" {
  description = "API Gateway endpoint URL for LLM system"
  value       = var.enable_llm_system ? "https://${aws_api_gateway_rest_api.llm[0].id}.execute-api.${var.aws_region}.amazonaws.com/${aws_api_gateway_stage.llm[0].stage_name}/trending-products/query" : null
}

output "cognito_user_pool_id" {
  description = "Cognito User Pool ID for authentication"
  value       = var.enable_llm_system ? aws_cognito_user_pool.llm[0].id : null
}

output "cognito_client_id" {
  description = "Cognito App Client ID for chatbot integration"
  value       = var.enable_llm_system ? aws_cognito_user_pool_client.llm[0].id : null
}

output "cognito_user_pool_domain" {
  description = "Cognito User Pool domain for hosted UI"
  value       = var.enable_llm_system ? aws_cognito_user_pool_domain.llm[0].domain : null
}

output "pdf_bucket_name" {
  description = "S3 bucket name for PDF reports"
  value       = var.enable_llm_system ? aws_s3_bucket.pdfs[0].id : null
}

output "lambda_function_name" {
  description = "Lambda orchestrator function name"
  value       = var.enable_llm_system ? aws_lambda_function.orchestrator[0].function_name : null
}

output "lambda_function_arn" {
  description = "Lambda orchestrator function ARN"
  value       = var.enable_llm_system ? aws_lambda_function.orchestrator[0].arn : null
}

output "lambda_scraper_function_name" {
  description = "Scraper Lambda function name (invoked by orchestrator)"
  value       = var.enable_llm_system ? aws_lambda_function.scraper[0].function_name : null
}

output "dynamodb_logs_table_name" {
  description = "DynamoDB table for prompt audit logs"
  value       = var.enable_llm_system ? aws_dynamodb_table.prompt_logs[0].name : null
}

output "cloudwatch_llm_dashboard_url" {
  description = "URL to CloudWatch LLM metrics dashboard"
  value       = var.enable_llm_system ? "https://console.aws.amazon.com/cloudwatch/home?region=${data.aws_region.current.name}#dashboards:name=${aws_cloudwatch_dashboard.llm_metrics[0].dashboard_name}" : null
}
