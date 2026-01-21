# Deployment Checklist
## Beauty Products Data Lake

**Version:** 1.0.0  
**Project:** Beauty Products Data Lake  
**Environment:** Production  

---

## Pre-Deployment Checklist

### 1. Code Review and Testing

- [ ] All code changes peer-reviewed (minimum 2 approvers)
- [ ] Unit tests written and passing (`pytest tests/test_transformations.py`)
- [ ] Integration tests passing (`pytest tests/integration_test.py`)
- [ ] Tested with sample data in dev environment
- [ ] Performance tested with production-size dataset
- [ ] No linter errors or warnings
- [ ] Code follows project coding standards

### 2. Documentation

- [ ] README.md updated with new features
- [ ] Schema documentation updated (`schemas/curated_beauty_products_v1.json`)
- [ ] Business glossary updated if new terms added
- [ ] Source-to-target mapping updated if schema changed
- [ ] Runbooks reviewed and updated if needed
- [ ] CHANGELOG.md updated with version and changes
- [ ] API/Query examples updated if interfaces changed

### 3. Infrastructure Review

- [ ] Terraform code reviewed and validated
- [ ] `terraform plan` executed and reviewed (no unexpected changes)
- [ ] IAM permissions verified (least privilege)
- [ ] S3 bucket policies reviewed
- [ ] Encryption enabled (at rest and in transit)
- [ ] Lifecycle policies configured correctly
- [ ] CloudWatch alarms configured and tested
- [ ] SNS topics and subscriptions verified

### 4. Data Quality

- [ ] Quality rules reviewed with business stakeholders
- [ ] Quality thresholds appropriate (>= 0.95 pass, >= 0.70 warn)
- [ ] Quality report format validated
- [ ] Quarantine routing logic tested
- [ ] Deduplication logic tested
- [ ] Anomaly detection thresholds reviewed

### 5. Security and Compliance

- [ ] Security scan completed (no high/critical vulnerabilities)
- [ ] IAM roles follow least privilege principle
- [ ] S3 buckets block public access
- [ ] CloudTrail logging enabled
- [ ] Data classification tags applied
- [ ] PII handling reviewed (if applicable)
- [ ] Compliance requirements met (GDPR, SOX, etc.)
- [ ] Encryption keys managed properly

### 6. Rollback Plan

- [ ] Rollback procedure documented
- [ ] Previous version tagged in Git
- [ ] Previous Glue job script backed up in S3
- [ ] Terraform state backed up
- [ ] Rollback tested in staging environment
- [ ] Rollback decision criteria defined
- [ ] Rollback owner identified

### 7. Communication

- [ ] Stakeholders notified of upcoming deployment
- [ ] Deployment window communicated (if downtime expected)
- [ ] Release notes prepared
- [ ] Training materials updated (if UI/query changes)
- [ ] Support team briefed on changes
- [ ] Escalation contacts confirmed

---

## Deployment Steps

### Phase 1: Infrastructure Deployment (Terraform)

**Estimated Duration:** 20-30 minutes  
**Downtime:** None (infrastructure only)

#### Step 1: Deploy S3 Buckets

```bash
cd terraform/

# Review changes
terraform plan -target=aws_s3_bucket.raw \
               -target=aws_s3_bucket.curated \
               -target=aws_s3_bucket.metadata \
               -target=aws_s3_bucket.glue_scripts

# Apply
terraform apply -target=aws_s3_bucket.raw \
                -target=aws_s3_bucket.curated \
                -target=aws_s3_bucket.metadata \
                -target=aws_s3_bucket.glue_scripts
```

- [ ] S3 buckets created successfully
- [ ] Bucket policies applied
- [ ] Lifecycle policies configured
- [ ] Versioning enabled where required

#### Step 2: Deploy IAM Roles and Policies

