# AWS Lake Formation Configuration
# Centralized governance for the Beauty Products Data Lake

# -----------------------------------------------------------------------------
# Data Lake Settings
# -----------------------------------------------------------------------------
resource "aws_lakeformation_data_lake_settings" "main" {
  admins = [
    data.aws_caller_identity.current.arn
  ]

  trusted_resource_owners = [
    data.aws_caller_identity.current.account_id
  ]
}

# -----------------------------------------------------------------------------
# Register S3 Buckets as Data Lake Locations
# -----------------------------------------------------------------------------
resource "aws_lakeformation_resource" "raw_bucket" {
  arn      = aws_s3_bucket.raw.arn
  role_arn = aws_iam_role.lake_formation_service.arn

  depends_on = [
    aws_lakeformation_data_lake_settings.main,
    aws_iam_role.lake_formation_service
  ]
}

resource "aws_lakeformation_resource" "curated_bucket" {
  arn      = aws_s3_bucket.curated.arn
  role_arn = aws_iam_role.lake_formation_service.arn

  depends_on = [
    aws_lakeformation_data_lake_settings.main,
    aws_iam_role.lake_formation_service
  ]
}

resource "aws_lakeformation_resource" "metadata_bucket" {
  arn      = aws_s3_bucket.metadata.arn
  role_arn = aws_iam_role.lake_formation_service.arn

  depends_on = [
    aws_lakeformation_data_lake_settings.main,
    aws_iam_role.lake_formation_service
  ]
}

# -----------------------------------------------------------------------------
# Database Permissions
# -----------------------------------------------------------------------------
resource "aws_lakeformation_permissions" "glue_etl_beauty_products_db" {
  principal   = aws_iam_role.glue_etl.arn
  permissions = ["CREATE_TABLE", "ALTER", "DROP"]

  database {
    name = aws_glue_catalog_database.beauty_products.name
  }

  depends_on = [
    aws_glue_catalog_database.beauty_products,
    aws_lakeformation_data_lake_settings.main
  ]
}

resource "aws_lakeformation_permissions" "glue_etl_metadata_db" {
  principal   = aws_iam_role.glue_etl.arn
  permissions = ["CREATE_TABLE", "ALTER", "DROP"]

  database {
    name = aws_glue_catalog_database.metadata.name
  }

  depends_on = [
    aws_glue_catalog_database.metadata,
    aws_lakeformation_data_lake_settings.main
  ]
}

resource "aws_lakeformation_permissions" "athena_beauty_products_db" {
  principal   = aws_iam_role.athena_query.arn
  permissions = ["DESCRIBE"]

  database {
    name = aws_glue_catalog_database.beauty_products.name
  }

  depends_on = [
    aws_glue_catalog_database.beauty_products,
    aws_lakeformation_data_lake_settings.main
  ]
}

resource "aws_lakeformation_permissions" "athena_metadata_db" {
  principal   = aws_iam_role.athena_query.arn
  permissions = ["DESCRIBE"]

  database {
    name = aws_glue_catalog_database.metadata.name
  }

  depends_on = [
    aws_glue_catalog_database.metadata,
    aws_lakeformation_data_lake_settings.main
  ]
}

# -----------------------------------------------------------------------------
# Table Permissions - Beauty Products Database
# -----------------------------------------------------------------------------
resource "aws_lakeformation_permissions" "glue_etl_raw_table" {
  principal   = aws_iam_role.glue_etl.arn
  permissions = ["SELECT", "INSERT", "DELETE", "ALTER", "DROP"]

  table {
    database_name = aws_glue_catalog_database.beauty_products.name
    name          = aws_glue_catalog_table.raw_beauty_products.name
  }

  depends_on = [
    aws_glue_catalog_table.raw_beauty_products,
    aws_glue_catalog_database.beauty_products,
    aws_lakeformation_data_lake_settings.main
  ]
}

resource "aws_lakeformation_permissions" "glue_etl_curated_table" {
  principal   = aws_iam_role.glue_etl.arn
  permissions = ["SELECT", "INSERT", "DELETE", "ALTER", "DROP"]

  table {
    database_name = aws_glue_catalog_database.beauty_products.name
    name          = aws_glue_catalog_table.curated_beauty_products.name
  }

  depends_on = [
    aws_glue_catalog_table.curated_beauty_products,
    aws_glue_catalog_database.beauty_products,
    aws_lakeformation_data_lake_settings.main
  ]
}

resource "aws_lakeformation_permissions" "athena_curated_table" {
  principal   = aws_iam_role.athena_query.arn
  permissions = ["SELECT"]

  table {
    database_name = aws_glue_catalog_database.beauty_products.name
    name          = aws_glue_catalog_table.curated_beauty_products.name
  }

  depends_on = [
    aws_glue_catalog_table.curated_beauty_products,
    aws_glue_catalog_database.beauty_products,
    aws_lakeformation_data_lake_settings.main
  ]
}

