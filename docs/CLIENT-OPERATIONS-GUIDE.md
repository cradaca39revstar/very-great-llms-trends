# Client Operations Guide
## Beauty Products Data Lake

**Version:** 1.0.0  
**Last Updated:** January 26, 2026

---

## Overview

This guide provides procedures for daily operations, maintenance, and support of the Beauty Products Data Lake. It covers common tasks, troubleshooting, and best practices for operating the system.

---

## Daily Operations

### Data Upload Procedures

#### Standard Upload Process

1. **Prepare CSV File**
   - Ensure file follows expected schema (11 columns)
   - Name format: `beauty-products_YYYYMMDD.csv`
   - Validate file encoding (UTF-8 recommended)

2. **Upload to S3 Raw Bucket**
   ```bash
   # Get bucket name (replace {environment} with your environment)
   RAW_BUCKET="very-great-products-raw-us-east-1-{environment}"
   
   # Create date-based folder structure
   DATE=$(date +%Y/%m/%d)  # Format: YYYY/MM/DD
   
   # Upload file
   aws s3 cp beauty-products_20240126.csv \
     s3://${RAW_BUCKET}/landing/beauty-products/${DATE}/beauty-products_$(date +%Y%m%d).csv
   ```

3. **Verify Upload**
   ```bash
   aws s3 ls s3://${RAW_BUCKET}/landing/beauty-products/${DATE}/
   ```

**Important Notes:**
- Files are processed automatically at 2 AM UTC daily
- For immediate processing, manually trigger the Glue job (see below)
- Ensure folder date matches filename date for consistency

#### Using Upload Script

PowerShell script available:
```powershell
.\scripts\upload_to_s3.ps1 -FilePath "path\to\file.csv" -Environment "poc"
```

Python script available:
```bash
python scripts/upload_to_s3.py --file path/to/file.csv --environment poc
```

### Job Monitoring

#### Check Job Status

**Via AWS Console:**
1. Navigate to: AWS Console → Glue → Jobs
2. Select: `beauty-products-etl-job`
3. View recent runs and status

**Via AWS CLI:**
```bash
# Get job name
JOB_NAME="beauty-products-etl-job"

# List recent runs
aws glue get-job-runs --job-name ${JOB_NAME} --max-results 10

# Get specific run status
aws glue get-job-run --job-name ${JOB_NAME} --run-id <run-id>
```

#### Monitor Job Execution

**CloudWatch Logs:**
1. AWS Console → CloudWatch → Log groups
2. Navigate to: `/aws-glue/jobs/beauty-products-etl-job`
3. View real-time logs during execution

**CloudWatch Dashboard:**
1. AWS Console → CloudWatch → Dashboards
2. Open: `beauty-products-pipeline-metrics`
3. Monitor:
   - Job completion status
   - Quality metrics
   - Record counts
   - Error rates

#### Manual Job Trigger

For immediate processing (outside scheduled time):

```bash
# Start job run
aws glue start-job-run --job-name beauty-products-etl-job
```

**Note**: Job runs are limited to 1 concurrent execution by default.

### Quality Report Review

#### Access Quality Reports

**List Reports:**
```bash
CURATED_BUCKET="very-great-products-processed-us-east-1-{environment}"

# List all reports
aws s3 ls s3://${CURATED_BUCKET}/quality-reports/beauty-products/ --recursive

# Get latest report
LATEST_REPORT=$(aws s3 ls s3://${CURATED_BUCKET}/quality-reports/beauty-products/ \
  --recursive | sort | tail -1 | awk '{print $NF}')

echo "Latest report: ${LATEST_REPORT}"
```

**Download and Review:**
```bash
# Download latest report
aws s3 cp s3://${CURATED_BUCKET}/${LATEST_REPORT} quality-report.json

# View report (requires jq)
cat quality-report.json | jq '.'
```

**Key Metrics to Review:**
- `pass_rate`: Should be >= 0.95 (95%)
- `avg_quality_score`: Should be >= 0.95
- `records_passed`: Count of high-quality records
- `records_failed`: Count of records in quarantine
- `quality_issues`: Breakdown of issue types

#### Quality Report Interpretation

**Good Quality Indicators:**
- Pass rate >= 95%
- Average quality score >= 0.95
- Low error rate (< 5%)
- Minimal quality issues

**Warning Indicators:**
- Pass rate 85-95%
- Average quality score 0.80-0.95
- Moderate quality issues

**Action Required:**
- Pass rate < 85%
- Average quality score < 0.80
- High error rate (> 5%)
- Significant quality issues

**See**: [Data Quality Investigation Runbook](../runbooks/data-quality-investigation.md) for detailed procedures.

### Alert Response Procedures

#### CloudWatch Alarm: Job Failure

**Trigger**: Glue job state = FAILED

**Actions:**
1. Check CloudWatch Logs for error details
2. Review job run history for patterns
3. Check S3 bucket permissions
4. Verify script path is correct
5. Review [ETL Job Failure Runbook](../runbooks/etl-job-failure.md)

**Resolution Steps:**
- Fix underlying issue (permissions, script error, etc.)
- Re-run job manually if needed
- Monitor next scheduled run

