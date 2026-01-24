# Athena Workgroup for Beauty Products Data Lake
# Enables querying via Athena with dedicated result location and engine version

resource "aws_athena_workgroup" "main" {
  name        = "beauty-products-athena-${var.environment}"
  description = "Athena workgroup for Beauty Products Data Lake (${var.environment})"
  state       = "ENABLED"

  configuration {
    result_configuration {
      output_location = "s3://${aws_s3_bucket.metadata.id}/athena-results/"

      encryption_configuration {
        encryption_option = "SSE_S3"
      }
    }

    engine_version {
      selected_engine_version = "Athena engine version 3"
    }

    enforce_workgroup_configuration = true
  }

  tags = {
    Name        = "Beauty Products Athena Workgroup"
    Environment = var.environment
    Project     = "BeautyProductsDataLake"
  }
}