resource "aws_lakeformation_permissions" "glue_etl_error_table" {
  principal   = aws_iam_role.glue_etl.arn
  permissions = ["SELECT", "INSERT", "DELETE", "ALTER", "DROP"]

  table {
    database_name = aws_glue_catalog_database.beauty_products.name
    name          = aws_glue_catalog_table.error_beauty_products.name
  }

  depends_on = [
    aws_glue_catalog_table.error_beauty_products,
    aws_glue_catalog_database.beauty_products,
    aws_lakeformation_data_lake_settings.main
  ]
}

resource "aws_lakeformation_permissions" "glue_etl_quarantine_table" {
  principal   = aws_iam_role.glue_etl.arn
  permissions = ["SELECT", "INSERT", "DELETE", "ALTER", "DROP"]

  table {
    database_name = aws_glue_catalog_database.beauty_products.name
    name          = aws_glue_catalog_table.quarantine_beauty_products.name
  }

  depends_on = [
    aws_glue_catalog_table.quarantine_beauty_products,
    aws_glue_catalog_database.beauty_products,
    aws_lakeformation_data_lake_settings.main
  ]
}

# -----------------------------------------------------------------------------
# Table Permissions - Metadata Database
# -----------------------------------------------------------------------------
resource "aws_lakeformation_permissions" "glue_etl_quality_metrics_table" {
  principal   = aws_iam_role.glue_etl.arn
  permissions = ["SELECT", "INSERT", "DELETE", "ALTER", "DROP"]

  table {
    database_name = aws_glue_catalog_database.metadata.name
    name          = aws_glue_catalog_table.data_quality_metrics.name
  }

  depends_on = [
    aws_glue_catalog_table.data_quality_metrics,
    aws_glue_catalog_database.metadata,
    aws_lakeformation_data_lake_settings.main
  ]
}

resource "aws_lakeformation_permissions" "athena_quality_metrics_table" {
  principal   = aws_iam_role.athena_query.arn
  permissions = ["SELECT"]

  table {
    database_name = aws_glue_catalog_database.metadata.name
    name          = aws_glue_catalog_table.data_quality_metrics.name
  }

  depends_on = [
    aws_glue_catalog_table.data_quality_metrics,
    aws_glue_catalog_database.metadata,
    aws_lakeformation_data_lake_settings.main
  ]
}

resource "aws_lakeformation_permissions" "glue_etl_lineage_table" {
  principal   = aws_iam_role.glue_etl.arn
  permissions = ["SELECT", "INSERT", "DELETE", "ALTER", "DROP"]

  table {
    database_name = aws_glue_catalog_database.metadata.name
    name          = aws_glue_catalog_table.transformation_lineage.name
  }

  depends_on = [
    aws_glue_catalog_table.transformation_lineage,
    aws_glue_catalog_database.metadata,
    aws_lakeformation_data_lake_settings.main
  ]
}

resource "aws_lakeformation_permissions" "athena_lineage_table" {
  principal   = aws_iam_role.athena_query.arn
  permissions = ["SELECT"]

  table {
    database_name = aws_glue_catalog_database.metadata.name
    name          = aws_glue_catalog_table.transformation_lineage.name
  }

  depends_on = [
    aws_glue_catalog_table.transformation_lineage,
    aws_glue_catalog_database.metadata,
    aws_lakeformation_data_lake_settings.main
  ]
}

# -----------------------------------------------------------------------------
# Data Location Permissions (Glue ETL)
# -----------------------------------------------------------------------------
resource "aws_lakeformation_permissions" "glue_etl_raw_location" {
  principal   = aws_iam_role.glue_etl.arn
  permissions = ["DATA_LOCATION_ACCESS"]

  data_location {
    arn = aws_s3_bucket.raw.arn
  }

  depends_on = [
    aws_lakeformation_resource.raw_bucket,
    aws_lakeformation_data_lake_settings.main
  ]
}

resource "aws_lakeformation_permissions" "glue_etl_curated_location" {
  principal   = aws_iam_role.glue_etl.arn
  permissions = ["DATA_LOCATION_ACCESS"]

  data_location {
    arn = aws_s3_bucket.curated.arn
  }

  depends_on = [
    aws_lakeformation_resource.curated_bucket,
    aws_lakeformation_data_lake_settings.main
  ]
}

resource "aws_lakeformation_permissions" "glue_etl_metadata_location" {
  principal   = aws_iam_role.glue_etl.arn
  permissions = ["DATA_LOCATION_ACCESS"]

  data_location {
    arn = aws_s3_bucket.metadata.arn
  }

  depends_on = [
    aws_lakeformation_resource.metadata_bucket,
    aws_lakeformation_data_lake_settings.main
  ]
}
