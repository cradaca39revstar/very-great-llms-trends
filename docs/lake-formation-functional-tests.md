# Lake Formation Functional Testing Guide

## Summary

This guide provides step-by-step instructions to validate that Lake Formation is working correctly after deployment.

---

## Basic Tests (Automated)

### Run Test Script

```powershell
cd scripts
.\test-lake-formation.ps1 -Region us-east-1 -Environment dev
```

This script validates:
- ✓ Glue access to databases and tables
- ✓ Lake Formation permissions configured
- ✓ S3 bucket registration
- ✓ Glue job configuration
- ✓ Athena access to databases

---

## Advanced Functional Tests

### PHASE 1: Glue Data Access Test

#### Step 1.1: Verify Glue can read metadata

```powershell
# Verify database access
aws glue get-database --name beauty_products_db --region us-east-1

# Verify table access
aws glue get-table --database-name beauty_products_db --name raw_beauty_products --region us-east-1

# List all tables
aws glue get-tables --database-name beauty_products_db --region us-east-1
```

**Expected Result:**
- ✓ Commands execute without errors
- ✓ Database and table details are displayed

---

### PHASE 2: Athena Access Test

#### Step 2.1: Verify Athena can see databases

```powershell
# List databases
aws athena list-databases --catalog-name AwsDataCatalog --region us-east-1

# List tables in a database
aws athena list-table-metadata --catalog-name AwsDataCatalog --database-name beauty_products_db --region us-east-1
```

**Expected Result:**
- ✓ Athena can list databases
- ✓ Athena can list tables

#### Step 2.2: Execute a test query in Athena Console

