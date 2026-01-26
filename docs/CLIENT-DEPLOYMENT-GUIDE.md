# Client Deployment Guide

## Beauty Products Data Lake

**Version:** 1.0.0
**Last Updated:** January 26, 2026

---

## Overview

This guide provides step-by-step instructions for deploying the Beauty Products Data Lake to your AWS environment. The deployment uses Terraform for Infrastructure as Code (IaC) and follows AWS best practices for security, monitoring, and cost optimization.

**Estimated Deployment Time:** 30-45 minutes

---

## Prerequisites

### Required

1. **AWS Account**

   - Administrative access or permissions to create:
     - S3 buckets
     - IAM roles and policies
     - AWS Glue jobs, databases, and crawlers
     - EventBridge rules
     - CloudWatch dashboards and alarms
     - SNS topics
     - Athena workgroups
2. **Terraform**

   - Version 1.0 or higher
   - Installation: https://www.terraform.io/downloads
3. **AWS CLI**

   - Version 2.x recommended
   - Configured with credentials: `aws configure`
   - Installation: https://aws.amazon.com/cli/
4. **Git**

   - To clone the repository

### Optional (Recommended)

- **S3 Bucket for Terraform State**: Remote state management
- **AWS CloudShell**: Alternative to local CLI setup

---

## Pre-Deployment Checklist

Before starting deployment, ensure:

- [ ] AWS account has sufficient service quotas
- [ ] Terraform is installed and accessible
- [ ] AWS CLI is configured with appropriate credentials
- [ ] You have decided on environment name (dev, staging, prod, poc)
- [ ] Alert email address is available for CloudWatch notifications
- [ ] AWS region is selected (default: us-east-1)

---

## Step 1: Clone Repository

```bash
git clone https://github.com/cradaca39revstar/very-great-llms-trends
cd very-great-llms-trends
```

---

## Step 2: Configure Terraform Variables

1. Navigate to the terraform directory:

   ```bash
   cd terraform
   ```
2. Create `terraform.tfvars` file:

   ```bash
   # Copy example if available, or create new file
   # terraform.tfvars
   ```
3. Configure variables in `terraform.tfvars`:

   ```hcl
   # Environment Configuration
   environment = "poc"  # Options: dev, staging, prod, poc
   aws_region  = "us-east-1"

   # Alert Configuration
   alert_email = "your-email@example.com"

   # Optional: Phone number for SMS alerts
   alert_phone_number = ""

   # Project Tagging
   project_name = "BeautyProductsDataLake"

   # Additional Tags (optional)
   tags = {
     Owner       = "Data Team"
     Project     = "Beauty Products"
     CostCenter  = "Analytics"
   }
   ```

**Important Variables:**

- `environment`: Used in resource naming (e.g., `very-great-products-raw-us-east-1-poc`)
- `alert_email`: Email address for CloudWatch alarm notifications
- `aws_region`: AWS region for all resources (must be consistent)

---

## Step 3: Review Terraform Configuration

1. Review the Terraform files to understand what will be created:

   - `s3-buckets.tf` - S3 buckets for raw, curated, and metadata zones
   - `iam.tf` - IAM roles and policies
   - `glue-catalog.tf` - Glue databases and tables
   - `glue-jobs.tf` - ETL job configuration
   - `glue-crawlers.tf` - Crawler configurations
   - `eventbridge.tf` - Scheduling rules
   - `cloudwatch.tf` - Monitoring and alarms
   - `sns.tf` - Notification topics
   - `athena-workgroup.tf` - Athena workgroup
2. Review `variables.tf` for all available configuration options

---

## Step 4: Initialize Terraform

```bash
cd terraform
terraform init
```

This will:

- Download required Terraform providers (AWS)
- Initialize the backend (local state by default)

**Optional: Configure Remote State**

If using S3 for Terraform state, create a backend configuration file or add to `provider.tf`:

```hcl
terraform {
  backend "s3" {
    bucket = "your-terraform-state-bucket"
    key    = "beauty-products-data-lake/terraform.tfstate"
    region = "us-east-1"
  }
}
```

Then run `terraform init` again.

---

## Step 5: Review Deployment Plan

```bash
terraform plan
```

This will show:

- Resources to be created (S3 buckets, IAM roles, Glue jobs, etc.)
- Estimated costs (if enabled)
- Configuration details

**Review carefully:**

- Resource names and tags
- IAM permissions
- S3 bucket configurations
- Alert email addresses

