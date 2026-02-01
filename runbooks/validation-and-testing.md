# Runbook: Validation and Testing
## Beauty Products Data Lake - End-to-End Validation

**Version:** 1.0.0  
**Last Updated:** January 24, 2026  
**Owner:** Data Engineering Team  
**Purpose:** Comprehensive validation of data quality, crawler performance, query response time, dashboard accuracy, and (when enabled) the LLM trending-products API

---

## Overview

This runbook provides step-by-step procedures to validate the Beauty Products Data Lake across five critical dimensions:

1. **Data Quality** - Verify quality reports, metrics, and framework integrity
2. **Crawler Performance** - Validate Glue crawler configuration and execution
3. **Query Response Time** - Ensure Athena queries meet SLA (< 5 seconds)
4. **Dashboard Accuracy** - Confirm CloudWatch dashboard reflects actual metrics
5. **LLM API** - Validate the trending-products/query endpoint (when LLM system is enabled)

**Prerequisites:**
- AWS CLI configured with appropriate permissions
- Access to AWS Console (CloudWatch, Athena, Glue, S3)
- `jq` installed for JSON parsing
- Environment variable set: `ENVIRONMENT={dev|staging|prod|poc}` (default: `poc`)

**Note for Local Testing:**
- Integration tests (`tests/integration_test.py`) should be executed using the AWS Glue Docker container
- **Recommended:** Use `.\scripts\test-with-aws-glue-docker.ps1` for testing
- This ensures the same environment as AWS Glue in production (Linux-based)
- See `docs/testing-with-docker.md` for complete documentation

**Estimated Duration:** 60-90 minutes for complete validation

---

## 1. Data Quality Validation

### Objective
Verify that the data quality framework functions correctly, quality reports are generated with correct schema, and metrics are coherent across S3 reports, Athena queries, and CloudWatch.

### Context
- **ETL Script:** `scripts/beauty_products_etl.py` - Generates quality reports in Step 7
- **Quality Report Path:** `s3://very-great-products-processed-us-east-1-{environment}/quality-reports/beauty-products/YYYY/MM/DD/report_{job_run_id}.json`
- **Schema Template:** `docs/quality-report-template.json`
- **Schema Definition:** `schemas/quality_report_v1.json`
- **CloudWatch Metrics:** Namespace `BeautyProducts/DataQuality` (AvgQualityScore, PassRate, ErrorRate, RecordsPassed/Warned/Failed/Duplicates)
- **Athena Table:** `beauty_products_metadata_db.data_quality_metrics`
- **Athena View:** `beauty_products_db.vw_quality_trends`

### Step 1.1: Locate Latest Quality Report

**Command:**
```bash
# Set environment (replace with your environment: dev, staging, prod, poc)
export ENVIRONMENT="poc"

# List latest quality report
aws s3 ls s3://very-great-products-processed-us-east-1-${ENVIRONMENT}/quality-reports/beauty-products/ \
  --recursive | sort | tail -1

# Alternative: List reports for today
TODAY=$(date +%Y/%m/%d)
aws s3 ls s3://very-great-products-processed-us-east-1-${ENVIRONMENT}/quality-reports/beauty-products/${TODAY}/ \
  --recursive | sort | tail -1
```

**Expected Output:**
```
2026-01-24 10:30:45    12345 quality-reports/beauty-products/2026/01/24/report_jr_20260124_103045.json
```

**Criterion:** At least one quality report exists in the expected S3 path.

---

### Step 1.2: Download and Validate Quality Report Schema

**Command:**
```bash
# Download latest report
LATEST_REPORT=$(aws s3 ls s3://very-great-products-processed-us-east-1-${ENVIRONMENT}/quality-reports/beauty-products/ \
  --recursive | sort | tail -1 | awk '{print $NF}')

aws s3 cp s3://very-great-products-processed-us-east-1-${ENVIRONMENT}/${LATEST_REPORT} /tmp/latest-quality-report.json

# Validate JSON structure
cat /tmp/latest-quality-report.json | jq '.'

# Extract key metrics
cat /tmp/latest-quality-report.json | jq '{
  job_run_id,
  execution_timestamp,
  total_records,
  records_passed,
  records_warned,
  records_failed,
  records_duplicates,
  pass_rate,
  avg_quality_score,
  quality_issues
}'
```

**Validation Checks:**

1. **Schema Compliance:**
   ```bash
   # Check required fields exist
   cat /tmp/latest-quality-report.json | jq 'has("job_run_id") and has("execution_timestamp") and has("total_records") and has("records_passed") and has("records_warned") and has("records_failed") and has("records_duplicates") and has("pass_rate") and has("avg_quality_score") and has("quality_issues")'
   # Expected: true
   ```

