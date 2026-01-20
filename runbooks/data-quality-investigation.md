# Runbook: Data Quality Investigation
## Beauty Products Data Lake

**Version:** 1.0.0  
**Last Updated:** January 17, 2026  
**Owner:** Data Steward  

---

## Overview

This runbook provides procedures for investigating data quality issues, accessing quarantine data, and implementing remediation workflows in the Beauty Products Data Lake.

**Related Metrics:**
- Data Quality Score: Target >= 0.95
- Pass Rate: Target >= 95%
- Error Rate: Target < 2%

---

## Alert Triggers

Quality issues detected through:

1. **CloudWatch Alarm:** `beauty-products-low-quality`
   - Triggers when avg quality score < 0.80
   
2. **CloudWatch Alarm:** `beauty-products-high-error-rate`
   - Triggers when error rate > 5%

3. **Quality Reports:** Review JSON reports in S3
   - Location: `s3://very-great-products-processed-us-east-1-poc/quality-reports/`

4. **Athena Query:** Check quality trends
   ```sql
   SELECT * FROM beauty_products_db.vw_quality_trends 
   WHERE avg_quality_score < 0.90 
   ORDER BY year DESC, month_num DESC;
   ```

---

## Investigation Workflow

### Step 1: Review Quality Report

**Locate Latest Report:**
```bash
aws s3 ls s3://very-great-products-processed-us-east-1-poc/quality-reports/beauty-products/$(date +%Y/%m/%d)/ \
  --recursive | sort | tail -1
```

**Download and Review:**
```bash
REPORT_PATH="s3://very-great-products-processed-us-east-1-poc/quality-reports/beauty-products/2024/04/17/report_jr_20240417_123456.json"

aws s3 cp $REPORT_PATH /tmp/quality-report.json

cat /tmp/quality-report.json | jq '.'
```

**Key Metrics to Check:**
- `total_records`: Should match expected volume
- `pass_rate`: Should be >= 0.95
- `avg_quality_score`: Should be >= 0.95
- `quality_issues`: Breakdown by issue type
- `records_failed`: Count of quarantined records

**Example Report:**
```json
{
  "job_run_id": "jr_20240417_123456",
  "execution_timestamp": "2024-04-17T12:34:56Z",
  "total_records": 10000,
  "records_passed": 8500,
  "records_warned": 1200,
  "records_failed": 300,
  "pass_rate": 0.85,
  "quality_issues": {
    "INVALID_DATE": 150,
    "SYNTHETIC_PRODUCT_ID": 100,
    "MISSING_PRODUCT_NAME": 50
  },
  "avg_quality_score": 0.8234
}
```

---

### Step 2: Query Quality Trends

**Check Historical Trends:**
```sql
-- View quality score trends over time
SELECT 
    month,
    total_records,
    high_quality_count,
    medium_quality_count,
    low_quality_count,
    avg_quality_score,
    ROUND(high_quality_count * 100.0 / total_records, 2) as pass_rate_pct
FROM beauty_products_db.vw_quality_trends
WHERE year >= 2024
ORDER BY year DESC, month_num DESC;
```

**Identify Anomalies:**
```sql
-- Find sudden quality drops
WITH quality_trends AS (
    SELECT 
        month,
        avg_quality_score,
        LAG(avg_quality_score) OVER (ORDER BY year, month_num) as prev_score
    FROM beauty_products_db.vw_quality_trends
)
SELECT 
    month,
    avg_quality_score,
    prev_score,
    ROUND((avg_quality_score - prev_score) * 100, 2) as score_change_pct
FROM quality_trends
WHERE (avg_quality_score - prev_score) < -0.05  -- 5% drop
ORDER BY month DESC;
```

---

### Step 3: Analyze Quality Flags

**Quality Flags Breakdown:**
```sql
-- Count records by quality flag type
SELECT 
    quality_flags,
    COUNT(*) as record_count,
    ROUND(AVG(data_quality_score), 4) as avg_score,
    SUM(revenue_usd) as total_revenue_affected
FROM beauty_products_db.curated_beauty_products
WHERE quality_flags IS NOT NULL 
  AND quality_flags != ''
  AND month >= DATE '2024-04-01'
GROUP BY quality_flags
ORDER BY record_count DESC
LIMIT 20;
```