```bash
terraform plan -target=aws_iam_role.glue_etl \
               -target=aws_iam_role.athena_query \
               -target=aws_iam_role.lambda_trigger

terraform apply -target=aws_iam_role.glue_etl \
                -target=aws_iam_role.athena_query \
                -target=aws_iam_role.lambda_trigger
```

- [ ] IAM roles created
- [ ] Policies attached
- [ ] Trust relationships configured
- [ ] Permissions validated

#### Step 3: Create Glue Data Catalog

```bash
terraform plan -target=aws_glue_catalog_database.beauty_products \
               -target=aws_glue_catalog_database.metadata \
               -target=aws_glue_catalog_table.raw_beauty_products \
               -target=aws_glue_catalog_table.curated_beauty_products \
               -target=aws_glue_catalog_table.error_beauty_products \
               -target=aws_glue_catalog_table.quarantine_beauty_products \
               -target=aws_glue_catalog_table.data_quality_metrics \
               -target=aws_glue_catalog_table.transformation_lineage

terraform apply -target=aws_glue_catalog_database.beauty_products \
                -target=aws_glue_catalog_database.metadata \
                -target=aws_glue_catalog_table.raw_beauty_products \
                -target=aws_glue_catalog_table.curated_beauty_products \
                -target=aws_glue_catalog_table.error_beauty_products \
                -target=aws_glue_catalog_table.quarantine_beauty_products \
                -target=aws_glue_catalog_table.data_quality_metrics \
                -target=aws_glue_catalog_table.transformation_lineage
```

- [ ] Databases created
- [ ] Tables defined
- [ ] Partitions configured (for curated table)
- [ ] Schema matches documentation

#### Step 4: Upload Glue ETL Script

```bash
# Upload ETL script to S3 (replace {environment} with your environment)
aws s3 cp scripts/beauty_products_etl.py \
  s3://very-great-products-glue-scripts-us-east-1-{environment}/scripts/beauty_products_etl.py

# Verify upload
aws s3 ls s3://very-great-products-glue-scripts-us-east-1-{environment}/scripts/
```

- [ ] Script uploaded successfully
- [ ] S3 path matches Glue job configuration
- [ ] Script has correct permissions

#### Step 5: Create Glue Job

```bash
terraform plan -target=aws_glue_job.beauty_products_etl

terraform apply -target=aws_glue_job.beauty_products_etl
```

- [ ] Glue job created
- [ ] Worker type and count configured (G.1X, 2 workers)
- [ ] Timeout set (60 minutes)
- [ ] Job parameters configured
- [ ] Job bookmarks enabled

#### Step 6: Setup EventBridge Schedule

```bash
terraform plan -target=aws_cloudwatch_event_rule.daily_etl \
               -target=aws_cloudwatch_event_target.glue_job \
               -target=aws_iam_role.eventbridge_glue

terraform apply -target=aws_cloudwatch_event_rule.daily_etl \
                -target=aws_cloudwatch_event_target.glue_job \
                -target=aws_iam_role.eventbridge_glue
```

- [ ] EventBridge rule created (cron: 0 2 * * ? *)
- [ ] Target configured to trigger Glue job
- [ ] IAM role for EventBridge created
- [ ] Schedule enabled

#### Step 7: Configure CloudWatch Alarms

```bash
terraform plan -target=aws_sns_topic.alerts \
               -target=aws_cloudwatch_metric_alarm.job_failure \
               -target=aws_cloudwatch_metric_alarm.low_quality \
               -target=aws_cloudwatch_metric_alarm.high_error_rate \
               -target=aws_cloudwatch_dashboard.pipeline_metrics

terraform apply -target=aws_sns_topic.alerts \
                -target=aws_cloudwatch_metric_alarm.job_failure \
                -target=aws_cloudwatch_metric_alarm.low_quality \
                -target=aws_cloudwatch_metric_alarm.high_error_rate \
                -target=aws_cloudwatch_dashboard.pipeline_metrics
```

- [ ] SNS topic created
- [ ] Email subscription confirmed (check inbox)
- [ ] Alarms created and enabled
- [ ] Dashboard created and accessible

