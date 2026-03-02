# Client Deployment Guide
## Beauty Products Data Lake + LLM Product Innovation Engine

**Version:** 2.0.0  
**Last Updated:** February 26, 2026

---

## Overview

This guide covers end-to-end deployment of the full system: Data Lake (V1) + LLM Product Innovation Engine (V2). Follow the sections in order for a fresh deployment.

**Estimated total time:** 45–90 minutes (plus AWS propagation delays)

---

## Prerequisites

### Tools Required

| Tool | Version | Verify |
|------|---------|--------|
| AWS CLI | >= 2.x | `aws --version` |
| Terraform | >= 1.0 | `terraform --version` |
| Python | >= 3.10 | `python --version` |
| Node.js | >= 18 | `node --version` |
| PowerShell | >= 5.1 (Windows) | `$PSVersionTable.PSVersion` |

### AWS Permissions Required

Your AWS IAM user or role must have permissions for:
- S3, Glue, Athena, EventBridge, CloudWatch, SNS
- Lambda, API Gateway, Cognito, DynamoDB
- Bedrock (InvokeModel), IAM (role/policy management)
- Lake Formation, Amplify

### Bedrock Model Access (Required Before Deployment)

Enable the following models in the AWS Console before running Terraform:

**In `us-east-1`:**
- **Amazon Nova Pro** (`amazon.nova-pro-v1:0`) — auto-enabled on first invocation

**In `us-west-2`:** (for AI product images)
1. Go to **AWS Console** → **Amazon Bedrock** → change region to **US West (Oregon)**
2. Click **Model access** → **Manage model access**
3. Enable:
   - **Stability AI SD3.5 Large** (`stability.sd3-5-large-v1:0`)
   - **Stability AI SD3 Large** (`stability.sd3-large-v1:0`) — fallback model
4. Wait for **Access granted** status (~1–2 minutes)

> If these models are not enabled, product concept images will fail silently and the report will be generated without images.

---

## Part 1 — Infrastructure Deployment (Terraform)

### Step 1: Configure Variables

Copy the example configuration and fill in your values:

```powershell
cd terraform
copy terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars`:

```hcl
environment           = "poc"          # or "dev", "staging", "prod"
aws_region            = "us-east-1"
alert_email           = "your-team@example.com"
project_name          = "BeautyProductsDataLake"

# LLM System
enable_llm_system     = true
cognito_domain_prefix = "beauty-products-trending-poc"   # Must be globally unique
lambda_memory_size    = 1024
lambda_timeout        = 60
pdf_expiration_days   = 7

# Bedrock models
bedrock_primary_model  = "amazon.nova-pro-v1:0"
bedrock_fallback_model = "amazon.nova-pro-v1:0"

# Brave Search (optional — for web market insights)
brave_search_api_key   = "YOUR_KEY_HERE"   # Leave empty "" to disable
enable_scraper_lambda  = false             # Set true only if Scraper Lambda is deployed
```

**Important:** `cognito_domain_prefix` must be globally unique across all AWS accounts. If you get a "domain already exists" error, add your company name (e.g. `beauty-products-trending-acme-poc`).

### Step 2: Create Lambda Placeholder (First Time Only)

Before the first `terraform apply`, a placeholder Lambda zip must exist:

```powershell
cd terraform
.\create-lambda-placeholder.ps1
```

### Step 3: Initialize and Deploy Terraform

```powershell
cd terraform

# Initialize providers
terraform init

# Review what will be created (~50+ AWS resources)
terraform plan

# Deploy (type 'yes' when prompted)
terraform apply
```

**Deployment time:** 3–8 minutes.

### Step 4: Save Terraform Outputs

```powershell
terraform output
```

Save all output values — you will need them for Lambda deployment and frontend configuration:

```
api_gateway_url           = "https://xxxxxx.execute-api.us-east-1.amazonaws.com/poc/trending-products/query"
cognito_user_pool_id      = "us-east-1_xxxxxxxxx"
cognito_client_id         = "xxxxxxxxxxxxxxxxxxxxxxxxxx"
pdf_bucket_name           = "beauty-products-pdfs-us-east-1-poc"
lambda_function_name      = "beauty-products-llm-orchestrator-poc"
athena_workgroup_name     = "beauty-products-athena-poc"
cloudwatch_llm_dashboard_url = "https://console.aws.amazon.com/cloudwatch/..."
```