**Flag Frequency Over Time:**
```sql
-- Track specific flag over time
SELECT 
    year,
    month_num,
    month,
    COUNT(CASE WHEN quality_flags LIKE '%INVALID_DATE%' THEN 1 END) as invalid_date_count,
    COUNT(CASE WHEN quality_flags LIKE '%SYNTHETIC_PRODUCT_ID%' THEN 1 END) as synthetic_id_count,
    COUNT(CASE WHEN quality_flags LIKE '%MISSING_PRODUCT_NAME%' THEN 1 END) as missing_name_count,
    COUNT(CASE WHEN quality_flags LIKE '%INVALID_REVENUE%' THEN 1 END) as invalid_revenue_count
FROM beauty_products_db.curated_beauty_products
WHERE quality_flags IS NOT NULL AND quality_flags != ''
GROUP BY year, month_num, month
ORDER BY year DESC, month_num DESC;
```

---

### Step 4: Access Quarantine Data

**List Quarantined Records:**
```sql
-- View quarantined records
SELECT 
    quarantine_reason,
    data_quality_score,
    product_id,
    product_name,
    month,
    COUNT(*) OVER (PARTITION BY quarantine_reason) as count_by_reason
FROM beauty_products_db.quarantine_beauty_products
WHERE month >= DATE '2024-04-01'
ORDER BY data_quality_score ASC
LIMIT 100;
```

**Download Quarantine Data for Review:**
```bash
# Query and export to CSV
aws athena start-query-execution \
  --query-string "SELECT * FROM beauty_products_db.quarantine_beauty_products WHERE month = DATE '2024-04-17'" \
  --result-configuration OutputLocation=s3://aws-athena-query-results-us-east-1/

# Wait for completion and download
```

---

## Root Cause Analysis by Issue Type

### Issue: INVALID_DATE

**Symptoms:**
- Records with NULL month after parsing
- Quality flag: `INVALID_DATE`
- Penalty: -0.20

**Common Causes:**
1. Date format changed in source CSV
2. Non-standard date format (e.g., "April 1, 2024")
3. Invalid dates (e.g., "2024-13-01")
4. Empty date field

**Investigation:**
```sql
-- Find records with invalid dates
SELECT 
    source_file,
    source_record_number,
    month,
    quality_flags,
    data_quality_score
FROM beauty_products_db.curated_beauty_products
WHERE quality_flags LIKE '%INVALID_DATE%'
  AND processed_timestamp >= CURRENT_TIMESTAMP - INTERVAL '7' DAY
LIMIT 50;
```

**Check Raw Data:**
```bash
# Download source file
aws s3 cp s3://very-great-products-raw-us-east-1-poc/landing/beauty-products/2024/04/17/file.csv /tmp/

# Check Month column format
head -20 /tmp/file.csv | cut -d',' -f1

# Look for pattern
grep -E "^[^,]+" /tmp/file.csv | sort | uniq -c
```

**Remediation:**
1. **Quick Fix:** Update ETL to handle new date format
   ```python
   # Add new format to parse_date_field function
   formats = ['%m/%d/%Y', '%m/%d/%y', '%Y-%m-%d', '%B %d, %Y']  # Add new format
   ```

2. **Source Fix:** Contact data provider to standardize date format

3. **Batch Remediation:** Reprocess historical files with updated logic

---

### Issue: SYNTHETIC_PRODUCT_ID

**Symptoms:**
- Product ID could not be parsed from scientific notation
- Synthetic ID generated from hash
- Quality flag: `SYNTHETIC_PRODUCT_ID`
- Penalty: -0.15

**Common Causes:**
1. Product ID format changed (no longer scientific notation)
2. Product ID contains non-numeric characters
3. Product ID exceeds BIGINT max value

**Investigation:**
```sql
-- Find records with synthetic IDs
SELECT 
    product_id,
    product_name,
    shop_name,
    quality_flags,
    data_quality_score
FROM beauty_products_db.curated_beauty_products
WHERE quality_flags LIKE '%SYNTHETIC_PRODUCT_ID%'
  AND month >= DATE '2024-04-01'
LIMIT 50;
```

**Check for Collisions:**
```sql
-- Check if synthetic IDs collide with real IDs
SELECT 
    product_id,
    COUNT(*) as occurrence_count,
    COUNT(DISTINCT product_name) as unique_products
FROM beauty_products_db.curated_beauty_products
GROUP BY product_id
HAVING COUNT(DISTINCT product_name) > 1;
```

