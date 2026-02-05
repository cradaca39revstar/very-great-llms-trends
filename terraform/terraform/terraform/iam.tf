# IAM Roles and Policies for Beauty Products Data Lake

# Glue ETL Service Role
resource "aws_iam_role" "glue_etl" {
  name = "GlueETLRole-BeautyProducts"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "glue.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "Glue ETL Role for Beauty Products"
    Environment = var.environment
    Project     = "BeautyProductsDataLake"
  }
}

# Attach AWS managed Glue service policy
resource "aws_iam_role_policy_attachment" "glue_service" {
  role       = aws_iam_role.glue_etl.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

# Custom policy for S3 access
resource "aws_iam_role_policy" "glue_s3_access" {
  name = "GlueS3AccessPolicy"
  role = aws_iam_role.glue_etl.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = [
          "${aws_s3_bucket.raw.arn}/*",
          "${aws_s3_bucket.curated.arn}/*",
          "${aws_s3_bucket.metadata.arn}/*",
          "${aws_s3_bucket.glue_scripts.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket",
          "s3:GetBucketLocation"
        ]
        Resource = [
          aws_s3_bucket.raw.arn,
          aws_s3_bucket.curated.arn,
          aws_s3_bucket.metadata.arn,
          aws_s3_bucket.glue_scripts.arn
        ]
      }
    ]
  })
}

# CloudWatch Logs policy for Glue
resource "aws_iam_role_policy" "glue_cloudwatch" {
  name = "GlueCloudWatchLogsPolicy"
  role = aws_iam_role.glue_etl.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:/aws-glue/*"
      }
    ]
  })
}

# Athena Query Role
resource "aws_iam_role" "athena_query" {
  name = "AthenaQueryRole-BeautyProducts"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "athena.amazonaws.com"
        }
      },
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
      }
    ]
  })

  tags = {
    Name        = "Athena Query Role for Beauty Products"
    Environment = var.environment
    Project     = "BeautyProductsDataLake"
  }
}

# Athena S3 access policy
resource "aws_iam_role_policy" "athena_s3_access" {
  name = "AthenaS3AccessPolicy"
  role = aws_iam_role.athena_query.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          "${aws_s3_bucket.curated.arn}/*",
          aws_s3_bucket.curated.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::aws-athena-query-results-*/*",
          "arn:aws:s3:::aws-athena-query-results-*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "glue:GetDatabase",
          "glue:GetTable",
          "glue:GetPartitions"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.metadata.arn,
          "${aws_s3_bucket.metadata.arn}/athena-results/*"
        ]
      }
    ]
  })
}

# Lambda trigger role (for S3 event triggers)
resource "aws_iam_role" "lambda_trigger" {
  name = "LambdaTriggerRole-BeautyProducts"

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
    Name        = "Lambda Trigger Role for Glue Jobs"
    Environment = var.environment
    Project     = "BeautyProductsDataLake"
  }
}

# Lambda policy to invoke Glue jobs
resource "aws_iam_role_policy" "lambda_glue_invoke" {
  name = "LambdaGlueInvokePolicy"
  role = aws_iam_role.lambda_trigger.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "glue:StartJobRun",
          "glue:GetJobRun",
          "glue:GetJobRuns"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

# Lake Formation service role
resource "aws_iam_role" "lake_formation_service" {
  name = "LakeFormationServiceRole-BeautyProducts-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lakeformation.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "Lake Formation Service Role"
    Environment = var.environment
    Project     = "BeautyProductsDataLake"
  }
}

resource "aws_iam_role_policy" "lake_formation_s3_access" {
  name = "LakeFormationS3AccessPolicy"
  role = aws_iam_role.lake_formation_service.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket",
          "s3:GetBucketLocation"
        ]
        Resource = [
          aws_s3_bucket.raw.arn,
          "${aws_s3_bucket.raw.arn}/*",
          aws_s3_bucket.curated.arn,
          "${aws_s3_bucket.curated.arn}/*",
          aws_s3_bucket.metadata.arn,
          "${aws_s3_bucket.metadata.arn}/*"
        ]
      }
    ]
  })
}

# Get current AWS account ID
data "aws_caller_identity" "current" {}