1. Open Athena Console: https://console.aws.amazon.com/athena/home?region=us-east-1
2. Select the workgroup (or create one if it doesn't exist)
3. Execute this test query:

```sql
-- Verify you can describe the database
SHOW DATABASES;

-- Verify you can see the tables
SHOW TABLES IN beauty_products_db;

-- If there is data, try a simple query
SELECT COUNT(*) as total_records 
FROM beauty_products_db.curated_beauty_products 
LIMIT 1;
```

**Expected Result:**
- ✓ Queries execute without permission errors
- ✓ If there is data, results are displayed

**If there are permission errors:**
- Verify that the Athena role has SELECT permissions on tables
- Verify that Lake Formation is enabled for the database

---

### PHASE 3: Glue ETL Execution Test

#### Step 3.1: Prepare test data

```powershell
# Create test CSV file
$testData = @"
Month,Product Id,Product Name,Shop Name,L1 category,L2 category,L3 category,Item Sold,Revenue,Avg. Unit Price,MoM Growth %
4/01/2024,1729380000000000000,Test Product,TestShop,Beauty & Personal Care,Haircare,Brushes,100,1000.00,10.00,5%
"@

$testData | Out-File -FilePath test-beauty-products.csv -Encoding UTF8

# Upload to S3 (adjust date as needed)
$date = Get-Date -Format "yyyy/MM/dd"
$timestamp = Get-Date -Format "yyyyMMddHHmmss"
$s3Path = "s3://very-great-products-raw-us-east-1-dev/landing/beauty-products/$date/test-$timestamp.csv"

aws s3 cp test-beauty-products.csv $s3Path --region us-east-1

Write-Host "File uploaded to: $s3Path"
```

#### Step 3.2: Execute Glue job

```powershell
# Start Glue job
$jobRun = aws glue start-job-run --job-name beauty-products-etl-job --region us-east-1 --output json | ConvertFrom-Json
$jobRunId = $jobRun.JobRunId

Write-Host "Job started. Job Run ID: $jobRunId"

# Monitor job status
Write-Host "`nMonitoring job status..." -ForegroundColor Yellow
do {
    Start-Sleep -Seconds 10
    $status = aws glue get-job-run --job-name beauty-products-etl-job --run-id $jobRunId --region us-east-1 --output json | ConvertFrom-Json
    $currentStatus = $status.JobRun.JobRunState
    Write-Host "Current status: $currentStatus" -ForegroundColor Gray
} while ($currentStatus -eq "RUNNING" -or $currentStatus -eq "STARTING")

# View final result
if ($currentStatus -eq "SUCCEEDED") {
    Write-Host "`n✓ Job completed successfully!" -ForegroundColor Green
    Write-Host "  Execution Time: $($status.JobRun.ExecutionTime) seconds" -ForegroundColor Gray
} else {
    Write-Host "`n✗ Job failed or was stopped" -ForegroundColor Red
    Write-Host "  Status: $currentStatus" -ForegroundColor Red
    Write-Host "  Error Message: $($status.JobRun.ErrorMessage)" -ForegroundColor Red
}
```

#### Step 3.3: Verify job results

```powershell
# Verify files were created in S3 curated
aws s3 ls s3://very-great-products-processed-us-east-1-dev/curated/beauty-products/ --recursive --region us-east-1

# Verify quality metrics were created
aws s3 ls s3://very-great-products-processed-us-east-1-dev/quality-reports/beauty-products/ --recursive --region us-east-1

# Verify job logs in CloudWatch
Write-Host "`nView job logs in CloudWatch:" -ForegroundColor Yellow
Write-Host "https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups/log-group/$252Faws-glue$252Fjobs$252Foutput" -ForegroundColor Gray
```

**Expected Result:**
- ✓ Job executes without permission errors
- ✓ Files are created in S3 curated
- ✓ Quality reports are generated
- ✓ No access denied errors in logs

---

### PHASE 4: Athena Query Tests with Data

#### Step 4.1: Execute test queries in Athena

Once the Glue job has processed data, execute these queries in Athena:

```sql
-- 1. Verify you can query the curated table
SELECT COUNT(*) as total_records
FROM beauty_products_db.curated_beauty_products;

-- 2. Simple query with filters
SELECT 
    product_name,
    shop_name,
    item_sold,
    revenue_usd
FROM beauty_products_db.curated_beauty_products
WHERE year = 2024
LIMIT 10;

-- 3. Aggregated query
SELECT 
    l1_category,
    SUM(item_sold) as total_items,
    SUM(revenue_usd) as total_revenue
FROM beauty_products_db.curated_beauty_products
GROUP BY l1_category
ORDER BY total_revenue DESC;

-- 4. Query quality metrics
SELECT 
    job_run_id,
    total_records,
    records_passed,
    pass_rate,
    avg_quality_score
FROM beauty_products_metadata_db.data_quality_metrics
ORDER BY execution_timestamp DESC
LIMIT 10;
```

**Expected Result:**
- ✓ All queries execute without errors
- ✓ Correct results are displayed
- ✓ No permission errors

---

### PHASE 5: Specific Permission Verification

#### Step 5.1: Verify Glue CANNOT do SELECT on tables (ETL only)

```powershell
# This should work because Glue has SELECT permissions for ETL
# But it should not be able to do ad-hoc queries like Athena
# (This is validated in practice when you execute the job)
```

#### Step 5.2: Verify Athena CANNOT modify data

```sql
-- This MUST fail - Athena only has SELECT
INSERT INTO beauty_products_db.curated_beauty_products 
VALUES (...);

-- This also MUST fail
DELETE FROM beauty_products_db.curated_beauty_products;
```

**Expected Result:**
- ✗ Write operations fail with permission error
- ✓ Only SELECT operations work

---

## Complete Validation Checklist

### Basic Tests
- [ ] Automated test script executes without errors
- [ ] Glue can access databases
- [ ] Glue can access tables
- [ ] Athena can list databases
- [ ] Athena can list tables

### Permission Tests
- [ ] Glue ETL permissions configured (CREATE_TABLE, ALTER, DROP)
- [ ] Athena permissions configured (DESCRIBE, SELECT)
- [ ] S3 location permissions configured (DATA_LOCATION_ACCESS)
- [ ] S3 buckets registered in Lake Formation

### Functional Tests
- [ ] Glue job can execute without permission errors
- [ ] Glue job can read from S3 raw
- [ ] Glue job can write to S3 curated
- [ ] Glue job can write to S3 metadata
- [ ] Athena can execute SELECT queries
- [ ] Athena CANNOT execute INSERT/DELETE (security)

### Integration Tests
- [ ] Data processed by Glue is accessible in Athena
- [ ] Quality metrics are generated correctly
- [ ] Lineage tracking works
- [ ] No errors in CloudWatch logs

---

## Troubleshooting

### Error: "AccessDeniedException" in Glue

**Cause:** Lake Formation permissions not configured correctly

**Solution:**
1. Verify permissions with: `terraform state show aws_lakeformation_permissions.glue_etl_*`
2. Verify that the Glue role has the correct permissions
3. Verify that Lake Formation is enabled for the database

### Error: "AccessDeniedException" in Athena

**Cause:** SELECT permissions not granted to Athena

**Solution:**
1. Verify permissions with: `terraform state show aws_lakeformation_permissions.athena_*`
2. Ensure Athena has DESCRIBE permissions on databases
3. Ensure Athena has SELECT permissions on tables

### Error: "Resource not registered" in Glue

**Cause:** S3 bucket not registered in Lake Formation

**Solution:**
1. Verify registered resources: `aws lakeformation list-resources`
2. If missing, execute: `terraform apply -target=aws_lakeformation_resource.*`

---

## Next Steps

Once all tests pass:

1. **Monitoring:** Configure CloudWatch alerts
2. **Documentation:** Document any additional configuration
3. **Optimization:** Review query performance
4. **Security:** Review access logs in CloudTrail

---

## References

- [Lake Formation Documentation](https://docs.aws.amazon.com/lake-formation/)
- [Troubleshooting Guide](docs/lake-formation-deployment-risks.md)
- [ETL Runbook](runbooks/etl-job-failure.md)