**Remediation:**
1. **Investigate Source:** Determine why product IDs are invalid
2. **Update Transformation:** Enhance parsing logic for new format
3. **Request Product Master:** Get canonical product ID mapping from source
4. **Document Synthetic IDs:** Track which IDs are synthetic for future reference

---

### Issue: MISSING_PRODUCT_NAME

**Symptoms:**
- Product name is NULL or empty after cleaning
- Quality flag: `MISSING_PRODUCT_NAME`
- Penalty: -0.20

**Common Causes:**
1. Source data has empty product name field
2. Product name contains only non-printable characters
3. Data extraction issue from source system

**Investigation:**
```sql
-- Find records with missing names
SELECT 
    product_id,
    shop_name,
    l1_category,
    quality_flags,
    source_file
FROM beauty_products_db.curated_beauty_products
WHERE quality_flags LIKE '%MISSING_PRODUCT_NAME%'
  AND month >= DATE '2024-04-01'
LIMIT 100;
```

**Check Raw Data:**
```bash
# Search for empty product names in source
awk -F',' '{if ($3 == "" || $3 == "\"\"") print NR, $0}' /tmp/file.csv
```

**Remediation:**
1. **Source Fix:** Request source system to populate product names
2. **Lookup Enhancement:** Implement product master lookup to backfill names
3. **Accept as Warning:** If rare, accept lower quality score for these records

---

### Issue: INVALID_REVENUE

**Symptoms:**
- Revenue could not be parsed or is negative
- Defaulted to 0.00
- Quality flag: `INVALID_REVENUE`
- Penalty: -0.15

**Common Causes:**
1. Currency format changed (different symbol or delimiter)
2. Negative revenue values (refunds?)
3. Non-numeric characters in revenue field

**Investigation:**
```sql
-- Find records with invalid revenue
SELECT 
    product_name,
    revenue_usd,
    avg_unit_price_usd,
    item_sold,
    quality_flags
FROM beauty_products_db.curated_beauty_products
WHERE quality_flags LIKE '%INVALID_REVENUE%'
  AND month >= DATE '2024-04-01'
LIMIT 50;
```

**Business Impact:**
```sql
-- Calculate potential revenue data loss
SELECT 
    COUNT(*) as affected_records,
    COUNT(*) * AVG(avg_unit_price_usd * item_sold) as estimated_lost_revenue
FROM beauty_products_db.curated_beauty_products
WHERE quality_flags LIKE '%INVALID_REVENUE%'
  AND month >= DATE '2024-04-01';
```

**Remediation:**
1. **Update Parser:** Enhance currency parsing for new formats
2. **Handle Negatives:** Decide business rule for negative revenue (refunds)
3. **Source Investigation:** Work with finance team to understand valid revenue values

---

### Issue: SUSPICIOUS_GROWTH

**Symptoms:**
- MoM growth outside reasonable range (-100% to +1000%)
- Quality flag: `SUSPICIOUS_GROWTH`
- Penalty: -0.05

**Common Causes:**
1. New product launched (first month has 0 previous revenue)
2. Product went viral (legitimate 1000%+ growth)
3. Data error in current or previous month revenue

**Investigation:**
```sql
-- Review suspicious growth records
SELECT 
    product_name,
    month,
    revenue_usd,
    mom_growth_pct,
    LAG(revenue_usd) OVER (PARTITION BY product_id ORDER BY month) as prev_month_revenue
FROM beauty_products_db.curated_beauty_products
WHERE quality_flags LIKE '%SUSPICIOUS_GROWTH%'
  AND year = 2024
ORDER BY ABS(mom_growth_pct) DESC
LIMIT 50;
```

**Remediation:**
1. **Verify Legitimate:** Cross-check with business for viral products
2. **Adjust Threshold:** If too many false positives, adjust threshold
3. **Manual Review:** Route extreme cases to business analyst for validation

---

## Remediation Workflows

### Workflow 1: Fix and Reprocess

**When to Use:** Fixable issue in ETL logic or source data

**Steps:**

1. **Identify Root Cause:** Determine exact issue
2. **Fix ETL Code:** Update transformation logic
3. **Test Fix:** Run in dev environment
4. **Deploy to Production:** Follow change management
5. **Reprocess Historical Data:**
   ```bash
   # Copy affected files back to landing
   aws s3 sync s3://.../archive/beauty-products/2024/04/ \
                s3://.../landing/beauty-products/2024/04/
   
   # Run job with bookmark disabled
   aws glue start-job-run \
     --job-name beauty-products-etl-job \
     --arguments='--job-bookmark-option=job-bookmark-disable'
   ```