2. **Data Quality Thresholds:**
   ```bash
   # Extract and validate metrics
   PASS_RATE=$(cat /tmp/latest-quality-report.json | jq -r '.pass_rate')
   AVG_SCORE=$(cat /tmp/latest-quality-report.json | jq -r '.avg_quality_score')
   
   echo "Pass Rate: $PASS_RATE (target: >= 0.95)"
   echo "Avg Quality Score: $AVG_SCORE (target: >= 0.95)"
   
   # Validate thresholds
   if (( $(echo "$PASS_RATE >= 0.95" | bc -l) )) && (( $(echo "$AVG_SCORE >= 0.95" | bc -l) )); then
     echo "✓ Quality metrics meet targets"
   else
     echo "✗ Quality metrics below targets - investigate"
   fi
   ```

3. **Quality Issues Present:**
   ```bash
   # Verify quality_issues field exists and is an object
   cat /tmp/latest-quality-report.json | jq 'type(.quality_issues) == "object"'
   # Expected: true
   ```

**Criterion:** Report exists, schema matches template, `pass_rate >= 0.95`, `avg_quality_score >= 0.95`, and `quality_issues` is present.

---

### Step 1.3: Compare Quality Report with Athena Metrics

**Query:**
```sql
-- Run in Athena (workgroup: beauty-products-athena-{environment})
-- Replace {job_run_id} with the job_run_id from Step 1.2

SELECT 
    job_run_id,
    execution_timestamp,
    total_records,
    records_passed,
    records_warned,
    records_failed,
    records_duplicates,
    pass_rate,
    avg_quality_score,
    transformation_version
FROM beauty_products_metadata_db.data_quality_metrics
WHERE job_run_id = '{job_run_id}'
ORDER BY execution_timestamp DESC
LIMIT 1;
```

**Alternative: Query Latest Report:**
```sql
-- Get latest quality metrics from Athena
SELECT 
    job_run_id,
    execution_timestamp,
    total_records,
    records_passed,
    records_warned,
    records_failed,
    records_duplicates,
    pass_rate,
    avg_quality_score
FROM beauty_products_metadata_db.data_quality_metrics
ORDER BY execution_timestamp DESC
LIMIT 1;
```

**Validation:**
1. Compare `total_records`, `records_passed`, `records_warned`, `records_failed`, `records_duplicates` between S3 report and Athena query
2. Compare `pass_rate` and `avg_quality_score` (allow small rounding differences, e.g., ±0.0001)

**Criterion:** Metrics in Athena match S3 quality report (within rounding tolerance).

---

### Step 1.4: Validate Quality Trends View

**Query:**
```sql
-- Query quality trends view
SELECT 
    year,
    month_num,
    month,
    total_records,
    high_quality_count,
    medium_quality_count,
    low_quality_count,
    avg_quality_score,
    ROUND(high_quality_count * 100.0 / total_records, 2) as pass_rate_pct
FROM beauty_products_db.vw_quality_trends
WHERE year >= YEAR(CURRENT_DATE) - 1
ORDER BY year DESC, month_num DESC
LIMIT 12;
```

**Validation:**
1. Verify `total_records` matches sum of `high_quality_count + medium_quality_count + low_quality_count`
2. Verify `pass_rate_pct` aligns with quality report `pass_rate` for the same month
3. Verify `avg_quality_score` is between 0.0 and 1.0

**Criterion:** View returns data, aggregations are correct, and metrics align with quality reports.

---

### Step 1.5: Review Integration Test Coverage

**Review File:** `tests/integration_test.py`

**Current Coverage:**
- ✓ CSV read with valid data
- ✓ Transformation pipeline
- ✓ Quality scoring (basic test with invalid date penalty)
- ✓ Malformed CSV handling
- ✓ Deduplication logic
- ✓ Output schema validation

**Suggested Additional Test Cases (Document Only - Do Not Implement):**

1. **Quality Score Edge Cases:**
   - Test record with all quality flags (should score < 0.70)
   - Test record with no quality flags (should score = 1.0000)
   - Test record with multiple flags (verify cumulative penalties)

2. **Quality Routing:**
   - Test record with score 0.95 (should route to curated)
   - Test record with score 0.70 (should route to curated with warning)
   - Test record with score 0.69 (should route to quarantine)

3. **Anomaly Detection:**
   - Test record with revenue > ANOMALY_REVENUE_MAX
   - Test record with items_sold > ANOMALY_ITEMS_MAX

4. **Quality Report Generation:**
   - Test that quality report JSON matches schema
   - Test that quality_issues dictionary is populated correctly
   - Test pass_rate calculation with mixed pass/warn/fail records

**Criterion:** Integration tests cover transformations and quality scoring. Additional cases documented for future implementation.

---

### Data Quality Validation Summary

**Success Criteria:**
- ✓ Quality reports generated in expected S3 path
- ✓ Report schema matches `quality_report_v1.json`
- ✓ `pass_rate >= 0.95` and `avg_quality_score >= 0.95`
- ✓ Metrics in Athena match S3 quality report
- ✓ Quality trends view returns correct aggregations
- ✓ Integration tests cover core quality logic

**Status:** ☐ Pass / ☐ With caveats / ☐ Fail

**Notes:**
```
[Document any issues found during validation]
```

