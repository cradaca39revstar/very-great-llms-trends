# AWS Glue Crawlers for Beauty Products Data Lake

# Crawler for raw zone (optional - for initial discovery)
resource "aws_glue_crawler" "raw_crawler" {
  name          = "beauty-products-raw-crawler"
  role          = aws_iam_role.glue_etl.arn
  database_name = aws_glue_catalog_database.beauty_products.name
  
  description = "Crawler for raw beauty products CSV files (exploratory use only)"
  
  s3_target {
    path = "s3://${aws_s3_bucket.raw.bucket}/landing/beauty-products/"
  }
  
  schema_change_policy {
    delete_behavior = "LOG"
    update_behavior = "LOG"
  }
  
  tags = {
    Name        = "Beauty Products Raw Crawler"
    Environment = var.environment
    Project     = "BeautyProductsDataLake"
  }
}

# Crawler for quality reports
resource "aws_glue_crawler" "quality_crawler" {
  name          = "beauty-products-quality-crawler"
  role          = aws_iam_role.glue_etl.arn
  database_name = aws_glue_catalog_database.metadata.name
  
  description = "Crawler for data quality report JSON files"
  
  s3_target {
    path = "s3://${aws_s3_bucket.curated.bucket}/quality-reports/beauty-products/"
  }
  
  schedule = "cron(0 3 * * ? *)"  # Daily at 3 AM UTC (after ETL job)
  
  schema_change_policy {
    delete_behavior = "LOG"
    update_behavior = "LOG"
  }
  
  tags = {
    Name        = "Beauty Products Quality Reports Crawler"
    Environment = var.environment
    Project     = "BeautyProductsDataLake"
  }
}
