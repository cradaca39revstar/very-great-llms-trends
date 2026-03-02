# Client Operations Guide
## Beauty Products Data Lake + LLM Product Innovation Engine

**Version:** 2.0.0  
**Last Updated:** February 26, 2026

---

## Overview

This guide covers day-to-day operations of the Beauty Products system, including data uploads, monitoring, user management, and troubleshooting common issues.

---

## 1. Daily Operations

### 1.1 Automated ETL Schedule

The Glue ETL job runs **automatically every day at 2:00 AM UTC** via EventBridge. No manual action is required unless the job fails.

**Verify last run:**

```sh
aws glue get-job-runs --job-name beauty-products-etl-job --max-results 1 \
  --query "JobRuns[0].{State:JobRunState,Start:StartedOn,Duration:ExecutionTime}"
```

---

### 1.2 Uploading New Data

Upload CSV files to the S3 raw zone. The path must follow the date partition:

```powershell
$ENV = "dev"   # Replace with your environment
$DATE = (Get-Date).ToString("yyyy/MM/dd")
aws s3 cp your-data-file.csv `
  "s3://very-great-products-raw-us-east-1-$ENV/landing/beauty-products/$DATE/"
```

**CSV file requirements:**

| Column | Type | Notes |
|--------|------|-------|
| Month | String | Format: `Jan-2026` or `2026-01` |
| Product Id | Integer | Must be a positive number |
| Product Name | String | Required, non-empty |
| Shop Name | String | Required |
| L1 category | String | Top-level category |
| L2 category | String | Used by the LLM system to match queries |
| L3 category | String | Optional sub-category |
| Item Sold | Integer | Must be >= 0 |
| Revenue | Decimal | USD, must be >= 0 |
| Avg. Unit Price | Decimal | USD, must be >= 0 |
| MoM Growth % | Decimal | Month-over-month growth percentage |

After upload, the ETL will pick up the file at the next scheduled run (2 AM UTC), or you can trigger it manually.

---

### 1.3 Triggering the ETL Job Manually

```powershell
aws glue start-job-run --job-name beauty-products-etl-job
```

Monitor progress:

```powershell
aws glue get-job-runs --job-name beauty-products-etl-job --max-results 1
```

Job typically completes in **5–8 minutes** for files up to 10K records.

---

## 2. Monitoring

### 2.1 CloudWatch Dashboards

**Data Lake Dashboard:**
- URL: AWS Console → CloudWatch → Dashboards → `beauty-products-pipeline-metrics`
- Shows: Job success rate, data quality score trend, records by quality tier, error rate

**LLM System Dashboard:**
- URL: AWS Console → CloudWatch → Dashboards → `beauty-products-llm-dashboard`
- Shows: Report request volume, average latency, error count, Bedrock/Athena/PDF durations
- Or from CLI: `terraform output -raw cloudwatch_llm_dashboard_url`

### 2.2 CloudWatch Alarms

| Alarm | Trigger | Action |
|-------|---------|--------|
| `beauty-products-job-failure` | Glue job FAILED | Email via SNS |
| `beauty-products-low-quality` | Avg quality score < 0.80 | Email via SNS |
| `beauty-products-high-error-rate` | Error rate > 5% | Email via SNS |
| LLM error alarms | Lambda errors > threshold | CloudWatch alert |

**Check alarm status:**

```powershell
aws cloudwatch describe-alarms --alarm-name-prefix "beauty-products" `
  --query "MetricAlarms[*].{Name:AlarmName,State:StateValue}"
```

### 2.3 Checking Data Freshness

```sql
-- In Athena (workgroup: beauty-products-athena-{environment})
SELECT MAX(processed_timestamp) as last_processed,
       COUNT(*) as total_records
FROM beauty_products_db.curated_beauty_products;
```

### 2.4 LLM Request Audit Logs

All report requests are logged to DynamoDB for 90 days:

```powershell
aws dynamodb scan `
  --table-name beauty-products-prompt-logs-dev `
  --limit 10 `
  --query "Items[*].{id:request_id.S,user:user_email.S,status:status.S,time_ms:execution_time_ms.N}"
```

View Lambda logs in real-time:

```powershell
aws logs tail /aws/lambda/beauty-products-llm-orchestrator-dev --follow
```

---

## 3. How to Query Data with Athena

### 3.1 Access the Athena Query Editor

1. Go to **AWS Console** → **Amazon Athena**
2. Select workgroup: `beauty-products-athena-{environment}` (e.g. `beauty-products-athena-dev`)
3. Select database: `beauty_products_db`

### 3.2 Common Queries

**Top products by revenue (current year):**

```sql
SELECT product_name, shop_name, l2_category,
       SUM(revenue_usd) as total_revenue,
       SUM(item_sold) as total_items
