# Analysis of Possible Errors When Deploying Lake Formation

## Executive Summary

This document identifies possible errors that may occur during Lake Formation deployment with Terraform and provides preventive solutions.

---

## 1. Dependency and Creation Order Errors

### 1.1. Table Permissions Without Explicit Dependencies

**Problem:** Table permissions (`aws_lakeformation_permissions`) for specific tables do not have explicit `depends_on`, which can cause errors if Glue tables do not yet exist.

**Location:** Lines 77-168 in `lake-formation.tf`

**Expected Error:**
```
Error: InvalidInputException: Table not found: beauty_products_db.raw_beauty_products
```

**Solution:** Add `depends_on` to all table permission resources:
```hcl
resource "aws_lakeformation_permissions" "glue_etl_raw_table" {
  # ... existing config ...
  
  depends_on = [
    aws_glue_catalog_table.raw_beauty_products,
    aws_lakeformation_data_lake_settings.main
  ]
}
```

### 1.2. Database Permissions Without Dependencies

**Problem:** Database permissions do not have explicit `depends_on`.

**Location:** Lines 38-72 in `lake-formation.tf`

**Expected Error:**
```
Error: InvalidInputException: Database not found: beauty_products_db
```

**Solution:** Add `depends_on`:
```hcl
resource "aws_lakeformation_permissions" "glue_etl_beauty_products_db" {
  # ... existing config ...
  
  depends_on = [
    aws_glue_catalog_database.beauty_products,
    aws_lakeformation_data_lake_settings.main
  ]
}
```

### 1.3. S3 Resource Registration Before Data Lake Settings

**Problem:** S3 resources are registered before `data_lake_settings` exists, which can cause issues.

**Location:** Lines 20-33 in `lake-formation.tf`

**Solution:** Add `depends_on`:
```hcl
resource "aws_lakeformation_resource" "raw_bucket" {
  # ... existing config ...
  
  depends_on = [
    aws_lakeformation_data_lake_settings.main
  ]
}
```

---

## 2. IAM Permission Errors

### 2.1. Roles Without Lake Formation Permissions

**Problem:** IAM roles (Glue ETL, Athena) do not have explicit Lake Formation permissions to grant permissions.

**Location:** `iam.tf` - Roles `glue_etl` and `athena_query`

**Expected Error:**
```
Error: AccessDeniedException: User: arn:aws:iam::ACCOUNT:role/GlueETLRole is not authorized to perform: lakeformation:GrantPermissions
```

**Solution:** Add IAM policies for Lake Formation:
```hcl
# For Glue ETL Role
resource "aws_iam_role_policy" "glue_lakeformation" {
  name = "GlueLakeFormationPolicy"
  role = aws_iam_role.glue_etl.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "lakeformation:GetDataAccess",
          "lakeformation:GrantPermissions"
        ]
        Resource = "*"
      }
    ]
  })
}
```

### 2.2. Terraform User Without Lake Formation Permissions

**Problem:** The user/role executing Terraform needs Lake Formation permissions to create resources.

**Expected Error:**
```
Error: AccessDeniedException: User: arn:aws:iam::ACCOUNT:user/terraform-user is not authorized to perform: lakeformation:PutDataLakeSettings
```

**Solution:** Ensure the Terraform user/role has:
- `lakeformation:PutDataLakeSettings`
- `lakeformation:GetDataLakeSettings`
- `lakeformation:RegisterResource`
- `lakeformation:DeregisterResource`
- `lakeformation:GrantPermissions`
- `lakeformation:RevokePermissions`
- `lakeformation:GetResourceLFTags`
- `lakeformation:PutResourceLFTags`

---

## 3. Glue Catalog Configuration Errors

### 3.1. Glue Catalog Without Lake Formation Permissions

**Problem:** When Lake Formation is enabled, Glue Catalog needs explicit permissions to create databases and tables.

**Expected Error:**
```
Error: AccessDeniedException: Insufficient permissions to perform this operation
```

**Solution:** The Glue ETL role needs `CREATE_DATABASE` and `CREATE_TABLE` permissions in Lake Formation (already configured, but verify they are applied before creating Glue resources).

### 3.2. Databases Created Before Lake Formation

**Problem:** If Glue databases are created before enabling Lake Formation, they may not be under Lake Formation control.

**Solution:** Ensure `aws_lakeformation_data_lake_settings` is created first, or use `terraform apply -target` to apply in order.

---

## 4. S3 Resource Registration Errors

### 4.1. S3 Buckets Without Permissions for Lake Formation Service Role

**Problem:** The Lake Formation service role needs permissions on S3 buckets, but buckets may have policies that block access.

**Location:** `iam.tf` line 246-273