#### CloudWatch Alarm: Low Quality Score

**Trigger**: Average quality score < 0.80

**Actions:**
1. Review quality report for issue breakdown
2. Check source data quality
3. Review quality rules and thresholds
4. Investigate specific quality flags
5. Review [Data Quality Investigation Runbook](../runbooks/data-quality-investigation.md)

**Resolution Steps:**
- Address data quality issues at source
- Adjust quality thresholds if needed (requires code change)
- Review transformation logic

#### CloudWatch Alarm: High Error Rate

**Trigger**: Error rate > 5%

**Actions:**
1. Check error bucket for failed records
2. Review quarantine bucket for low-quality records
3. Analyze error patterns
4. Check for schema changes in source data
5. Review job logs for transformation errors

**Resolution Steps:**
- Fix data issues at source
- Update transformation logic if needed
- Review and adjust anomaly detection thresholds

---

## Maintenance Tasks

### Monthly Tasks

#### Quality Trend Analysis

1. **Query Quality Trends View:**
   ```sql
   SELECT 
       year,
       month,
       total_records,
       avg_quality_score,
       pass_rate_pct
   FROM beauty_products_db.vw_quality_trends
   WHERE year >= YEAR(CURRENT_DATE) - 1
   ORDER BY year DESC, month_num DESC;
   ```

2. **Review Trends:**
   - Identify declining quality patterns
   - Compare month-over-month metrics
   - Document any anomalies

3. **Action Items:**
   - Address declining quality trends
   - Update documentation if needed
   - Report findings to stakeholders

#### Cost Review

1. **Check AWS Cost Explorer:**
   - Filter by project tags
   - Review S3 storage costs
   - Review Glue job execution costs
   - Review Athena query costs

2. **Optimization Opportunities:**
   - Review S3 lifecycle policies
   - Optimize Glue job worker configuration
   - Review Athena query patterns

### Quarterly Tasks

#### Schema Review

1. **Review Schema Evolution:**
   - Check for new columns in source data
   - Review schema change logs
   - Update documentation

2. **Schema Updates:**
   - Follow [Schema Evolution Runbook](../runbooks/schema-evolution.md)
   - Test changes in dev environment
   - Deploy to production

#### Performance Review

1. **Query Performance:**
   - Review Athena query execution times
   - Identify slow queries
   - Optimize partition usage

2. **ETL Performance:**
   - Review job execution duration
   - Check for performance degradation
   - Optimize worker configuration if needed

### Annual Tasks

#### Governance Review

1. **Data Governance:**
   - Review data governance charter
   - Update business glossary
   - Review data retention policies

2. **Access Review:**
   - Audit IAM roles and permissions
   - Review S3 bucket access
   - Update access controls as needed

#### Disaster Recovery Testing

1. **Backup Verification:**
   - Verify S3 versioning is enabled
   - Test data recovery procedures
   - Document recovery time objectives (RTO)

2. **Failover Testing:**
   - Test job re-run procedures
   - Verify data consistency
   - Document lessons learned

---

## Common Tasks

### How to Upload New Data Files

**Step-by-Step:**

1. **Prepare File:**
   - Ensure CSV format with correct schema
   - Validate data quality
   - Name file: `beauty-products_YYYYMMDD.csv`

2. **Upload to S3:**
   ```bash
   aws s3 cp beauty-products_20240126.csv \
     s3://very-great-products-raw-us-east-1-{environment}/landing/beauty-products/2024/01/26/beauty-products_20240126.csv
   ```

3. **Verify Upload:**
   ```bash
   aws s3 ls s3://very-great-products-raw-us-east-1-{environment}/landing/beauty-products/2024/01/26/
   ```

4. **Wait for Processing:**
   - Job runs automatically at 2 AM UTC
   - Or trigger manually (see Job Monitoring section)

5. **Verify Results:**
   - Check CloudWatch dashboard
   - Review quality report
   - Query curated data in Athena

### How to Query Data with Athena

**Basic Query:**
```sql
-- Query curated data
SELECT 
    product_name,
    shop_name,
    SUM(revenue_usd) as total_revenue
FROM beauty_products_db.curated_beauty_products
WHERE year = 2024
  AND data_quality_score >= 0.95
GROUP BY product_name, shop_name
ORDER BY total_revenue DESC
LIMIT 10;
```

**Using Views:**
```sql
-- High quality products only
SELECT * FROM beauty_products_db.vw_high_quality_products
WHERE month >= DATE '2024-01-01'
LIMIT 100;

-- Sales by category
SELECT * FROM beauty_products_db.vw_sales_by_category_month
WHERE l1_category = 'Beauty & Personal Care'
ORDER BY total_revenue_usd DESC;
```

**Performance Tips:**
- Always filter by `year` and `month_num` when possible
- Use views for common query patterns
- Limit result sets for exploratory queries

### How to Investigate Quality Issues

1. **Review Quality Report:**
   - Download latest quality report
   - Identify issue types and counts
   - Review quality flags breakdown

