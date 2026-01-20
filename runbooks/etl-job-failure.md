# Runbook: ETL Job Failure Recovery
## Beauty Products Data Lake

**Version:** 1.0.0  
**Last Updated:** January 17, 2026  
**Owner:** Data Engineering Team  

---

## Overview

This runbook provides step-by-step procedures for diagnosing and recovering from AWS Glue ETL job failures in the Beauty Products Data Lake pipeline.

**Job Name:** `beauty-products-etl-job`  
**Criticality:** High  
**SLA:** Recovery within 4 hours  

---

## Prerequisites

**Required Access:**
- AWS Console access (read-only minimum)
- AWS Glue job execution permissions (for reruns)
- S3 read access to raw and curated buckets
- CloudWatch Logs read access

**Required Tools:**
- AWS CLI installed and configured
- Access to Terraform codebase (for infrastructure issues)
- Slack/PagerDuty for team communication

---

## Alert Triggers

Job failures can be detected through:

1. **CloudWatch Alarm:** `beauty-products-job-failure`
   - Triggers when Glue job state = FAILED
   - SNS notification sent to `beauty-products-alerts` topic

2. **Manual Check:** AWS Glue Console
   - Navigate to: AWS Glue > ETL > Jobs > `beauty-products-etl-job`
   - Check "Run status" column

3. **Athena Query:** No recent data in curated table
   ```sql
   SELECT MAX(processed_timestamp) as last_load
   FROM beauty_products_db.curated_beauty_products;
   ```

---

## Triage and Diagnosis

### Step 1: Verify Job Failure

**AWS Console:**
1. Go to: AWS Glue > ETL Jobs > `beauty-products-etl-job`
2. Click "History" tab
3. Identify failed run (red status indicator)
4. Note the "Run ID" and "Started" timestamp

**AWS CLI:**
```bash
aws glue get-job-runs \
  --job-name beauty-products-etl-job \
  --max-results 5 \
  --query "JobRuns[?JobRunState=='FAILED']"
```

### Step 2: Review Error Logs

**CloudWatch Logs:**
1. Go to: CloudWatch > Log Groups > `/aws-glue/jobs/beauty-products-etl-job`
2. Filter by failed run ID or timestamp
3. Search for keywords: `ERROR`, `Exception`, `FAILED`, `Traceback`

**Common Error Patterns:**

| Error Message | Root Cause | Quick Fix |
|--------------|------------|-----------|
| `S3 Access Denied` | IAM permission issue | Verify GlueETLRole has s3:GetObject on source bucket |
| `No files found at path` | Source file missing | Check if CSV uploaded to landing/ prefix |
| `Schema mismatch` | CSV structure changed | Update Glue table schema or add columns |
| `OutOfMemoryError` | Data volume exceeded worker capacity | Increase worker count or use G.2X workers |
| `Column not found` | Code references missing column | Check CSV header matches expected columns |
| `Timeout` | Job exceeded 60-minute limit | Optimize transformations or increase timeout |

**AWS CLI to fetch logs:**
```bash
aws logs filter-log-events \
  --log-group-name /aws-glue/jobs/beauty-products-etl-job \
  --start-time $(date -d '2 hours ago' +%s)000 \
  --filter-pattern "ERROR"
```

### Step 3: Check Source Data

**Verify source file exists:**
```bash
aws s3 ls s3://very-great-products-raw-us-east-1-poc/landing/beauty-products/$(date +%Y/%m/%d)/
```

**Download and inspect file:**
```bash
aws s3 cp s3://very-great-products-raw-us-east-1-poc/landing/beauty-products/YYYY/MM/DD/file.csv /tmp/

# Check file size
ls -lh /tmp/file.csv

# Check header and first few rows
head -5 /tmp/file.csv

# Count rows
wc -l /tmp/file.csv

# Check for malformed rows
file /tmp/file.csv
```

**Common source data issues:**
- Empty file (0 bytes)
- Missing header row
- Incorrect delimiter (semicolon instead of comma)
- Encoding issues (not UTF-8)
- Extra or missing columns

### Step 4: Check Infrastructure

**Glue Job Configuration:**
```bash
aws glue get-job --job-name beauty-products-etl-job
```

Verify:
- Script location exists in S3
- IAM role ARN is correct
- Worker type and count are appropriate
- Job parameters are set correctly

**S3 Buckets Accessibility:**
```bash
# Test read from raw bucket
aws s3 ls s3://very-great-products-raw-us-east-1-poc/landing/

# Test write to curated bucket
echo "test" | aws s3 cp - s3://very-great-products-processed-us-east-1-poc/test.txt
aws s3 rm s3://very-great-products-processed-us-east-1-poc/test.txt
```

---

## Recovery Procedures

### Scenario 1: Transient Failure (Network, Timeout)