---

## Part 2 — Lambda Code Deployment

### Step 5: Deploy Lambda Orchestrator

From the project root:

```powershell
.\scripts\deploy-lambda-llm.ps1
```

The script will:
1. Install Python dependencies from `lambda/requirements.txt` into the Lambda package
2. Create `lambda/function.zip`
3. Upload to the Lambda function created by Terraform
4. Wait for the update to complete

**Expected output:** `Lambda function updated successfully.`

**Manual deployment** (if script fails):

```powershell
cd lambda
pip install -r requirements.txt -t .
Compress-Archive -Path * -DestinationPath function.zip -Force -Exclude "*.pyc","__pycache__","tests"
$FUNCTION = terraform -chdir=..\terraform output -raw lambda_function_name
aws lambda update-function-code --function-name $FUNCTION --zip-file fileb://function.zip
aws lambda wait function-updated --function-name $FUNCTION
```

### Step 6: Verify Lambda Deployment

```powershell
$FUNCTION = (cd terraform; terraform output -raw lambda_function_name)
aws lambda get-function --function-name $FUNCTION --query "Configuration.[State,LastUpdateStatus,Runtime]"
```

Expected: `["Active", "Successful", "python3.10"]`

---

## Part 3 — ETL Data Pipeline Setup

### Step 7: Upload Test or Production Data

Upload a CSV file to the S3 raw zone. The path must follow the date partition format:

```powershell
# Replace {environment} with your environment value (e.g. poc, dev)
$ENV = "poc"
$DATE = (Get-Date).ToString("yyyy/MM/dd")
aws s3 cp tests/sample-data/valid_input.csv `
  "s3://very-great-products-raw-us-east-1-$ENV/landing/beauty-products/$DATE/"
```

**CSV format required** (11 columns):
```
Month, Product Id, Product Name, Shop Name, L1 category, L2 category, L3 category, Item Sold, Revenue, Avg. Unit Price, MoM Growth %
```

### Step 8: Run the ETL Job

```powershell
aws glue start-job-run --job-name beauty-products-etl-job
```

**Monitor progress** (wait ~5–8 minutes):

```powershell
aws glue get-job-run --job-name beauty-products-etl-job --run-id <RunId> --query "JobRun.JobRunState"
```

Or watch logs:

```powershell
aws logs tail /aws-glue/jobs/beauty-products-etl-job --follow
```

### Step 9: Verify Data in Athena

In the **Athena Query Editor** (workgroup: `beauty-products-athena-{environment}`):

```sql
SELECT COUNT(*) as total_records,
       AVG(data_quality_score) as avg_quality
FROM beauty_products_db.curated_beauty_products;
```

Expected: record count > 0, avg quality > 0.90

Verify L2 categories available for LLM queries:

```sql
SELECT DISTINCT l2_category, COUNT(*) as products
FROM beauty_products_db.curated_beauty_products
WHERE data_quality_score >= 0.95
GROUP BY l2_category
ORDER BY products DESC;
```

---

## Part 4 — Cognito User Setup

### Step 10: Create Test/Admin User

```powershell
cd terraform
$USER_POOL_ID = terraform output -raw cognito_user_pool_id

# Create user
aws cognito-idp admin-create-user `
  --user-pool-id $USER_POOL_ID `
  --username verygreat@test.com `
  --user-attributes Name=email,Value=verygreat@test.com `
  --temporary-password "VeryGreat123!" `
  --message-action SUPPRESS

# Set permanent password
aws cognito-idp admin-set-user-password `
  --user-pool-id $USER_POOL_ID `
  --username verygreat@test.com `
  --password "VeryGreat123!" `
  --permanent
```

---

## Part 5 — End-to-End Test

### Step 11: Test the API

From the project root:

```powershell
.\scripts\call-api-llm.ps1
```

Expected response (abbreviated):
```json
{
  "status": "processing",
  "request_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "message": "Report is being generated. Poll GET /report/{request_id} for status."
}
```

Then poll for the result:
```json
{
  "status": "success",
  "request_id": "...",
  "brand_name": "...",
  "category": "Skincare",
  "product_count": 5,
  "pdf_url": "https://...",
  "execution_time_ms": 22000
}
```