6. **Validate Results:** Check quality score improved

---

### Workflow 2: Accept as Warning

**When to Use:** Issue is unavoidable but data still usable

**Steps:**

1. **Document Decision:** Why accepting lower quality
2. **Adjust Threshold:** Update warning threshold if needed
3. **Monitor Trend:** Track if issue worsens
4. **Add Business Logic:** Filter in queries if needed
   ```sql
   -- Exclude records with specific flags
   SELECT * FROM beauty_products_db.curated_beauty_products
   WHERE data_quality_score >= 0.90
     AND (quality_flags NOT LIKE '%INVALID_REVENUE%' OR quality_flags IS NULL);
   ```

---

### Workflow 3: Source Data Fix

**When to Use:** Issue is in source system, not ETL

**Steps:**

1. **Document Issue:** Create detailed report with examples
2. **Contact Source Team:** Provide specific records and patterns
3. **Request Fix Timeline:** Get ETA for source system fix
4. **Temporary Workaround:** Implement ETL workaround if critical
5. **Monitor for Fix:** Watch for improvement in future files
6. **Remove Workaround:** Clean up temporary code once source fixed

**Issue Report Template:**
```
Subject: Data Quality Issue in Beauty Products CSV Feed

Issue: Invalid date format in Month column
Severity: High (20% quality penalty)
Affected Records: ~150 per file
Business Impact: Records quarantined, revenue data missing

Examples:
- Expected: "4/01/2024"
- Actual: "April 1, 2024"

Request: Standardize date format to M/DD/YYYY

Affected Files:
- s3://.../landing/beauty-products/2024/04/15/file.csv
- s3://.../landing/beauty-products/2024/04/16/file.csv

Contact: data-steward@company.com
```

---

### Workflow 4: Manual Data Correction

**When to Use:** Small number of high-value records need manual fix

**Steps:**

1. **Export Quarantine Data:**
   ```sql
   -- Export specific records
   SELECT * FROM beauty_products_db.quarantine_beauty_products
   WHERE quarantine_reason = 'LOW_QUALITY_SCORE'
     AND data_quality_score >= 0.65  -- Close to threshold
     AND revenue_usd > 10000;  -- High value
   ```

2. **Manual Review:** Data steward reviews in spreadsheet

3. **Correct Data:** Fix issues manually

4. **Re-upload:** Create corrected CSV file

5. **Reprocess:** Run ETL on corrected file

6. **Validate:** Verify records now in curated zone

---

## Quality Monitoring Dashboard

**Create Athena View for Dashboard:**
```sql
CREATE OR REPLACE VIEW beauty_products_db.vw_quality_dashboard AS
SELECT 
    month,
    total_records,
    ROUND(high_quality_count * 100.0 / total_records, 2) as pass_rate_pct,
    ROUND(avg_quality_score, 4) as avg_score,
    CASE 
        WHEN avg_quality_score >= 0.95 THEN 'Excellent'
        WHEN avg_quality_score >= 0.80 THEN 'Good'
        WHEN avg_quality_score >= 0.70 THEN 'Acceptable'
        ELSE 'Poor'
    END as quality_rating
FROM beauty_products_db.vw_quality_trends
WHERE year >= 2024
ORDER BY year DESC, month_num DESC;
```

**QuickSight Metrics (if available):**
- Quality Score Trend Line (30 days)
- Pass Rate Gauge (target: 95%)
- Quality Issues Pie Chart
- Quarantine Record Count

---

## Escalation

**Level 1: Data Analyst (0-2 hours)**
- Review quality reports
- Query quarantine data
- Identify patterns

**Level 2: Data Steward (2-8 hours)**
- Root cause analysis
- Decide on remediation approach
- Coordinate with source teams

**Level 3: Data Architect + Governance Council (8+ hours)**
- Systemic quality issues
- Policy/threshold changes
- Major source system problems

**Escalation Criteria:**
- Pass rate < 80% for 3 consecutive days
- Quality score drop > 10% in single day
- Critical business metric affected (revenue data)

---

## Related Runbooks

- [ETL Job Failure](etl-job-failure.md)
- [Schema Evolution](schema-evolution.md)

---

**Questions:** Contact data-steward@company.com or Slack #data-quality
