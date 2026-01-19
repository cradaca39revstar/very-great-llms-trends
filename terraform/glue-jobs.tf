# AWS Glue ETL Jobs for Beauty Products Data Lake

# Main ETL job for beauty products
resource "aws_glue_job" "beauty_products_etl" {
  name         = "beauty-products-etl-job"
  role_arn     = aws_iam_role.glue_etl.arn
  glue_version = "4.0"
  
  description = "ETL job to transform raw beauty products CSV to curated Parquet with data quality checks"
  
  command {
    name            = "glueetl"
    script_location = "s3://${aws_s3_bucket.glue_scripts.bucket}/scripts/beauty_products_etl.py"
    python_version  = "3"
  }
  
  default_arguments = {
    "--job-language"                     = "python"
    "--job-bookmark-option"              = "job-bookmark-enable"
    "--enable-metrics"                   = "true"
    "--enable-continuous-cloudwatch-log" = "true"
    "--enable-spark-ui"                  = "true"
    "--spark-event-logs-path"            = "s3://${aws_s3_bucket.glue_scripts.bucket}/spark-logs/"
    
    # Job parameters
    "--SOURCE_BUCKET"          = aws_s3_bucket.raw.bucket
    "--CURATED_BUCKET"         = aws_s3_bucket.curated.bucket
    "--METADATA_BUCKET"        = aws_s3_bucket.metadata.bucket
    "--DATABASE_NAME"          = aws_glue_catalog_database.beauty_products.name
    "--TRANSFORMATION_VERSION" = "v1.0.0"
    
    # Data quality thresholds
    "--DQ_PASS_THRESHOLD"      = "0.95"
    "--DQ_WARN_THRESHOLD"      = "0.70"
    "--ANOMALY_REVENUE_MAX"    = "10000000"
    "--ANOMALY_ITEMS_MAX"      = "1000000"
    
    # Additional Spark configurations
    "--conf" = "spark.sql.adaptive.enabled=true"
  }
  
  execution_property {
    max_concurrent_runs = 1
  }
  
  worker_type       = "G.1X"
  number_of_workers = 2
  timeout           = 60  # 60 minutes
  max_retries       = 2
  
  tags = {
    Name        = "Beauty Products ETL Job"
    Environment = var.environment
    Project     = "BeautyProductsDataLake"
    Version     = "v1.0.0"
  }
}

# Output job name for reference
output "glue_job_name" {
  value       = aws_glue_job.beauty_products_etl.name
  description = "Name of the Glue ETL job"
}