---

## 2. Crawler Performance Validation

### Objective
Verify that Glue crawlers are correctly configured, can be executed, and their performance can be measured.

### Context
- **Raw Crawler:** `beauty-products-raw-crawler` (on-demand, no schedule)
- **Quality Crawler:** `beauty-products-quality-crawler` (scheduled: `cron(0 3 * * ? *)` - daily at 3 AM UTC)
- **Terraform Config:** `terraform/glue-crawlers.tf`
- **IAM Role:** `GlueETLRole-BeautyProducts` (used by crawlers)

### Step 2.1: Review Crawler Configuration

**Review Terraform:**
```bash
# Review crawler configuration
cat terraform/glue-crawlers.tf
```

**Validation Checklist:**

1. **Raw Crawler:**
   - ✓ Name: `beauty-products-raw-crawler`
   - ✓ Database: `beauty_products_db`
   - ✓ S3 Path: `s3://{raw-bucket}/landing/beauty-products/`
   - ✓ Schedule: None (on-demand only)
   - ✓ Schema Change Policy: `delete_behavior = "LOG"`, `update_behavior = "LOG"`

2. **Quality Crawler:**
   - ✓ Name: `beauty-products-quality-crawler`
   - ✓ Database: `beauty_products_metadata_db`
   - ✓ S3 Path: `s3://{curated-bucket}/quality-reports/beauty-products/`
   - ✓ Schedule: `cron(0 3 * * ? *)` (daily at 3 AM UTC)
   - ✓ Schema Change Policy: `delete_behavior = "LOG"`, `update_behavior = "LOG"`

3. **IAM Permissions:**
   - ✓ Crawler role has S3 read access to source paths
   - ✓ Crawler role has Glue Catalog write access

**Criterion:** Crawlers configured correctly in Terraform.

---

### Step 2.2: Verify Crawler IAM Permissions

**Command:**
```bash
# Get crawler role ARN
CRAWLER_ROLE=$(aws iam get-role --role-name GlueETLRole-BeautyProducts --query 'Role.Arn' --output text)
echo "Crawler Role: $CRAWLER_ROLE"

# List attached policies
aws iam list-attached-role-policies --role-name GlueETLRole-BeautyProducts

# Check inline policies
aws iam list-role-policies --role-name GlueETLRole-BeautyProducts
```

**Validation:**
- Verify role has `AWSGlueServiceRole` policy attached
- Verify custom S3 access policy includes read access to raw and curated buckets
- Verify role has Glue Catalog permissions

**Criterion:** IAM role has necessary permissions for crawlers.

---

### Step 2.3: Start Crawlers and Monitor Execution

**Command:**
```bash
# Start raw crawler (on-demand)
aws glue start-crawler --name beauty-products-raw-crawler

# Start quality crawler (if not scheduled, or to test immediately)
aws glue start-crawler --name beauty-products-quality-crawler

# Wait a few seconds, then check status
sleep 10

# Get crawler status
aws glue get-crawler --name beauty-products-raw-crawler \
  --query 'Crawler.State' --output text

aws glue get-crawler --name beauty-products-quality-crawler \
  --query 'Crawler.State' --output text
```

**Expected States:**
- `READY` - Crawler is ready to run
- `RUNNING` - Crawler is currently executing
- `STOPPING` - Crawler is stopping

---

### Step 2.4: Get Crawler Execution Metrics

**Command:**
```bash
# Get last run information for raw crawler
aws glue get-crawler --name beauty-products-raw-crawler \
  --query 'Crawler.LastCrawl.{State:State,Message:Message,LogGroup:LogGroup,LogStream:LogStream,StartTime:StartTime}' \
  --output json

# Get last run information for quality crawler
aws glue get-crawler --name beauty-products-quality-crawler \
  --query 'Crawler.LastCrawl.{State:State,Message:Message,LogGroup:LogGroup,LogStream:LogStream,StartTime:StartTime}' \
  --output json

# Get crawler metrics (if available via CloudWatch)
# Note: Glue crawlers don't publish standard CloudWatch metrics, so we rely on LastCrawl info
```

**Validation:**
1. Check `State` - should be `SUCCEEDED` for successful runs
2. Check `Message` - should not contain errors
3. Check `StartTime` - verify crawler ran recently (if scheduled)
4. Check `LogStream` - can be used to view detailed logs in CloudWatch

**Alternative: Get Crawler Metrics via CLI:**
```bash
# List all crawler runs (requires custom script or manual check in console)
# For now, use get-crawler to see last run info

# Check if tables were updated
aws glue get-tables --database-name beauty_products_db --query 'TableList[?Name==`raw_beauty_products`].UpdateTime' --output text

aws glue get-tables --database-name beauty_products_metadata_db --query 'TableList[?Name==`data_quality_metrics`].UpdateTime' --output text
```

**Criterion:** Crawlers can be started, execute successfully, and update Glue Catalog tables.

---

### Step 2.5: Verify Tables Updated by Crawlers