#### Step 8: Create Glue Crawlers (Optional)

```bash
terraform plan -target=aws_glue_crawler.raw_crawler \
               -target=aws_glue_crawler.quality_crawler

terraform apply -target=aws_glue_crawler.raw_crawler \
                -target=aws_glue_crawler.quality_crawler
```

- [ ] Raw crawler created (on-demand only)
- [ ] Quality crawler created (daily schedule)
- [ ] Crawler schedules configured

---

### Phase 2: Athena Views Deployment

**Estimated Duration:** 10 minutes  
**Downtime:** None

#### Step 9: Create Athena Views

```sql
-- Execute in Athena Query Editor
-- Copy from athena-views.sql

-- View 1: High Quality Products
CREATE OR REPLACE VIEW beauty_products_db.vw_high_quality_products AS ...;

-- View 2: Sales by Category and Month
CREATE OR REPLACE VIEW beauty_products_db.vw_sales_by_category_month AS ...;

-- View 3: Quality Trends
CREATE OR REPLACE VIEW beauty_products_db.vw_quality_trends AS ...;

-- View 4: Product Performance
CREATE OR REPLACE VIEW beauty_products_db.vw_product_performance AS ...;

-- View 5: Shop Leaderboard
CREATE OR REPLACE VIEW beauty_products_db.vw_shop_leaderboard AS ...;
```

- [ ] All views created successfully
- [ ] Views queryable (test with SELECT * LIMIT 10)
- [ ] Performance acceptable

---

### Phase 3: Test End-to-End

**Estimated Duration:** 30-45 minutes  
**Downtime:** None (test run)

#### Step 10: Upload Test Data

```bash
# Create test CSV file
cat > /tmp/test-beauty-products.csv << 'EOF'
Month,Product Id,Product Name,Shop Name,L1 category,L2 category,L3 category,Item Sold,Revenue,Avg. Unit Price,MoM Growth %
4/01/2024,1.72938E+18,Test Product,TestShop,Beauty & Personal Care,Haircare,Brushes,100,$1000.00,$10.00,5%
EOF

# Upload to landing zone (replace {environment} with your environment)
aws s3 cp /tmp/test-beauty-products.csv \
  s3://very-great-products-raw-us-east-1-{environment}/landing/beauty-products/$(date +%Y/%m/%d)/test-$(date +%s).csv
```

- [ ] Test file uploaded successfully

#### Step 11: Trigger Glue Job Manually

```bash
# Start job
JOB_RUN_ID=$(aws glue start-job-run --job-name beauty-products-etl-job --query 'JobRunId' --output text)

echo "Job Run ID: $JOB_RUN_ID"

# Monitor status (repeat until SUCCEEDED or FAILED)
aws glue get-job-run --job-name beauty-products-etl-job --run-id $JOB_RUN_ID --query 'JobRun.JobRunState'
```

- [ ] Job started successfully
- [ ] Job state: RUNNING
- [ ] CloudWatch logs streaming
- [ ] Job completed: SUCCEEDED
- [ ] Job duration < 15 minutes

#### Step 12: Validate Curated Output

```sql
-- Run in Athena

-- Check record count
SELECT COUNT(*) as record_count
FROM beauty_products_db.curated_beauty_products
WHERE processed_timestamp >= CURRENT_TIMESTAMP - INTERVAL '1' HOUR;
-- Expected: 1 (test record)

-- Verify data quality
SELECT 
    product_name,
    data_quality_score,
    quality_flags,
    processed_timestamp,
    transformation_version
FROM beauty_products_db.curated_beauty_products
WHERE processed_timestamp >= CURRENT_TIMESTAMP - INTERVAL '1' HOUR;
-- Expected: Test Product, score = 1.0000, flags empty/null

-- Check partitions
SELECT DISTINCT year, month_num
FROM beauty_products_db.curated_beauty_products
ORDER BY year DESC, month_num DESC;
-- Expected: Current year/month visible
```