---

## Step 6: Deploy Infrastructure

```bash
terraform apply
```

Terraform will:

1. Show the execution plan
2. Prompt for confirmation: Type `yes` to proceed
3. Create all AWS resources
4. Display outputs (bucket names, job names, etc.)

**Expected Output:**

```
Apply complete! Resources: XX added, 0 changed, 0 destroyed.

Outputs:

raw_bucket_name = "very-great-products-raw-us-east-1-poc"
curated_bucket_name = "very-great-products-processed-us-east-1-poc"
metadata_bucket_name = "very-great-products-metadata-us-east-1-poc"
glue_job_name = "beauty-products-etl-job"
athena_workgroup_name = "beauty-products-athena-poc"
...
```

**Save these outputs** - you'll need them for subsequent steps.

---

## Step 7: Upload ETL Script to S3

The Glue job requires the ETL script to be in S3. Upload it:

```bash
# Get the curated bucket name from Terraform output
CURATED_BUCKET=$(terraform output -raw curated_bucket_name)

# Upload the ETL script
aws s3 cp ../scripts/beauty_products_etl.py \
  s3://${CURATED_BUCKET}/scripts/beauty_products_etl.py
```

**Alternative: Use PowerShell (Windows)**

```powershell
$curatedBucket = terraform output -raw curated_bucket_name
aws s3 cp ..\scripts\beauty_products_etl.py `
  s3://$curatedBucket/scripts/beauty_products_etl.py
```

**Verify Upload:**

```bash
aws s3 ls s3://${CURATED_BUCKET}/scripts/
```

---

## Step 8: Update Glue Job Script Location

If the Glue job script path wasn't set during Terraform deployment, update it:

1. Go to AWS Console → Glue → Jobs
2. Select `beauty-products-etl-job`
3. Edit the job
4. Under "Script path", set: `s3://${CURATED_BUCKET}/scripts/beauty_products_etl.py`
5. Save changes

**Note**: The Terraform configuration should handle this automatically, but verify if needed.

---

## Step 9: Create Athena Views

1. Open AWS Console → Athena
2. Select the workgroup: `beauty-products-athena-{environment}`
3. Set result location (if prompted): `s3://${METADATA_BUCKET}/athena-results/`
4. Open the SQL query editor
5. Copy and execute the views from `../athena-views.sql`

**Views to Create:**

- `vw_high_quality_products`
- `vw_sales_by_category_month`
- `vw_quality_trends`
- `vw_product_performance`
- `vw_shop_leaderboard`

**Verify Views:**

```sql
SHOW TABLES IN beauty_products_db;
```

---

## Step 10: Upload Sample Data (Optional)

To test the pipeline, upload sample data:

```bash
# Get the raw bucket name
RAW_BUCKET=$(terraform output -raw raw_bucket_name)

# Create date-based folder structure
DATE=$(date +%Y/%m/%d)  # Format: YYYY/MM/DD

# Upload sample CSV file
aws s3 cp ../tests/sample-data/valid_input.csv \
  s3://${RAW_BUCKET}/landing/beauty-products/${DATE}/beauty-products_$(date +%Y%m%d).csv
```

**Verify Upload:**

```bash
aws s3 ls s3://${RAW_BUCKET}/landing/beauty-products/${DATE}/
```

---

## Step 11: Run Initial Glue Job

Test the ETL pipeline:

```bash
# Get job name
JOB_NAME=$(terraform output -raw glue_job_name)

# Start job run
aws glue start-job-run --job-name ${JOB_NAME}
```

**Monitor Job:**

1. AWS Console → Glue → Jobs → `beauty-products-etl-job`
2. Click on the job run
3. View logs in CloudWatch Logs
4. Check execution status

**Expected Duration:** 5-8 minutes for sample data

---

## Step 12: Verify Deployment

### 12.1 Check S3 Buckets

```bash
# Verify curated data
aws s3 ls s3://${CURATED_BUCKET}/curated/beauty-products/ --recursive

# Verify quality reports
aws s3 ls s3://${CURATED_BUCKET}/quality-reports/beauty-products/ --recursive
```

### 12.2 Check Glue Catalog

1. AWS Console → Glue → Databases
2. Verify databases exist:
   - `beauty_products_db`
   - `beauty_products_metadata_db`
3. Check tables are created and updated

### 12.3 Test Athena Query

```sql
-- In Athena Query Editor
SELECT COUNT(*) as total_records
FROM beauty_products_db.curated_beauty_products
LIMIT 10;
```