**Command:**
```bash
# Check raw table metadata
aws glue get-table \
  --database-name beauty_products_db \
  --name raw_beauty_products \
  --query 'Table.{Name:Name,UpdateTime:UpdateTime,StorageDescriptor:StorageDescriptor.Location}' \
  --output json

# Check quality metrics table metadata
aws glue get-table \
  --database-name beauty_products_metadata_db \
  --name data_quality_metrics \
  --query 'Table.{Name:Name,UpdateTime:UpdateTime,StorageDescriptor:StorageDescriptor.Location}' \
  --output json
```

**Validation:**
- Verify `UpdateTime` is recent (within last 24 hours for scheduled crawler)
- Verify `Location` matches expected S3 paths
- Verify table schema is correct

**Criterion:** Tables updated by crawlers reflect current S3 data structure.

---

### Crawler Performance Validation Summary

**Success Criteria:**
- ✓ Crawlers correctly configured in Terraform
- ✓ IAM roles have necessary permissions
- ✓ Crawlers can be started via CLI
- ✓ Crawlers execute successfully (State = SUCCEEDED)
- ✓ Tables updated after crawler runs
- ✓ Crawler duration can be measured via LastCrawl.StartTime

**Status:** ☐ Pass / ☐ With caveats / ☐ Fail

**Notes:**
```
[Document any issues found during validation]

Note: Glue crawlers do not publish standard CloudWatch metrics. Performance is validated via:
- Crawler state (SUCCEEDED/FAILED)
- LastCrawl.StartTime (duration can be calculated if end time is available)
- Table UpdateTime (confirms crawler ran and updated schema)
```

---

## 3. Query Response Time Validation

### Objective
Verify that Athena queries against Glue Catalog tables and views meet the SLA of < 5 seconds for standard aggregations.

### Context
- **Workgroup:** `beauty-products-athena-{environment}` (defined in `terraform/athena-workgroup.tf`)
- **Views:** Defined in `athena-views.sql`
  - `vw_high_quality_products`
  - `vw_sales_by_category_month`
  - `vw_quality_trends`
  - `vw_product_performance`
  - `vw_shop_leaderboard`
- **SLA:** < 5 seconds for queries with `LIMIT 10` (per `deployment-checklist.md` Step 14 and `README.md`)

### Step 3.1: Verify Views Use Correct Tables and Partitions

**Review:** `athena-views.sql`

**Validation Checklist:**

1. **View: `vw_high_quality_products`**
   - ✓ Uses table: `beauty_products_db.curated_beauty_products`
   - ✓ Filters by `data_quality_score >= 0.95`
   - ✓ Orders by `month DESC, revenue_usd DESC`

2. **View: `vw_sales_by_category_month`**
   - ✓ Uses table: `beauty_products_db.curated_beauty_products`
   - ✓ Groups by `year`, `month_num`, `month`, categories
   - ✓ Filters by `data_quality_score >= 0.70`
   - ✓ Uses partition columns (`year`, `month_num`) in GROUP BY

3. **View: `vw_quality_trends`**
   - ✓ Uses table: `beauty_products_db.curated_beauty_products`
   - ✓ Groups by `year`, `month_num`, `month`
   - ✓ Uses partition columns in GROUP BY

4. **View: `vw_product_performance`**
   - ✓ Uses table: `beauty_products_db.curated_beauty_products`
   - ✓ Filters by `data_quality_score >= 0.70`
   - ✓ Aggregates across partitions

5. **View: `vw_shop_leaderboard`**
   - ✓ Uses table: `beauty_products_db.curated_beauty_products`
   - ✓ Filters by `data_quality_score >= 0.70`
   - ✓ Aggregates by `shop_name`

**Criterion:** All views use Glue Catalog tables and leverage partition columns where applicable.

---

### Step 3.2: Measure Query Response Time for Each View

**Prerequisites:**
- Get workgroup name: `terraform output -raw athena_workgroup_name` (or use `beauty-products-athena-{environment}`)
- Ensure you have Athena query permissions

**Commands:**

