# AWS Glue Data Catalog - Databases and Tables

# Main database for beauty products
resource "aws_glue_catalog_database" "beauty_products" {
  name        = "beauty_products_db"
  description = "Database for beauty products sales data - raw and curated tables"
  
  catalog_id = data.aws_caller_identity.current.account_id
}

# Metadata database
resource "aws_glue_catalog_database" "metadata" {
  name        = "beauty_products_metadata_db"
  description = "Database for data quality metrics and lineage tracking"
  
  catalog_id = data.aws_caller_identity.current.account_id
}

# Raw beauty products table (CSV schema)
resource "aws_glue_catalog_table" "raw_beauty_products" {
  name          = "raw_beauty_products"
  database_name = aws_glue_catalog_database.beauty_products.name
  
  table_type = "EXTERNAL_TABLE"
  
  parameters = {
    "classification" = "csv"
    "skip.header.line.count" = "1"
  }
  
  storage_descriptor {
    location      = "s3://${aws_s3_bucket.raw.bucket}/landing/beauty-products/"
    input_format  = "org.apache.hadoop.mapred.TextInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat"
    
    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.serde2.OpenCSVSerde"
      
      parameters = {
        "separatorChar"          = ","
        "quoteChar"              = "\""
        "escapeChar"             = "\\"
      }
    }
    
    columns {
      name = "month"
      type = "string"
    }
    
    columns {
      name = "product_id"
      type = "string"
    }
    
    columns {
      name = "product_name"
      type = "string"
    }
    
    columns {
      name = "shop_name"
      type = "string"
    }
    
    columns {
      name = "l1_category"
      type = "string"
    }
    
    columns {
      name = "l2_category"
      type = "string"
    }
    
    columns {
      name = "l3_category"
      type = "string"
    }
    
    columns {
      name = "item_sold"
      type = "string"
    }
    
    columns {
      name = "revenue"
      type = "string"
    }
    
    columns {
      name = "avg_unit_price"
      type = "string"
    }
    
    columns {
      name = "mom_growth_pct"
      type = "string"
    }
  }
}

# Curated beauty products table (Parquet schema)
resource "aws_glue_catalog_table" "curated_beauty_products" {
  name          = "curated_beauty_products"
  database_name = aws_glue_catalog_database.beauty_products.name
  
  description = "Curated beauty products sales data with data quality metadata"
  
  table_type = "EXTERNAL_TABLE"
  
  parameters = {
    "classification" = "parquet"
    "parquet.compression" = "SNAPPY"
  }
  
  partition_keys {
    name = "year"
    type = "int"
  }
  
  partition_keys {
    name = "month_num"
    type = "int"
  }
  
  storage_descriptor {
    location      = "s3://${aws_s3_bucket.curated.bucket}/curated/beauty-products/"
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"
    
    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
    }
    
    columns {
      name    = "month"
      type    = "date"
      comment = "Transaction month"
    }
    
    columns {
      name    = "product_id"
      type    = "bigint"
      comment = "Unique product identifier"
    }
    
    columns {
      name    = "product_name"
      type    = "string"
      comment = "Product name"
    }
    
    columns {
      name    = "shop_name"
      type    = "string"
      comment = "Shop/seller name"
    }
    
    columns {
      name    = "l1_category"
      type    = "string"
      comment = "Level 1 category"
    }
    
    columns {
      name    = "l2_category"
      type    = "string"
      comment = "Level 2 category"
    }
    
    columns {
      name    = "l3_category"
      type    = "string"
      comment = "Level 3 category"
    }
    
    columns {
      name    = "item_sold"
      type    = "int"
      comment = "Quantity sold"
    }
    
    columns {
      name    = "revenue_usd"
      type    = "decimal(18,2)"
      comment = "Total revenue in USD"
    }
    
    columns {
      name    = "avg_unit_price_usd"
      type    = "decimal(10,2)"
      comment = "Average unit price in USD"
    }
    
    columns {
      name    = "mom_growth_pct"
      type    = "decimal(5,4)"
      comment = "Month-over-month growth as decimal ratio"
    }
    
    columns {
      name    = "source_file"
      type    = "string"
      comment = "Original file name/path"
    }
    
    columns {
      name    = "source_record_number"
      type    = "bigint"
      comment = "Line number in source CSV"
    }
    
    columns {
      name    = "processed_timestamp"
      type    = "timestamp"
      comment = "When record was processed (UTC)"
    }
    
    columns {
      name    = "transformation_version"
      type    = "string"
      comment = "ETL job version"
    }
    
    columns {
      name    = "data_quality_score"
      type    = "decimal(5,4)"
      comment = "Data quality score 0.0000-1.0000"
    }
    
    columns {
      name    = "quality_flags"
      type    = "string"
      comment = "Comma-separated quality issues"
    }
    
    columns {
      name    = "created_by"
      type    = "string"
      comment = "Job/user that created record"
    }
    
    columns {
      name    = "record_hash"
      type    = "string"
      comment = "MD5 hash for deduplication"
    }
  }
}