**Symptoms:**
- Job failed with network error or timeout
- Source data is valid
- Previous runs succeeded

**Resolution:**
1. Rerun the job immediately:
   ```bash
   aws glue start-job-run --job-name beauty-products-etl-job
   ```
   
2. Monitor the new run:
   ```bash
   JOB_RUN_ID=$(aws glue get-job-runs --job-name beauty-products-etl-job --max-results 1 --query 'JobRuns[0].Id' --output text)
   
   aws glue get-job-run --job-name beauty-products-etl-job --run-id $JOB_RUN_ID --query 'JobRun.JobRunState'
   ```

3. If second attempt fails, escalate to infrastructure team

**Expected Outcome:** Job succeeds on retry

---

### Scenario 2: Source Data Issue

**Symptoms:**
- Schema mismatch error
- Malformed CSV error
- Unexpected null values

**Resolution:**

**Option A: Fix source file**
1. Contact data provider to fix and re-upload file
2. Move bad file to error prefix:
   ```bash
   aws s3 mv s3://very-great-products-raw-us-east-1-poc/landing/beauty-products/YYYY/MM/DD/bad-file.csv \
              s3://very-great-products-raw-us-east-1-poc/error/beauty-products/YYYY/MM/DD/
   ```
3. Wait for corrected file upload
4. Job will process automatically (if scheduled) or trigger manually

**Option B: Skip bad file**
1. Archive bad file:
   ```bash
   aws s3 mv s3://very-great-products-raw-us-east-1-poc/landing/beauty-products/YYYY/MM/DD/bad-file.csv \
              s3://very-great-products-raw-us-east-1-poc/archive/beauty-products/YYYY/MM/DD/skipped_$(date +%s).csv
   ```
2. Document skipped file in incident log
3. Notify data steward for follow-up

**Option C: Manually clean data**
1. Download file:
   ```bash
   aws s3 cp s3://very-great-products-raw-us-east-1-poc/landing/beauty-products/YYYY/MM/DD/file.csv /tmp/
   ```
2. Fix issues locally (add missing columns, fix encoding, etc.)
3. Upload corrected file:
   ```bash
   aws s3 cp /tmp/file-corrected.csv s3://very-great-products-raw-us-east-1-poc/landing/beauty-products/YYYY/MM/DD/file.csv
   ```
4. Rerun job

**Expected Outcome:** Valid source data processed successfully

---

### Scenario 3: Code Error (Bug in ETL Script)

**Symptoms:**
- Python exception in logs
- AttributeError, KeyError, TypeError
- Transformation logic failure

**Resolution:**

1. **Immediate Workaround:** Disable problematic transformation
   - Requires code change and deployment
   - Only if data can be loaded with reduced quality

2. **Fix and Deploy:**
   ```bash
   # 1. Pull latest code
   git pull origin main
   
   # 2. Create fix branch
   git checkout -b hotfix/etl-job-failure-YYYYMMDD
   
   # 3. Fix bug in scripts/beauty_products_etl.py
   # ... make changes ...
   
   # 4. Test locally (if possible)
   pytest tests/test_transformations.py
   
   # 5. Commit and push
   git add scripts/beauty_products_etl.py
   git commit -m "Fix: [description of bug fix]"
   git push origin hotfix/etl-job-failure-YYYYMMDD
   
   # 6. Create PR and get approval
   # ... follow change management process ...
   
   # 7. Deploy to production
   terraform apply -target=aws_s3_object.etl_script
   
   # 8. Rerun job
   aws glue start-job-run --job-name beauty-products-etl-job
   ```

3. **Post-Deployment Validation:**
   - Monitor job logs for errors
   - Verify curated data written successfully
   - Run Athena query to spot-check results

**Expected Outcome:** Bug fixed, job succeeds

---

### Scenario 4: Permission/IAM Issue

**Symptoms:**
- `Access Denied` errors in logs
- `403 Forbidden` from S3
- Unable to write to CloudWatch

**Resolution:**

1. **Verify IAM Role Permissions:**
   ```bash
   aws iam get-role --role-name GlueETLRole-BeautyProducts
   aws iam list-attached-role-policies --role-name GlueETLRole-BeautyProducts
   aws iam list-role-policies --role-name GlueETLRole-BeautyProducts
   ```

2. **Check S3 Bucket Policies:**
   ```bash
   aws s3api get-bucket-policy --bucket very-great-products-raw-us-east-1-poc
   aws s3api get-bucket-policy --bucket very-great-products-processed-us-east-1-poc
   ```

3. **Fix Permissions (via Terraform):**
   ```bash
   cd terraform/
   
   # Review IAM policy in iam.tf
   # Make necessary changes
   
   terraform plan -target=aws_iam_role_policy.glue_s3_access
   terraform apply -target=aws_iam_role_policy.glue_s3_access
   ```