```bash
# Set workgroup name
export WORKGROUP="beauty-products-athena-${ENVIRONMENT}"
export RESULT_LOCATION="s3://very-great-products-metadata-us-east-1-${ENVIRONMENT}/athena-results/"

# Function to execute query and measure time
measure_query_time() {
  local query="$1"
  local view_name="$2"
  
  echo "Testing view: $view_name"
  
  # Start query execution
  EXECUTION_ID=$(aws athena start-query-execution \
    --query-string "$query" \
    --work-group "$WORKGROUP" \
    --result-configuration "OutputLocation=$RESULT_LOCATION" \
    --query 'QueryExecutionId' \
    --output text)
  
  echo "Query Execution ID: $EXECUTION_ID"
  
  # Wait for query to complete
  while true; do
    STATUS=$(aws athena get-query-execution \
      --query-execution-id "$EXECUTION_ID" \
      --query 'QueryExecution.Status.State' \
      --output text)
    
    if [ "$STATUS" = "SUCCEEDED" ] || [ "$STATUS" = "FAILED" ] || [ "$STATUS" = "CANCELLED" ]; then
      break
    fi
    
    echo "Status: $STATUS - waiting..."
    sleep 2
  done
  
  # Get execution statistics
  aws athena get-query-execution \
    --query-execution-id "$EXECUTION_ID" \
    --query 'QueryExecution.Statistics' \
    --output json
  
  # Extract engine execution time (milliseconds)
  ENGINE_TIME=$(aws athena get-query-execution \
    --query-execution-id "$EXECUTION_ID" \
    --query 'QueryExecution.Statistics.EngineExecutionTimeInMillis' \
    --output text)
  
  echo "Engine Execution Time: ${ENGINE_TIME} ms"
  
  # Check if meets SLA (< 5000 ms)
  if [ "$ENGINE_TIME" -lt 5000 ]; then
    echo "✓ Query meets SLA (< 5 seconds)"
  else
    echo "✗ Query exceeds SLA (>= 5 seconds)"
  fi
  
  echo "---"
}

# Test each view
measure_query_time \
  "SELECT * FROM beauty_products_db.vw_high_quality_products LIMIT 10" \
  "vw_high_quality_products"

measure_query_time \
  "SELECT * FROM beauty_products_db.vw_sales_by_category_month LIMIT 10" \
  "vw_sales_by_category_month"

measure_query_time \
  "SELECT * FROM beauty_products_db.vw_quality_trends LIMIT 10" \
  "vw_quality_trends"

measure_query_time \
  "SELECT * FROM beauty_products_db.vw_product_performance LIMIT 10" \
  "vw_product_performance"

measure_query_time \
  "SELECT * FROM beauty_products_db.vw_shop_leaderboard LIMIT 10" \
  "vw_shop_leaderboard"
```

**Alternative: Manual Testing via Athena Console**

1. Navigate to Athena Console
2. Select workgroup: `beauty-products-athena-{environment}`
3. For each view, run: `SELECT * FROM beauty_products_db.{view_name} LIMIT 10`
4. Note the execution time shown in the query results
5. Verify it's < 5 seconds

**Criterion:** All views return results in < 5000 ms (5 seconds) for `LIMIT 10` queries.

---

### Step 3.3: Document Query Performance Results

**Template:**
```
View Performance Results:
- vw_high_quality_products: {time} ms - ☐ Meets SLA / ☐ Exceeds SLA
- vw_sales_by_category_month: {time} ms - ☐ Meets SLA / ☐ Exceeds SLA
- vw_quality_trends: {time} ms - ☐ Meets SLA / ☐ Exceeds SLA
- vw_product_performance: {time} ms - ☐ Meets SLA / ☐ Exceeds SLA
- vw_shop_leaderboard: {time} ms - ☐ Meets SLA / ☐ Exceeds SLA
```

**If Query Exceeds SLA:**
- Check if partitions are being used (verify `year`/`month_num` filters in WHERE clause)
- Check data volume (large datasets may require optimization)
- Consider adding more specific filters
- Review Athena query execution plan

---

### Step 3.4: Verify SLA Documentation

**Check Files:**
- `deployment-checklist.md` Step 14: "Performance acceptable (< 5 seconds)"
- `README.md`: "Query Performance: < 5 seconds (standard aggregations)"

**Proposed Addition to README.md (Text Only - Do Not Edit):**

```
**Query Performance SLA:**
- Standard aggregations with LIMIT 10: < 5 seconds
- Full table scans: Performance varies by data volume
- Partitioned queries (with year/month filters): < 3 seconds
```

**Criterion:** SLA of < 5 seconds is documented and measurable.

---

### Query Response Time Validation Summary

**Success Criteria:**
- ✓ Views use Glue Catalog tables and partition columns
- ✓ All views return results in < 5 seconds for LIMIT 10 queries
- ✓ Query execution time can be measured via AWS CLI or Console
- ✓ SLA of < 5 seconds is documented

**Status:** ☐ Pass / ☐ With caveats / ☐ Fail

**Notes:**
```
[Document query execution times and any performance issues]

Performance Measurement:
- Metric: EngineExecutionTimeInMillis from get-query-execution
- Criterion: < 5000 ms for LIMIT 10 queries
- If exceeded: Investigate partition usage, data volume, query optimization
```

---

## 4. Dashboard Accuracy Validation

### Objective
Verify that the CloudWatch dashboard accurately reflects data quality metrics from the ETL pipeline and quality reports.

### Context
- **Dashboard:** `beauty-products-pipeline-metrics` (defined in `terraform/cloudwatch.tf`)
- **Widgets:** Job status, data quality metrics, record counts, alerts, logs
- **Metric Namespaces:**
  - `BeautyProducts/DataQuality` - Custom metrics from ETL
  - `BeautyProducts/ETL` - Job completion metrics
  - `BeautyProducts/DataChanges` - Data change traceability
  - `AWS/Glue` - Standard Glue metrics