# Error records table
resource "aws_glue_catalog_table" "error_beauty_products" {
  name          = "error_beauty_products"
  database_name = aws_glue_catalog_database.beauty_products.name
  
  description = "Rejected records from ETL processing"
  
  table_type = "EXTERNAL_TABLE"
  
  parameters = {
    "classification" = "parquet"
  }
  
  storage_descriptor {
    location      = "s3://${aws_s3_bucket.curated.bucket}/error/beauty-products/"
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"
    
    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
    }
    
    columns {
      name = "error_reason"
      type = "string"
    }
    
    columns {
      name = "raw_record"
      type = "string"
    }
    
    columns {
      name = "error_timestamp"
      type = "timestamp"
    }
  }
}

# Quarantine records table
resource "aws_glue_catalog_table" "quarantine_beauty_products" {
  name          = "quarantine_beauty_products"
  database_name = aws_glue_catalog_database.beauty_products.name
  
  description = "Suspicious records requiring manual review"
  
  table_type = "EXTERNAL_TABLE"
  
  parameters = {
    "classification" = "parquet"
  }
  
  storage_descriptor {
    location      = "s3://${aws_s3_bucket.curated.bucket}/quarantine/beauty-products/"
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"
    
    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
    }
    
    columns {
      name = "quarantine_reason"
      type = "string"
    }
    
    columns {
      name = "data_quality_score"
      type = "decimal(5,4)"
    }
  }
}

# Data quality metrics table
resource "aws_glue_catalog_table" "data_quality_metrics" {
  name          = "data_quality_metrics"
  database_name = aws_glue_catalog_database.metadata.name
  
  description = "Aggregate data quality metrics from ETL job runs"
  
  table_type = "EXTERNAL_TABLE"
  
  parameters = {
    "classification" = "json"
  }
  
  storage_descriptor {
    location      = "s3://${aws_s3_bucket.curated.bucket}/quality-reports/beauty-products/"
    input_format  = "org.apache.hadoop.mapred.TextInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat"
    
    ser_de_info {
      serialization_library = "org.openx.data.jsonserde.JsonSerDe"
    }
    
    columns {
      name = "job_run_id"
      type = "string"
    }
    
    columns {
      name = "execution_timestamp"
      type = "string"
    }
    
    columns {
      name = "source_file"
      type = "string"
    }
    
    columns {
      name = "total_records"
      type = "int"
    }
    
    columns {
      name = "records_passed"
      type = "int"
    }
    
    columns {
      name = "records_warned"
      type = "int"
    }
    
    columns {
      name = "records_failed"
      type = "int"
    }
    
    columns {
      name = "pass_rate"
      type = "decimal(5,4)"
    }
    
    columns {
      name = "avg_quality_score"
      type = "decimal(5,4)"
    }
    
    columns {
      name = "transformation_version"
      type = "string"
    }
  }
}

# Transformation lineage table
resource "aws_glue_catalog_table" "transformation_lineage" {
  name          = "transformation_lineage"
  database_name = aws_glue_catalog_database.metadata.name
  
  description = "Source-to-target lineage tracking for ETL jobs"
  
  table_type = "EXTERNAL_TABLE"
  
  parameters = {
    "classification" = "parquet"
  }
  
  storage_descriptor {
    location      = "s3://${aws_s3_bucket.metadata.bucket}/lineage/"
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"
    
    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
    }
    
    columns {
      name = "source_file_path"
      type = "string"
    }
    
    columns {
      name = "target_file_path"
      type = "string"
    }
    
    columns {
      name = "job_name"
      type = "string"
    }
    
    columns {
      name = "job_run_id"
      type = "string"
    }
    
    columns {
      name = "transformation_timestamp"
      type = "timestamp"
    }
    
    columns {
      name = "records_in"
      type = "bigint"
    }
    
    columns {
      name = "records_out"
      type = "bigint"
    }
    
    columns {
      name = "records_error"
      type = "bigint"
    }
  }
}