2. **Query Quality Metrics:**
   ```sql
   -- Get quality metrics from Athena
   SELECT 
       job_run_id,
       execution_timestamp,
       total_records,
       records_passed,
       records_failed,
       avg_quality_score,
       pass_rate
   FROM beauty_products_metadata_db.data_quality_metrics
   ORDER BY execution_timestamp DESC
   LIMIT 10;
   ```

3. **Investigate Specific Issues:**
   - Query records with specific quality flags
   - Review source data for patterns
   - Check transformation logic

4. **Take Action:**
   - Fix data at source if possible
   - Update transformation logic if needed
   - Document findings

**See**: [Data Quality Investigation Runbook](../runbooks/data-quality-investigation.md) for detailed procedures.

### How to Handle Job Failures

1. **Identify Failure:**
   - Check CloudWatch alarm
   - Review job run status
   - Check CloudWatch Logs

2. **Analyze Error:**
   - Review error messages in logs
   - Check for permission issues
   - Verify script and data availability

3. **Resolve Issue:**
   - Fix underlying problem
   - Update configuration if needed
   - Re-run job manually

4. **Verify Resolution:**
   - Monitor next job run
   - Check quality metrics
   - Confirm data is processed

**See**: [ETL Job Failure Runbook](../runbooks/etl-job-failure.md) for detailed procedures.

---

## Troubleshooting

### Common Issues

#### Job Not Running

**Symptoms:**
- No job runs scheduled
- EventBridge rule not triggering

**Solutions:**
- Verify EventBridge rule is enabled
- Check rule schedule (should be `cron(0 2 * * ? *)`)
- Verify Glue job exists and is active
- Check IAM permissions for EventBridge

#### No Data in Curated Bucket

**Symptoms:**
- Job completes successfully
- No files in curated bucket

**Solutions:**
- Check job logs for errors
- Verify S3 write permissions
- Check bucket policies
- Review transformation logic

#### Athena Queries Return No Results

**Symptoms:**
- Tables exist in Glue Catalog
- Queries return empty results

**Solutions:**
- Run Glue crawlers manually
- Verify data exists in S3
- Check table partitions
- Verify Athena workgroup configuration

#### Quality Scores Too Low

**Symptoms:**
- Pass rate below 95%
- Many records in quarantine

**Solutions:**
- Review source data quality
- Check quality rules and thresholds
- Investigate specific quality flags
- Review transformation logic

### Log Access Procedures

#### CloudWatch Logs

**Access:**
1. AWS Console → CloudWatch → Log groups
2. Navigate to: `/aws-glue/jobs/beauty-products-etl-job`
3. Select log stream for specific job run
4. View log events

**Search Logs:**
- Use CloudWatch Logs Insights
- Filter by error messages
- Search for specific patterns

#### Glue Job Logs

**Access:**
1. AWS Console → Glue → Jobs
2. Select: `beauty-products-etl-job`
3. Click on job run
4. View logs in "Output" tab

### Error Code Reference

**Common Error Codes:**

- **AccessDenied**: IAM permission issue
  - Solution: Check IAM role permissions
- **NoSuchBucket**: S3 bucket not found
  - Solution: Verify bucket names in job parameters
- **InvalidInput**: Data format issue
  - Solution: Check source data format
- **ResourceLimitExceeded**: AWS service limit
  - Solution: Request limit increase

---

## Support Contacts

### Technical Support Escalation

**Level 1 - Basic Issues:**
- Review this operations guide
- Check runbooks for specific scenarios
- Review CloudWatch logs

**Level 2 - Complex Issues:**
- Contact system administrator
- Provide job run ID and error details
- Include relevant log excerpts

**Level 3 - Critical Issues:**
- Escalate to data engineering team
- Provide full error context
- Include troubleshooting steps taken

### Data Governance Questions

- Contact data steward
- Review [Data Governance Charter](../governance/data-governance-charter.md)
- Consult business glossary

### Infrastructure Issues

- Contact AWS support (if applicable)
- Review Terraform configuration
- Check AWS service health dashboard

---

## Best Practices

### Data Upload

- Always validate CSV format before upload
- Use consistent file naming convention
- Maintain folder structure (YYYY/MM/DD)
- Verify uploads before job execution

### Monitoring

- Review CloudWatch dashboard daily
- Check quality reports after each job run
- Monitor alarm status regularly
- Set up email notifications

### Query Optimization

- Always use partition filters (year, month_num)
- Use views for common queries
- Limit result sets for exploration
- Review query execution plans

### Maintenance

- Perform monthly quality reviews
- Keep documentation updated
- Review costs quarterly
- Test disaster recovery annually

---

## Related Documentation

- [Architecture Overview](ARCHITECTURE.md) - System architecture
- [Deployment Guide](CLIENT-DEPLOYMENT-GUIDE.md) - Deployment procedures
- [Runbooks](../runbooks/) - Detailed operational procedures
- [Data Quality Investigation](../runbooks/data-quality-investigation.md) - Quality troubleshooting
- [ETL Job Failure](../runbooks/etl-job-failure.md) - Job failure recovery

---

**Last Reviewed:** _______________  
**Reviewed By:** _______________