- **Quality Report Source:** S3 quality reports (Step 1)

### Step 4.1: Review Dashboard Configuration

**Review:** `terraform/cloudwatch.tf` (lines 274-506)

**Validation Checklist:**

1. **Widget: Glue Job Task Status**
   - ✓ Metrics: `AWS/Glue` - `glue.driver.aggregate.numCompletedTasks`, `numFailedTasks`
   - ✓ Dimensions: `JobName = beauty-products-etl-job`
   - ✓ Period: 300 seconds

2. **Widget: Job Completions**
   - ✓ Metrics: `BeautyProducts/ETL` - `JobCompletionCount`
   - ✓ Period: 3600 seconds

3. **Widget: Data Changes**
   - ✓ Metrics: `BeautyProducts/DataChanges` - `DataChangeCount`
   - ✓ Period: 3600 seconds

4. **Widget: Average Quality Score**
   - ✓ Metrics: `BeautyProducts/DataQuality` - `AvgQualityScore`
   - ✓ Dimensions: `JobName = beauty-products-etl-job`
   - ✓ Statistic: Average
   - ✓ Period: 3600 seconds
   - ✓ Y-axis: 0 to 1

5. **Widget: Pass Rate**
   - ✓ Metrics: `BeautyProducts/DataQuality` - `PassRate`
   - ✓ Dimensions: `JobName = beauty-products-etl-job`
   - ✓ Statistic: Average
   - ✓ Period: 3600 seconds
   - ✓ Y-axis: 0 to 100

6. **Widget: Error Rate**
   - ✓ Metrics: `BeautyProducts/DataQuality` - `ErrorRate`
   - ✓ Dimensions: `JobName = beauty-products-etl-job`
   - ✓ Statistic: Average
   - ✓ Period: 3600 seconds

7. **Widget: Records by Quality Tier**
   - ✓ Metrics: `BeautyProducts/DataQuality` - `RecordsPassed`, `RecordsWarned`, `RecordsFailed`, `RecordsDuplicates`
   - ✓ Dimensions: `JobName = beauty-products-etl-job`
   - ✓ Statistic: Sum
   - ✓ Period: 3600 seconds

8. **Widget: Alerts and Errors**
   - ✓ Metrics: `BeautyProducts/DataQuality` - `QualityAlertCount`, `ErrorCount`
   - ✓ Statistic: Sum
   - ✓ Period: 3600 seconds

**Criterion:** Dashboard widgets reference correct namespaces, metrics, and dimensions.

---

### Step 4.2: Extract Metrics from Latest Quality Report

**Command:**
```bash
# Use the quality report downloaded in Step 1.2
cat /tmp/latest-quality-report.json | jq '{
  avg_quality_score,
  pass_rate,
  records_passed,
  records_warned,
  records_failed,
  records_duplicates,
  execution_timestamp
}'
```

**Note the values:**
- `avg_quality_score`: {value}
- `pass_rate`: {value} (as decimal, e.g., 0.95)
- `records_passed`: {value}
- `records_warned`: {value}
- `records_failed`: {value}
- `records_duplicates`: {value}
- `execution_timestamp`: {timestamp}

---

### Step 4.3: Query CloudWatch Metrics for Comparison

**Command:**
```bash
# Set time range (last hour, or adjust based on job execution time)
END_TIME=$(date -u +%Y-%m-%dT%H:%M:%S)
START_TIME=$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S)

# Get AvgQualityScore
aws cloudwatch get-metric-statistics \
  --namespace "BeautyProducts/DataQuality" \
  --metric-name "AvgQualityScore" \
  --dimensions Name=JobName,Value=beauty-products-etl-job \
  --start-time "$START_TIME" \
  --end-time "$END_TIME" \
  --period 3600 \
  --statistics Average \
  --output json | jq '.'

# Get PassRate
aws cloudwatch get-metric-statistics \
  --namespace "BeautyProducts/DataQuality" \
  --metric-name "PassRate" \
  --dimensions Name=JobName,Value=beauty-products-etl-job \
  --start-time "$START_TIME" \
  --end-time "$END_TIME" \
  --period 3600 \
  --statistics Average \
  --output json | jq '.'

# Get RecordsPassed
aws cloudwatch get-metric-statistics \
  --namespace "BeautyProducts/DataQuality" \
  --metric-name "RecordsPassed" \
  --dimensions Name=JobName,Value=beauty-products-etl-job \
  --start-time "$START_TIME" \
  --end-time "$END_TIME" \
  --period 3600 \
  --statistics Sum \
  --output json | jq '.'

# Get RecordsWarned
aws cloudwatch get-metric-statistics \
  --namespace "BeautyProducts/DataQuality" \
  --metric-name "RecordsWarned" \
  --dimensions Name=JobName,Value=beauty-products-etl-job \
  --start-time "$START_TIME" \
  --end-time "$END_TIME" \
  --period 3600 \
  --statistics Sum \
  --output json | jq '.'

# Get RecordsFailed
aws cloudwatch get-metric-statistics \
  --namespace "BeautyProducts/DataQuality" \
  --metric-name "RecordsFailed" \
  --dimensions Name=JobName,Value=beauty-products-etl-job \
  --start-time "$START_TIME" \
  --end-time "$END_TIME" \
  --period 3600 \
  --statistics Sum \
  --output json | jq '.'

# Get RecordsDuplicates
aws cloudwatch get-metric-statistics \
  --namespace "BeautyProducts/DataQuality" \
  --metric-name "RecordsDuplicates" \
  --dimensions Name=JobName,Value=beauty-products-etl-job \
  --start-time "$START_TIME" \
  --end-time "$END_TIME" \
  --period 3600 \
  --statistics Sum \
  --output json | jq '.'
```