### 12.4 Check CloudWatch Dashboard

1. AWS Console → CloudWatch → Dashboards
2. Open `beauty-products-pipeline-metrics`
3. Verify widgets are displaying data

### 12.5 Verify Alarms

1. AWS Console → CloudWatch → Alarms
2. Check alarm status:
   - `beauty-products-job-failure`
   - `beauty-products-low-quality`
   - `beauty-products-high-error-rate`
3. Verify SNS subscription (check email for confirmation)

---

## Step 13: Configure Monitoring Alerts

### Email Notifications

1. Check your email for SNS subscription confirmation
2. Click the confirmation link to activate notifications

### Optional: SMS Notifications

If you configured `alert_phone_number`:

1. AWS Console → SNS → Subscriptions
2. Verify phone number subscription
3. Confirm via SMS code

---

## Post-Deployment Tasks

### 1. Review Quality Reports

After first job run, check quality metrics:

```bash
# List quality reports
aws s3 ls s3://${CURATED_BUCKET}/quality-reports/beauty-products/ --recursive

# Download latest report
LATEST_REPORT=$(aws s3 ls s3://${CURATED_BUCKET}/quality-reports/beauty-products/ \
  --recursive | sort | tail -1 | awk '{print $NF}')

aws s3 cp s3://${CURATED_BUCKET}/${LATEST_REPORT} quality-report.json

# View report
cat quality-report.json | jq '.'
```

**Expected Metrics:**

- `pass_rate >= 0.95`
- `avg_quality_score >= 0.95`

### 2. Test Athena Views

```sql
-- Test high quality products view
SELECT * FROM beauty_products_db.vw_high_quality_products LIMIT 10;

-- Test sales by category
SELECT * FROM beauty_products_db.vw_sales_by_category_month 
WHERE year = 2024 
ORDER BY total_revenue_usd DESC 
LIMIT 10;
```

### 3. Review CloudWatch Metrics

1. Open CloudWatch Dashboard
2. Verify metrics are being collected
3. Check for any alarms in alarm state

### 4. Document Access Information

Save the following for your team:

- S3 bucket names
- Glue job name
- Athena workgroup name
- CloudWatch dashboard URL
- SNS topic ARN

---

## Troubleshooting

### Terraform Apply Fails

**Issue**: Resource creation fails

**Solutions**:

- Check AWS service quotas
- Verify IAM permissions
- Review error messages in Terraform output
- Check for existing resources with same names

### Glue Job Fails

**Issue**: Job execution fails

**Solutions**:

- Check CloudWatch Logs: `/aws-glue/jobs/beauty-products-etl-job`
- Verify script path in S3 is correct
- Check IAM role permissions
- Review job parameters

### No Data in Athena

**Issue**: Tables exist but queries return no data

**Solutions**:

- Run Glue crawlers manually
- Verify data exists in S3 curated bucket
- Check table partitions
- Verify Athena workgroup result location

### Alarms Not Triggering

**Issue**: Alarms configured but not sending notifications

**Solutions**:

- Verify SNS subscription is confirmed
- Check alarm thresholds
- Review CloudWatch metrics are being published
- Test alarm manually

---

## Rollback Procedure

If deployment needs to be rolled back:

```bash
cd terraform
terraform destroy
```

**Warning**: This will delete all resources created by Terraform, including:

- S3 buckets and all data
- Glue jobs, databases, and tables
- CloudWatch dashboards and alarms
- IAM roles and policies

**Before destroying:**

- Backup any important data
- Export Terraform state
- Document current configuration

---

## Next Steps

After successful deployment:

1. **Review** [Operations Guide](CLIENT-OPERATIONS-GUIDE.md) for daily operations
2. **Configure** backup and disaster recovery procedures
3. **Train** team members on system usage
4. **Schedule** regular quality reviews
5. **Monitor** costs and optimize as needed

---

## Support

For deployment issues:

1. Review [Troubleshooting](#troubleshooting) section
2. Check [Runbooks](../runbooks/) for specific scenarios
3. Review CloudWatch Logs for detailed error messages
4. Contact your system administrator

---

## Related Documentation

- [Architecture Overview](ARCHITECTURE.md) - System architecture details
- [Operations Guide](CLIENT-OPERATIONS-GUIDE.md) - Daily operations
- [Deployment Checklist](../deployment-checklist.md) - Detailed checklist
- [README](../README.md) - Project overview