FROM beauty_products_db.curated_beauty_products
WHERE data_quality_score >= 0.95
  AND year = 2026
GROUP BY product_name, shop_name, l2_category
ORDER BY total_revenue DESC
LIMIT 20;
```

**Top 5 products per L2 category (used by LLM system):**

```sql
SELECT l2_category, product_name, shop_name,
       revenue_usd, mom_growth_pct, item_sold
FROM beauty_products_db.curated_beauty_products
WHERE l2_category = 'Skincare'
  AND data_quality_score >= 0.95
ORDER BY revenue_usd DESC
LIMIT 5;
```

**Available categories:**

```sql
SELECT DISTINCT l2_category, COUNT(*) as products
FROM beauty_products_db.curated_beauty_products
WHERE data_quality_score >= 0.95
GROUP BY l2_category
ORDER BY products DESC;
```

**Pre-built views (faster queries):**

```sql
SELECT * FROM beauty_products_db.vw_high_quality_products LIMIT 10;
SELECT * FROM beauty_products_db.vw_sales_by_category_month LIMIT 10;
SELECT * FROM beauty_products_db.vw_shop_leaderboard LIMIT 10;
SELECT * FROM beauty_products_db.vw_product_performance LIMIT 10;
SELECT * FROM beauty_products_db.vw_quality_trends LIMIT 10;
```

---

## 4. User Management

### 4.1 Creating New Users

```powershell
cd terraform
$USER_POOL_ID = terraform output -raw cognito_user_pool_id

aws cognito-idp admin-create-user `
  --user-pool-id $USER_POOL_ID `
  --username user@example.com `
  --user-attributes Name=email,Value=user@example.com `
  --temporary-password "TempPass123!" `
  --message-action SUPPRESS

# Set permanent password
aws cognito-idp admin-set-user-password `
  --user-pool-id $USER_POOL_ID `
  --username user@example.com `
  --password "PermanentPass123!" `
  --permanent
```

**Password requirements:** Minimum 8 characters, at least one uppercase, one lowercase, one number.

### 4.2 Listing Users

```powershell
$USER_POOL_ID = (cd terraform; terraform output -raw cognito_user_pool_id)
aws cognito-idp list-users --user-pool-id $USER_POOL_ID `
  --query "Users[*].{Username:Username,Status:UserStatus,Created:UserCreateDate}"
```

### 4.3 Disabling / Deleting a User

```powershell
# Disable (user cannot log in but account is kept)
aws cognito-idp admin-disable-user --user-pool-id $USER_POOL_ID --username user@example.com

# Delete permanently
aws cognito-idp admin-delete-user --user-pool-id $USER_POOL_ID --username user@example.com
```

---

## 5. How to Handle Job Failures

### 5.1 ETL Job Failure

**Symptoms:** CloudWatch alarm fires, ETL job state = FAILED

**Step 1 — Check the error:**

```powershell
aws glue get-job-runs --job-name beauty-products-etl-job --max-results 1 `
  --query "JobRuns[0].{State:JobRunState,Error:ErrorMessage}"
```

**Step 2 — Check full logs:**

```powershell
aws logs tail /aws-glue/jobs/beauty-products-etl-job --follow
```

**Step 3 — Common causes and fixes:**

| Error | Cause | Fix |
|-------|-------|-----|
| `FileNotFoundError` | No CSV in S3 landing path | Upload a CSV file before triggering |
| `Schema mismatch` | CSV has wrong columns | Verify CSV format against the 11-column schema |
| `Access denied` | IAM permissions | Verify Glue IAM role has S3 read access |
| `Out of memory` | File too large for 2 G.1X workers | Increase workers in Terraform: `glue_worker_count = 4` |

**Step 4 — Retry:**

```powershell
aws glue start-job-run --job-name beauty-products-etl-job
```

Full runbook: [`runbooks/etl-job-failure.md`](../runbooks/etl-job-failure.md)

---

### 5.2 LLM Report Generation Failure

**Symptoms:** Frontend shows error, or `status: "failed"` in API response

**Step 1 — Check the request logs:**

```powershell
aws logs filter-log-events `
  --log-group-name /aws/lambda/beauty-products-llm-orchestrator-dev `
  --filter-pattern "ERROR"
```

**Step 2 — Common errors and fixes:**