**Expected Error:**
```
Error: InvalidInputException: Unable to verify/create access role for the given S3 path
```

**Solution:** Verify that:
1. The `lake_formation_service` role has S3 permissions (already configured)
2. Buckets do not have policies that block the role
3. The role has permissions on the root bucket and all prefixes

### 4.2. S3 Buckets with Versioning Enabled

**Problem:** Buckets with versioning can cause issues with Lake Formation.

**Location:** `s3-buckets.tf` - All buckets have versioning enabled

**Note:** This is generally not a problem, but may require additional configuration.

---

## 5. Data Location Permission Errors

### 5.1. Location Permissions Without Prior Registration

**Problem:** `DATA_LOCATION_ACCESS` permissions are granted before the resource is fully registered.

**Location:** Lines 173-213 in `lake-formation.tf`

**Expected Error:**
```
Error: InvalidInputException: Resource not registered: arn:aws:s3:::bucket-name
```

**Solution:** They already have `depends_on`, but verify that registration completes before granting permissions. Consider adding a delay or using `terraform apply` in two steps.

---

## 6. Data Lake Settings Configuration Errors

### 6.1. Admin Without Sufficient Permissions

**Problem:** The configured admin may not have sufficient permissions in IAM.

**Location:** Line 9 in `lake-formation.tf`

**Expected Error:**
```
Error: InvalidInputException: Principal does not have sufficient permissions
```

**Solution:** Verify that the admin ARN has administrator permissions in IAM or is a role with Lake Formation permissions.

### 6.2. Incorrect Trusted Resource Owners

**Problem:** The `trusted_resource_owners` must be the correct account ID.

**Location:** Line 13 in `lake-formation.tf`

**Note:** Already correctly configured with `data.aws_caller_identity.current.account_id`.

---

## 7. Concurrency and Race Condition Errors

### 7.1. Multiple Permissions Created Simultaneously

**Problem:** Creating multiple permissions at the same time can cause conflicts.

**Solution:** Use `terraform apply` with `-parallelism=1` for initial deployment:
```bash
terraform apply -parallelism=1
```

---

## 8. Prevention Checklist

Before executing `terraform apply`, verify:

- [ ] The Terraform user/role has Lake Formation permissions
- [ ] S3 buckets exist and are accessible
- [ ] The `lake_formation_service` role has correct S3 permissions
- [ ] Glue databases will be created after `data_lake_settings`
- [ ] Glue tables will be created after databases
- [ ] All resources have appropriate `depends_on`
- [ ] IAM roles have Lake Formation policies (if necessary)
- [ ] There are no existing Lake Formation resources that could cause conflicts

---

## 9. Recommended Application Order

To avoid dependency errors, apply in this order:

1. **First phase:**
   ```bash
   terraform apply -target=aws_lakeformation_data_lake_settings.main
   terraform apply -target=aws_iam_role.lake_formation_service
   terraform apply -target=aws_lakeformation_resource.raw_bucket
   terraform apply -target=aws_lakeformation_resource.curated_bucket
   terraform apply -target=aws_lakeformation_resource.metadata_bucket
   ```

2. **Second phase:**
   ```bash
   terraform apply -target=aws_glue_catalog_database.beauty_products
   terraform apply -target=aws_glue_catalog_database.metadata
   ```

3. **Third phase:**
   ```bash
   terraform apply -target=aws_glue_catalog_table.raw_beauty_products
   terraform apply -target=aws_glue_catalog_table.curated_beauty_products
   # ... other tables
   ```

4. **Fourth phase:**
   ```bash
   terraform apply  # Apply all remaining permissions
   ```

---

## 10. Diagnostic Commands

If an error occurs, use these commands to diagnose:

```bash
# Verify Lake Formation configuration
aws lakeformation get-data-lake-settings

# Verify registered resources
aws lakeformation list-resources

# Verify permissions for a principal
aws lakeformation list-permissions --principal <role-arn>

# Verify permissions for a database
aws lakeformation list-permissions --resource-type DATABASE --resource <database-name>
```

---

## 11. Proposed Solutions

### Solution 1: Add Explicit Dependencies

Modify `lake-formation.tf` to add `depends_on` to all permission resources.

### Solution 2: Add Lake Formation IAM Policies

Add IAM policies so roles can interact with Lake Formation.

### Solution 3: Use Terraform Modules

Consider using Terraform modules for Lake Formation that handle dependencies automatically.

### Solution 4: Gradual Application Script

Create a script that applies resources in the correct order.

---

## Conclusion

The most likely errors are:
1. **Missing explicit dependencies** (most common)
2. **Insufficient IAM permissions** (very common)
3. **Incorrect creation order** (common in initial deployments)

It is recommended to implement solutions 1 and 2 before initial deployment.