**Validation:**
1. Compare `AvgQualityScore` from CloudWatch with `avg_quality_score` from quality report
2. Compare `PassRate` from CloudWatch (as percentage) with `pass_rate * 100` from quality report
3. Compare `RecordsPassed`, `RecordsWarned`, `RecordsFailed`, `RecordsDuplicates` (Sum) with quality report values

**Note:** CloudWatch metrics may have slight delays (1-2 minutes). If metrics are missing, wait a few minutes and retry.

---

### Step 4.4: Visual Comparison in Dashboard

**Steps:**
1. Navigate to CloudWatch Console → Dashboards → `beauty-products-pipeline-metrics`
2. Set time range to last 1 hour (or time range covering latest ETL job)
3. Compare dashboard values with quality report values

**Comparison Table:**
```
Metric                    | Quality Report | CloudWatch Dashboard | Match?
------------------------- | -------------- | -------------------- | ------
Avg Quality Score         | {value}        | {value}              | ☐ Yes / ☐ No
Pass Rate (%)             | {value}%       | {value}%             | ☐ Yes / ☐ No
Records Passed            | {value}        | {value}              | ☐ Yes / ☐ No
Records Warned            | {value}        | {value}              | ☐ Yes / ☐ No
Records Failed            | {value}        | {value}              | ☐ Yes / ☐ No
Records Duplicates        | {value}        | {value}              | ☐ Yes / ☐ No
```

**Tolerance:**
- `AvgQualityScore`: ±0.01 (rounding differences)
- `PassRate`: ±1% (percentage conversion)
- Record counts: Exact match (Sum aggregation)

---

### Step 4.5: Identify Potential Discrepancies

**Common Causes of Discrepancies:**

1. **Metric Delay:**
   - CloudWatch custom metrics can take 1-2 minutes to appear
   - **Check:** Wait 5 minutes after job completion and retry

2. **Aggregation Period:**
   - Dashboard uses 3600-second (1 hour) period
   - If multiple jobs ran in the hour, values are aggregated
   - **Check:** Ensure only one job ran in the time window

3. **Different Job Runs:**
   - Dashboard may show metrics from a different job run
   - **Check:** Compare `execution_timestamp` from quality report with CloudWatch metric timestamps

4. **Unit Conversion:**
   - `PassRate` in quality report is decimal (0.95), dashboard shows percentage (95%)
   - **Check:** Multiply quality report value by 100 for comparison

5. **Missing Metrics:**
   - Metrics may not be published if job failed early
   - **Check:** Verify job completed successfully

**Criterion:** Dashboard metrics align with quality report values (within tolerance).

---

### Dashboard Accuracy Validation Summary

**Success Criteria:**
- ✓ Dashboard widgets reference correct namespaces and metrics
- ✓ CloudWatch metrics can be queried via CLI
- ✓ Dashboard values match quality report values (within tolerance)
- ✓ Discrepancies can be explained (delay, aggregation, etc.)

**Status:** ☐ Pass / ☐ With caveats / ☐ Fail

**Notes:**
```
[Document any discrepancies and their causes]

Validation Approach:
1. Extract metrics from latest quality report (Step 1.2)
2. Query CloudWatch metrics for same time period
3. Compare values (accounting for aggregation and unit conversion)
4. Visual inspection in CloudWatch dashboard
5. Document any discrepancies and root causes
```

---

## 5. LLM Trending Products API Validation

**Applicable when:** LLM system is enabled (`enable_llm_system = true`) and Lambda orchestrator is deployed.

### Objective

Verify that the `POST /trending-products/query` API endpoint accepts authenticated requests, returns a valid report, and completes within the expected latency (target 20–25 seconds end-to-end).

### Context

- **Endpoint:** `https://{api-id}.execute-api.{region}.amazonaws.com/{stage}/trending-products/query`
- **Method:** POST
- **Auth:** Cognito User Pool (Bearer JWT in `Authorization` header)
- **Body:** `{ "query": "What are the top trending products in Skincare?" }` (natural language; required field: `query`)
- **Terraform output:** `terraform output -raw api_gateway_url`
- **Script:** `.\scripts\call-api-llm.ps1` (from project root)