- [ ] Record found in curated table
- [ ] Data quality score = 1.0000 (perfect)
- [ ] All fields populated correctly
- [ ] Partition created properly
- [ ] No errors in error/quarantine buckets

#### Step 13: Verify Quality Report

```bash
# Download quality report (replace {environment} with your environment)
aws s3 ls s3://very-great-products-processed-us-east-1-{environment}/quality-reports/beauty-products/$(date +%Y/%m/%d)/ \
  | grep $JOB_RUN_ID

aws s3 cp s3://very-great-products-processed-us-east-1-{environment}/quality-reports/beauty-products/$(date +%Y/%m/%d)/report_${JOB_RUN_ID}.json /tmp/

cat /tmp/report_${JOB_RUN_ID}.json | jq '.'
```

- [ ] Quality report generated
- [ ] Report structure valid JSON
- [ ] Metrics accurate (total_records = 1, pass_rate = 1.0)

#### Step 14: Test Athena Views

```sql
-- Test each view
SELECT * FROM beauty_products_db.vw_high_quality_products LIMIT 10;
SELECT * FROM beauty_products_db.vw_sales_by_category_month LIMIT 10;
SELECT * FROM beauty_products_db.vw_quality_trends LIMIT 10;
SELECT * FROM beauty_products_db.vw_product_performance LIMIT 10;
SELECT * FROM beauty_products_db.vw_shop_leaderboard LIMIT 10;
```

- [ ] All views queryable
- [ ] Results make sense
- [ ] Performance acceptable (< 5 seconds)

#### Step 15: Test CloudWatch Alarms

```bash
# Check alarm status
aws cloudwatch describe-alarms --alarm-names beauty-products-job-failure \
                                              beauty-products-low-quality \
                                              beauty-products-high-error-rate
```

- [ ] Alarms in OK state (no false alarms from test)
- [ ] SNS email received for test run (if configured)

---

### Phase 4: Production Data Load

**Estimated Duration:** Varies by data volume  
**Downtime:** None

#### Step 16: Upload Production Data

```bash
# Coordinate with data provider to upload first production file
# Example path (replace {environment} with your environment): 
# s3://very-great-products-raw-us-east-1-{environment}/landing/beauty-products/2024/04/17/production-data.csv
```

- [ ] Production file uploaded to landing/
- [ ] File format matches expected schema
- [ ] File size reasonable (< 1GB for initial test)

#### Step 17: Monitor Production Job Run

```bash
# Job should trigger automatically via EventBridge schedule
# OR trigger manually:
aws glue start-job-run --job-name beauty-products-etl-job

# Monitor
aws glue get-job-runs --job-name beauty-products-etl-job --max-results 1
```

- [ ] Job triggered (auto or manual)
- [ ] Job running without errors
- [ ] CloudWatch logs healthy
- [ ] Job completed successfully
- [ ] Duration within SLA (< 15 min for typical file)

#### Step 18: Validate Production Output

```sql
-- Check record count matches expectation
SELECT 
    COUNT(*) as total_records,
    MIN(month) as earliest_month,
    MAX(month) as latest_month,
    AVG(data_quality_score) as avg_quality_score
FROM beauty_products_db.curated_beauty_products;

-- Check quality distribution
SELECT 
    CASE 
        WHEN data_quality_score >= 0.95 THEN 'High Quality'
        WHEN data_quality_score >= 0.70 THEN 'Medium Quality'
        ELSE 'Low Quality'
    END as quality_tier,
    COUNT(*) as record_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as percentage
FROM beauty_products_db.curated_beauty_products
GROUP BY 
    CASE 
        WHEN data_quality_score >= 0.95 THEN 'High Quality'
        WHEN data_quality_score >= 0.70 THEN 'Medium Quality'
        ELSE 'Low Quality'
    END;
```

