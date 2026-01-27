# S3 Bucket for LLM-Generated PDF Reports
# Temporary storage with lifecycle policy for automatic deletion

# PDF Storage Bucket
resource "aws_s3_bucket" "pdfs" {
  count = var.enable_llm_system ? 1 : 0

  bucket = "beauty-products-pdfs-us-east-1-${var.environment}"

  tags = {
    Name        = "LLM PDF Reports"
    Environment = var.environment
    Component   = "LLM-TrendingProducts"
    DataZone    = "Temporary"
    ManagedBy   = "Terraform"
  }
}

# Block all public access
resource "aws_s3_bucket_public_access_block" "pdfs" {
  count = var.enable_llm_system ? 1 : 0

  bucket = aws_s3_bucket.pdfs[0].id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Server-side encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "pdfs" {
  count = var.enable_llm_system ? 1 : 0

  bucket = aws_s3_bucket.pdfs[0].id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

# Versioning disabled (PDFs are temporary)
resource "aws_s3_bucket_versioning" "pdfs" {
  count = var.enable_llm_system ? 1 : 0

  bucket = aws_s3_bucket.pdfs[0].id

  versioning_configuration {
    status = "Disabled"
  }
}

# Lifecycle rule to delete PDFs after configurable days
resource "aws_s3_bucket_lifecycle_configuration" "pdfs" {
  count = var.enable_llm_system ? 1 : 0

  bucket = aws_s3_bucket.pdfs[0].id

  rule {
    id     = "delete-old-pdfs"
    status = "Enabled"

    expiration {
      days = var.pdf_expiration_days
    }

    noncurrent_version_expiration {
      noncurrent_days = 1
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }
}

# CORS configuration for direct browser access (if needed)
resource "aws_s3_bucket_cors_configuration" "pdfs" {
  count = var.enable_llm_system ? 1 : 0

  bucket = aws_s3_bucket.pdfs[0].id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "HEAD"]
    allowed_origins = ["*"] # Restrict to specific domains in production
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}

# Bucket policy to allow Lambda write access
resource "aws_s3_bucket_policy" "pdfs" {
  count = var.enable_llm_system ? 1 : 0

  bucket = aws_s3_bucket.pdfs[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowLambdaWrite"
        Effect = "Allow"
        Principal = {
          AWS = aws_iam_role.lambda_orchestrator[0].arn
        }
        Action = [
          "s3:PutObject",
          "s3:PutObjectAcl",
          "s3:GetObject"
        ]
        Resource = "${aws_s3_bucket.pdfs[0].arn}/*"
      },
      {
        Sid    = "DenyInsecureTransport"
        Effect = "Deny"
        Principal = "*"
        Action = "s3:*"
        Resource = [
          aws_s3_bucket.pdfs[0].arn,
          "${aws_s3_bucket.pdfs[0].arn}/*"
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      }
    ]
  })
}

# CloudWatch metric for bucket size monitoring
resource "aws_cloudwatch_metric_alarm" "pdf_bucket_size" {
  count = var.enable_llm_system ? 1 : 0

  alarm_name          = "beauty-products-llm-pdf-bucket-size-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "BucketSizeBytes"
  namespace           = "AWS/S3"
  period              = "86400" # 1 day
  statistic           = "Average"
  threshold           = "10737418240" # 10 GB
  alarm_description   = "PDF bucket size exceeds 10 GB - check lifecycle policy"
  treat_missing_data  = "notBreaching"

  dimensions = {
    BucketName = aws_s3_bucket.pdfs[0].id
    StorageType = "StandardStorage"
  }

  tags = {
    Name        = "pdf-bucket-size-alarm-${var.environment}"
    Component   = "LLM-TrendingProducts"
    Environment = var.environment
  }
}
