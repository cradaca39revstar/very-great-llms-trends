# S3 Buckets for Beauty Products Data Lake
# Raw, Curated, and Metadata zones

# Raw Zone Bucket
resource "aws_s3_bucket" "raw" {
  bucket = "very-great-products-raw-us-east-1-dev"
  
  tags = {
    Name        = "Beauty Products Raw Zone"
    Environment = var.environment
    Project     = "BeautyProductsDataLake"
    DataZone    = "Raw"
    ManagedBy   = "Terraform"
  }
}

# Enable versioning on raw bucket
resource "aws_s3_bucket_versioning" "raw" {
  bucket = aws_s3_bucket.raw.id
  
  versioning_configuration {
    status = "Enabled"
  }
}

# Server-side encryption for raw bucket
resource "aws_s3_bucket_server_side_encryption_configuration" "raw" {
  bucket = aws_s3_bucket.raw.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Lifecycle policy for raw bucket
resource "aws_s3_bucket_lifecycle_configuration" "raw" {
  bucket = aws_s3_bucket.raw.id

  rule {
    id     = "archive-old-raw-files"
    status = "Enabled"

    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    expiration {
      days = 365
    }

    filter {
      prefix = "landing/"
    }
  }
}

# Block public access for raw bucket
resource "aws_s3_bucket_public_access_block" "raw" {
  bucket = aws_s3_bucket.raw.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Curated Zone Bucket
resource "aws_s3_bucket" "curated" {
  bucket = "very-great-products-processed-us-east-1-dev"
  
  tags = {
    Name        = "Beauty Products Curated Zone"
    Environment = var.environment
    Project     = "BeautyProductsDataLake"
    DataZone    = "Curated"
    ManagedBy   = "Terraform"
  }
}

# Enable versioning on curated bucket
resource "aws_s3_bucket_versioning" "curated" {
  bucket = aws_s3_bucket.curated.id
  
  versioning_configuration {
    status = "Enabled"
  }
}

# Server-side encryption for curated bucket
resource "aws_s3_bucket_server_side_encryption_configuration" "curated" {
  bucket = aws_s3_bucket.curated.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Lifecycle policy for curated bucket
resource "aws_s3_bucket_lifecycle_configuration" "curated" {
  bucket = aws_s3_bucket.curated.id

  rule {
    id     = "transition-to-ia"
    status = "Enabled"

    transition {
      days          = 180
      storage_class = "STANDARD_IA"
    }

    filter {
      prefix = "curated/"
    }
  }

  rule {
    id     = "cleanup-error-files"
    status = "Enabled"

    expiration {
      days = 30
    }

    filter {
      prefix = "error/"
    }
  }

  rule {
    id     = "cleanup-quarantine-files"
    status = "Enabled"

    expiration {
      days = 30
    }

    filter {
      prefix = "quarantine/"
    }
  }
}

# Block public access for curated bucket
resource "aws_s3_bucket_public_access_block" "curated" {
  bucket = aws_s3_bucket.curated.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Metadata Zone Bucket
resource "aws_s3_bucket" "metadata" {
  bucket = "very-great-products-metadata-us-east-1-dev"
  
  tags = {
    Name        = "Beauty Products Metadata Zone"
    Environment = var.environment
    Project     = "BeautyProductsDataLake"
    DataZone    = "Metadata"
    ManagedBy   = "Terraform"
  }
}

# Enable versioning on metadata bucket
resource "aws_s3_bucket_versioning" "metadata" {
  bucket = aws_s3_bucket.metadata.id
  
  versioning_configuration {
    status = "Enabled"
  }
}

# Server-side encryption for metadata bucket
resource "aws_s3_bucket_server_side_encryption_configuration" "metadata" {
  bucket = aws_s3_bucket.metadata.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Block public access for metadata bucket
resource "aws_s3_bucket_public_access_block" "metadata" {
  bucket = aws_s3_bucket.metadata.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Allow Athena to write query results to athena-results/ (required for "Unable to verify/create output bucket")
resource "aws_s3_bucket_policy" "metadata_athena" {
  bucket = aws_s3_bucket.metadata.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AthenaQueryResults"
        Effect    = "Allow"
        Principal = { Service = "athena.amazonaws.com" }
        Action = [
          "s3:GetBucketLocation",
          "s3:GetObject",
          "s3:ListBucket",
          "s3:ListBucketMultipartUploads",
          "s3:AbortMultipartUpload",
          "s3:PutObject"
        ]
        Resource = [
          aws_s3_bucket.metadata.arn,
          "${aws_s3_bucket.metadata.arn}/athena-results/*"
        ]
        Condition = {
          StringEquals = { "aws:SourceAccount" = data.aws_caller_identity.current.account_id }
        }
      }
    ]
  })
}

# Dedicated Athena query results bucket (NOT in Lake Formation).
# metadata bucket is LF-managed; Athena "Unable to verify/create output bucket" can persist.
# This bucket uses only IAM + bucket policy; workgroup points here.
resource "aws_s3_bucket" "athena_results" {
  bucket = "very-great-products-athena-results-us-east-1-${var.environment}"

  tags = {
    Name        = "Beauty Products Athena Results"
    Environment = var.environment
    Project     = "BeautyProductsDataLake"
    ManagedBy   = "Terraform"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "athena_results" {
  bucket = aws_s3_bucket.athena_results.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "athena_results" {
  bucket = aws_s3_bucket.athena_results.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_policy" "athena_results" {
  bucket = aws_s3_bucket.athena_results.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AthenaQueryResults"
        Effect    = "Allow"
        Principal = { Service = "athena.amazonaws.com" }
        Action = [
          "s3:GetBucketLocation",
          "s3:GetObject",
          "s3:ListBucket",
          "s3:ListBucketMultipartUploads",
          "s3:AbortMultipartUpload",
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

# S3 Bucket for Glue scripts
resource "aws_s3_bucket" "glue_scripts" {
  bucket = "very-great-products-glue-scripts-us-east-1-dev"
  
  tags = {
    Name        = "Glue Scripts Storage"
    Environment = var.environment
    Project     = "BeautyProductsDataLake"
    ManagedBy   = "Terraform"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "glue_scripts" {
  bucket = aws_s3_bucket.glue_scripts.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Upload Glue ETL script to S3
resource "aws_s3_object" "etl_script" {
  bucket = aws_s3_bucket.glue_scripts.id
  key    = "scripts/beauty_products_etl.py"
  source = "${path.module}/../scripts/beauty_products_etl.py"
  etag   = filemd5("${path.module}/../scripts/beauty_products_etl.py")
  
  tags = {
    Name = "Beauty Products ETL Script"
  }
}