### Step 5.1: Obtain API URL and Cognito Credentials

**Commands:**

```bash
cd terraform
terraform output -raw api_gateway_url
terraform output -raw cognito_user_pool_id
terraform output -raw cognito_client_id
```

**Criterion:** You have the API URL and Cognito client ID. A test user must exist (e.g. created per [terraform/README-LLM.md](../terraform/README-LLM.md#step-1-create-test-user-required-once)).

### Step 5.2: Call the API (Postman or Script)

**Option A – PowerShell script (recommended):**

```powershell
# From project root
.\scripts\call-api-llm.ps1
```

**Option B – Postman (or curl):**

1. **Get IdToken:** Use Cognito `USER_PASSWORD_AUTH` with the test user (e.g. `verygreat@test.com` / `VeryGreat123!`). Use the returned `IdToken`.
2. **Request:**
   - Method: POST
   - URL: value of `api_gateway_url`
   - Headers: `Authorization: Bearer <IdToken>`, `Content-Type: application/json`
   - Body (raw JSON): `{ "query": "What are the top trending products in Skincare?" }`
3. Send the request.

**Criterion:** Response status 200 and JSON body contains `status`, `report`, `product_count`.

### Step 5.3: Validate Response Structure

**Checks:**

1. **Status:** `status` is `"success"`.
2. **Body fields:** `request_id`, `query`, `category`, `report`, `pdf_url` (or null), `execution_time_ms`, `product_count` are present.
3. **Category:** `category` matches the extracted L2 category (e.g. `"Skincare"`).
4. **Report:** `report` is an object with at least `query`, `category`, `generated_at`, and a products array.
5. **Latency (optional):** `execution_time_ms` is typically under 30000 ms (target 20000–25000 ms).

**Example success response (abbreviated):**

```json
{
  "status": "success",
  "request_id": "...",
  "query": "What are the top trending products in Skincare?",
  "category": "Skincare",
  "report": { "query": "...", "category": "Skincare", "products": [...] },
  "pdf_url": "https://...",
  "execution_time_ms": 22000,
  "product_count": 5
}
```

**Criterion:** Response structure matches the above; no client-side parsing errors.

### Step 5.4: Optional – Check Lambda Logs

**Command:**

```bash
aws logs tail /aws/lambda/beauty-products-llm-orchestrator-{environment} --follow
```

Run a request and confirm logs show successful steps (Athena query, Bedrock processing, PDF generation) and no errors.

**Criterion:** Logs show completion without exceptions for the test query.

### LLM API Validation Summary

**Success Criteria:**

- ✓ API URL and Cognito credentials obtained
- ✓ POST with Bearer token and body `{ "query": "..." }` returns 200
- ✓ Response includes `status`, `report`, `product_count`, `execution_time_ms`
- ✓ `category` extracted correctly; report structure valid
- ✓ (Optional) Lambda logs show successful execution

**Status:** ☐ Pass / ☐ With caveats / ☐ Fail

**Notes:**

```
[Document any API errors, timeouts, or missing fields]
```

---

## Overall Validation Summary

### Completion Checklist

- [ ] **Data Quality:** All steps completed, criteria met
- [ ] **Crawler Performance:** All steps completed, criteria met
- [ ] **Query Response Time:** All steps completed, criteria met
- [ ] **Dashboard Accuracy:** All steps completed, criteria met
- [ ] **LLM API** (if enabled): All steps completed, criteria met

### Final Status

| Validation Area          | Status                           | Notes                                    |
| ------------------------ | -------------------------------- | ---------------------------------------- |
| Data Quality             | ☐ Pass / ☐ With caveats / ☐ Fail |                                          |
| Crawler Performance      | ☐ Pass / ☐ With caveats / ☐ Fail |                                          |
| Query Response Time      | ☐ Pass / ☐ With caveats / ☐ Fail |                                          |
| Dashboard Accuracy       | ☐ Pass / ☐ With caveats / ☐ Fail |                                          |
| LLM API (if enabled)     | ☐ Pass / ☐ With caveats / ☐ Fail |                                          |

### Issues Found

```
[List any issues discovered during validation]
```

### Recommendations

```
[List recommendations for improvements]
```

---

## Related Documentation

- **Quality Report Template:** `docs/quality-report-template.json`
- **Quality Report Schema:** `schemas/quality_report_v1.json`
- **Data Quality Investigation:** `runbooks/data-quality-investigation.md`
- **Athena Views:** `athena-views.sql`
- **Crawler Configuration:** `terraform/glue-crawlers.tf`
- **CloudWatch Dashboard:** `terraform/cloudwatch.tf`
- **Deployment Checklist:** `deployment-checklist.md`
- **Integration Tests:** `tests/integration_test.py`
- **LLM Architecture:** `docs/LLM-TRENDING-PRODUCTS-ARCHITECTURE.md`
- **LLM Deployment & Testing:** `terraform/README-LLM.md`

---

**Validation Date:** _______________  
**Validated By:** _______________  
**Environment:** _______________