- [ ] Record count matches expected (cross-check with source row count)
- [ ] Quality score distribution acceptable (>= 95% high quality)
- [ ] No unexpected nulls or anomalies
- [ ] Partitions created correctly

#### Step 19: Review Quality Report

```bash
# Get latest quality report (replace {environment} with your environment)
LATEST_REPORT=$(aws s3 ls s3://very-great-products-processed-us-east-1-{environment}/quality-reports/beauty-products/ --recursive | sort | tail -1 | awk '{print $NF}')

aws s3 cp s3://very-great-products-processed-us-east-1-{environment}/$LATEST_REPORT /tmp/latest-quality-report.json

cat /tmp/latest-quality-report.json | jq '.pass_rate, .avg_quality_score, .quality_issues'
```

- [ ] Pass rate >= 0.95
- [ ] Average quality score >= 0.95
- [ ] Quality issues within acceptable ranges
- [ ] No critical anomalies

---

## Post-Deployment Validation

### Step 20: Monitor for 24 Hours

**Day 1 Monitoring:**

- [ ] First scheduled job run completes successfully (2 AM UTC next day)
- [ ] No CloudWatch alarms triggered
- [ ] Data freshness acceptable (< 4 hours from file upload)
- [ ] Quality metrics stable
- [ ] No errors in CloudWatch Logs
- [ ] S3 storage costs within budget
- [ ] Glue DPU usage within budget

**Queries to Run:**

```sql
-- Data freshness check
SELECT 
    MAX(processed_timestamp) as last_load_time,
    MAX(month) as latest_data_month,
    COUNT(*) as total_records
FROM beauty_products_db.curated_beauty_products;

-- Quality trend
SELECT * FROM beauty_products_db.vw_quality_trends
ORDER BY year DESC, month_num DESC LIMIT 7;
```

### Step 21: User Acceptance Testing (UAT)

- [ ] Data analysts can query curated table
- [ ] Athena views accessible
- [ ] BI dashboard connected (if applicable)
- [ ] Query performance acceptable
- [ ] Results match business expectations
- [ ] Data quality acceptable for business use

### Step 22: Documentation Handoff

- [ ] Runbooks delivered to operations team
- [ ] Training session conducted (if needed)
- [ ] Access granted to relevant users
- [ ] Support contacts documented
- [ ] Escalation procedures communicated

---

## Rollback Procedure

**If critical issues arise:**

### Rollback Step 1: Stop Scheduled Jobs

```bash
# Disable EventBridge rule
aws events disable-rule --name beauty-products-daily-etl
```

### Rollback Step 2: Revert Glue Job Script

```bash
# Re-upload previous version from backup (replace {environment} with your environment)
aws s3 cp s3://very-great-products-glue-scripts-us-east-1-{environment}/scripts/backup/beauty_products_etl_v0.9.0.py \
          s3://very-great-products-glue-scripts-us-east-1-{environment}/scripts/beauty_products_etl.py
```

### Rollback Step 3: Revert Terraform Changes

```bash
cd terraform/

# Checkout previous version
git checkout v0.9.0

# Apply previous configuration
terraform plan
terraform apply
```

### Rollback Step 4: Notify Stakeholders

- [ ] Send rollback notification
- [ ] Explain reason for rollback
- [ ] Provide timeline for fix
- [ ] Update status page

---

## Post-Deployment Checklist

- [ ] All deployment steps completed successfully
- [ ] Production data loaded and validated
- [ ] CloudWatch monitoring active
- [ ] Alerts configured and tested
- [ ] Documentation updated
- [ ] Users trained and have access
- [ ] Rollback plan verified
- [ ] Lessons learned documented
- [ ] Project marked as complete in tracking system

---

## Sign-Off

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Data Engineer | | | |
| Data Steward | | | |
| Data Architect | | | |
| Project Manager | | | |

---

**Deployment Date:** _______________  
**Deployment Status:** ☐ Success ☐ Partial ☐ Rollback Required  
**Notes:**

---