**Typical execution time:** 15–25 seconds.

### Step 12: Test the Frontend

1. Open https://amplify-versio.d32yhcl4pif1yr.amplifyapp.com/
2. Sign in with the test account
3. Select a category and click **Get Report**
4. Verify the report loads with brand proposal, 5 product ideas, and AI images
5. Click **Download PDF** and verify the PDF opens

---

## Part 6 — Frontend (Amplify) Configuration

The frontend is already deployed on Amplify. If you need to redeploy or reconfigure:

### Amplify Environment Variables

Set these in **AWS Amplify Console** → your app → **Environment variables**:

| Variable | Source |
|----------|--------|
| `VITE_API_URL` | `terraform output -raw api_gateway_url` |
| `VITE_COGNITO_USER_POOL_ID` | `terraform output -raw cognito_user_pool_id` |
| `VITE_COGNITO_CLIENT_ID` | `terraform output -raw cognito_client_id` |
| `VITE_AWS_REGION` | `us-east-1` |

### Trigger Amplify Rebuild

After updating environment variables, trigger a new build from the Amplify Console or by pushing a commit to the connected branch.

---

## Deployment Checklist

```
INFRASTRUCTURE
  [ ] Terraform initialized and applied successfully
  [ ] All terraform outputs captured and saved
  [ ] No resources failed during apply

LAMBDA
  [ ] deploy-lambda-llm.ps1 completed successfully
  [ ] Lambda state: Active, LastUpdateStatus: Successful

DATA PIPELINE
  [ ] CSV data uploaded to S3 raw zone
  [ ] Glue ETL job completed (state: SUCCEEDED)
  [ ] Athena query returns records with expected categories

COGNITO
  [ ] Test user created with permanent password
  [ ] Login tested via API or frontend

END-TO-END
  [ ] call-api-llm.ps1 returns success with report
  [ ] Frontend loads and generates a report
  [ ] PDF download works
  [ ] CloudWatch dashboard shows metrics

FRONTEND (AMPLIFY)
  [ ] Amplify environment variables set correctly
  [ ] Frontend URL confirmed working
```

---

## Troubleshooting

### Terraform: "Domain already exists"

```
Error: InvalidParameterException: Domain already exists
```

Change `cognito_domain_prefix` in `terraform.tfvars` to a unique value and re-run `terraform apply`.

---

### Terraform: Lambda role IAM propagation

```
Error: The role defined for the function cannot be assumed by Lambda
```

Wait 15 seconds and re-run `terraform apply`.

---

### Lambda: Module not found

```
Error: Module not found: fpdf2 (or Pillow, boto3)
```

Re-run the Lambda deployment script. Dependencies were not packaged correctly.

```powershell
cd lambda
Remove-Item -Recurse -Force * -Exclude "*.py","utils","requirements*.txt"
pip install -r requirements.txt -t .
.\scripts\deploy-lambda-llm.ps1
```

---

### No products returned for a category

```
"Category not found in last 30 days"
```

The Athena table has no records for that category in the last 30 days. Verify data was uploaded and the ETL job completed:

```sql
SELECT DISTINCT l2_category, MAX(month) as latest_month
FROM beauty_products_db.curated_beauty_products
WHERE data_quality_score >= 0.95
GROUP BY l2_category;
```

---

### Bedrock: AccessDeniedException for images

```
AccessDeniedException: aws-marketplace:ViewSubscriptions
```

Enable Stability AI models in `us-west-2` (see Prerequisites → Bedrock Model Access).

---

### High latency (> 30 seconds)

1. Check CloudWatch metrics for the slow step (Athena, Bedrock, image generation, PDF)
2. Increase Lambda memory to 2048 MB in `terraform.tfvars` and re-apply
3. Check for Bedrock throttling: request quota increase in Service Quotas

---

## Related Documentation

- [Operations Guide](CLIENT-OPERATIONS-GUIDE.md) — Daily operations after deployment
- [Frontend Access](AMPLIFY-CLIENT-LINK.md) — User management and frontend usage
- [LLM Architecture](LLM-TRENDING-PRODUCTS-ARCHITECTURE.md) — Detailed technical reference
- [LLM Terraform Guide](../terraform/README-LLM.md) — Infrastructure details
- [Runbooks](../runbooks/) — Specific troubleshooting procedures