4. **Rerun Job:**
   ```bash
   aws glue start-job-run --job-name beauty-products-etl-job
   ```

**Expected Outcome:** Permissions restored, job succeeds

---

### Scenario 5: Resource Exhaustion

**Symptoms:**
- `OutOfMemoryError` in logs
- Job timeout (exceeds 60 minutes)
- Executor failures

**Resolution:**

**Option A: Increase Worker Count**
```bash
aws glue update-job \
  --job-name beauty-products-etl-job \
  --job-update NumberOfWorkers=5
  
aws glue start-job-run --job-name beauty-products-etl-job
```

**Option B: Use Larger Worker Type**
```bash
aws glue update-job \
  --job-name beauty-products-etl-job \
  --job-update WorkerType=G.2X,NumberOfWorkers=2
  
aws glue start-job-run --job-name beauty-products-etl-job
```

**Option C: Increase Timeout**
```bash
aws glue update-job \
  --job-name beauty-products-etl-job \
  --job-update Timeout=120
  
aws glue start-job-run --job-name beauty-products-etl-job
```

**Long-term Fix:**
- Optimize ETL code (reduce shuffles, partition data)
- Update Terraform configuration permanently
- Implement incremental processing

**Expected Outcome:** Job completes within resource limits

---

## Reprocessing Historical Data

If job failure caused data loss, reprocess historical files:

### Step 1: Identify Missing Data

```sql
-- Check for gaps in curated data
SELECT 
    year,
    month_num,
    COUNT(*) as record_count,
    MAX(processed_timestamp) as last_processed
FROM beauty_products_db.curated_beauty_products
GROUP BY year, month_num
ORDER BY year DESC, month_num DESC;
```

### Step 2: Locate Source Files

```bash
# List files in archive (if auto-archived)
aws s3 ls s3://very-great-products-raw-us-east-1-poc/archive/beauty-products/2024/04/ --recursive

# Or check landing if still there
aws s3 ls s3://very-great-products-raw-us-east-1-poc/landing/beauty-products/2024/04/ --recursive
```

### Step 3: Restore and Reprocess

**Option A: Restore from archive**
```bash
# Copy back to landing
aws s3 cp s3://very-great-products-raw-us-east-1-poc/archive/beauty-products/2024/04/17/file.csv \
           s3://very-great-products-raw-us-east-1-poc/landing/beauty-products/2024/04/17/file.csv

# Disable job bookmark to reprocess
aws glue start-job-run \
  --job-name beauty-products-etl-job \
  --arguments='--job-bookmark-option=job-bookmark-disable'
```

**Option B: Request file from source system**
1. Contact data provider
2. Request specific date range
3. Upload to landing prefix
4. Trigger job

---

## Escalation Path

### Level 1: On-Call Data Engineer (0-2 hours)
- Initial triage and diagnosis
- Attempt recovery procedures above
- Check for known issues

### Level 2: Senior Data Engineer (2-4 hours)
- Complex debugging
- Code fixes and hotfixes
- Infrastructure changes

### Level 3: Data Architect + DevOps (4+ hours)
- Architecture issues
- AWS service outages
- Major infrastructure redesign

**Escalation Contacts:**
- On-Call Engineer: Slack #data-oncall or PagerDuty
- Senior Engineer: [email/phone]
- Data Architect: [email/phone]
- Manager: [email/phone]

---

## Post-Incident Actions

After resolving failure:

### 1. Document Incident
Create incident report with:
- Incident start and end time
- Root cause analysis
- Resolution steps taken
- Impact assessment (data loss, SLA breach)

### 2. Update Monitoring
- Add new CloudWatch alarm if gap identified
- Update alert thresholds if needed
- Enhance logging for better diagnosis

### 3. Prevent Recurrence
- Fix identified bugs
- Update documentation
- Enhance validation checks
- Consider additional testing

### 4. Communicate
- Notify stakeholders of resolution
- Update status page
- Share learnings in team retrospective

---

## Quick Reference Commands

```bash
# Check job status
aws glue get-job-runs --job-name beauty-products-etl-job --max-results 5

# Start job manually
aws glue start-job-run --job-name beauty-products-etl-job

# Check CloudWatch logs
aws logs tail /aws-glue/jobs/beauty-products-etl-job --follow

# List source files
aws s3 ls s3://very-great-products-raw-us-east-1-poc/landing/beauty-products/ --recursive

# Check curated data freshness
# (Run in Athena)
SELECT MAX(processed_timestamp) FROM beauty_products_db.curated_beauty_products;
```

---

## Related Runbooks

- [Schema Evolution](schema-evolution.md)
- [Data Quality Investigation](data-quality-investigation.md)
- [Disaster Recovery](disaster-recovery.md)

---

**Questions or Issues:** Contact #data-engineering on Slack