| Error Code | Description | Fix |
|------------|-------------|-----|
| `TRD001` | Missing `query` field in request | Verify the request body includes `{ "query": "..." }` |
| `TRD002` | L2 category not recognized | Check that the query contains a valid category name |
| `TRD003` | No products for category in last 30 days | Upload data for that category and re-run ETL |
| `TRD004` | Athena query failed | Check Athena workgroup and database configuration |
| `TRD005` | Bedrock brand generation failed | Check Bedrock model access and Lambda IAM permissions |
| `TRD006` | Product ideas generation failed | Same as TRD005 |
| `TRD007` | Internal server error | Check Lambda logs for full stack trace |

**Step 3 — Check Bedrock model access:**

```powershell
aws bedrock list-foundation-models --region us-east-1 `
  --query "modelSummaries[?modelId=='amazon.nova-pro-v1:0'].{id:modelId,status:modelLifecycle}"
```

---

## 6. How to Investigate Quality Issues

**Symptoms:** Low quality score alarm, high quarantine rate

**Step 1 — Check quality report:**

```powershell
$ENV = "dev"
aws s3 ls "s3://very-great-products-processed-us-east-1-$ENV/quality-reports/beauty-products/" `
  --recursive | Sort-Object | Select-Object -Last 1
```

Download and inspect:

```powershell
aws s3 cp s3://very-great-products-processed-us-east-1-$ENV/quality-reports/.../report.json report.json
```

**Step 2 — Query quarantined records:**

```sql
-- In Athena — view records that failed quality
SELECT quality_flags, COUNT(*) as count
FROM beauty_products_db.curated_beauty_products
WHERE data_quality_score < 0.70
GROUP BY quality_flags
ORDER BY count DESC;
```

**Step 3 — Fix source data:**
- Correct the quality issues in the source CSV (invalid dates, missing product names, negative revenue, etc.)
- Re-upload corrected file and re-run ETL

Full runbook: [`runbooks/data-quality-investigation.md`](../runbooks/data-quality-investigation.md)

---

## 7. Schema Changes

If the source CSV format changes (new columns, renamed columns, type changes), follow the schema evolution runbook before uploading new data:

Full runbook: [`runbooks/schema-evolution.md`](../runbooks/schema-evolution.md)

**Key principle:** The raw zone uses schema-on-read (all STRING). Changes to business columns require updates to `glue-catalog.tf` and the ETL script.

---

## 8. Data Retention Policies

| Data Zone | Retention | Location |
|-----------|-----------|----------|
| Raw zone (CSVs) | 1 year | `s3://very-great-products-raw-us-east-1-{env}/` |
| Curated zone (Parquet) | 7 years | `s3://very-great-products-processed-us-east-1-{env}/curated/` |
| Quality reports | 7 years | `s3://very-great-products-processed-us-east-1-{env}/quality-reports/` |
| Quarantine zone | 90 days | `s3://very-great-products-processed-us-east-1-{env}/quarantine/` |
| PDF reports | 7 days | `s3://beauty-products-pdfs-us-east-1-{env}/reports/` |
| Product images | 7 days | `s3://beauty-products-pdfs-us-east-1-{env}/images/` |
| DynamoDB audit logs | 90 days (TTL) | `beauty-products-prompt-logs-{env}` |
| DynamoDB report status | 90 days (TTL) | `beauty-products-report-status-{env}` |

---

## 9. Cost Management

**Monitor costs:** AWS Console → Cost Explorer → filter by tag `Project = BeautyProductsDataLake`

**Main cost drivers:**
- **Bedrock Nova Pro:** ~$0.08–0.15 per report (text generation)
- **Stability AI SD 3.5 (us-west-2):** ~$0.04–0.08 per image (5 images per report)
- **Glue ETL:** ~$0.44/DPU-hour
- **Athena:** $5.00 per TB scanned

**Cost optimization tips:**
- Use Parquet format and partition pruning in Athena queries to minimize data scanned
- Set `pdf_expiration_days` to the minimum needed (currently 7 days)
- Consider provisioned concurrency for Lambda only if usage is consistently high

---

## 10. Support Contacts

| Issue Type | Resource |
|------------|----------|
| ETL failures | [`runbooks/etl-job-failure.md`](../runbooks/etl-job-failure.md) |
| Data quality issues | [`runbooks/data-quality-investigation.md`](../runbooks/data-quality-investigation.md) |
| Schema changes | [`runbooks/schema-evolution.md`](../runbooks/schema-evolution.md) |
| LLM/API issues | Lambda CloudWatch logs |
| Security review | [`runbooks/lake-formation-security-review.md`](../runbooks/lake-formation-security-review.md) |
| End-to-end validation | [`runbooks/validation-and-testing.md`](../runbooks/validation-and-testing.md) |
| Architecture reference | [`docs/LLM-TRENDING-PRODUCTS-ARCHITECTURE.md`](LLM-TRENDING-PRODUCTS-ARCHITECTURE.md) |