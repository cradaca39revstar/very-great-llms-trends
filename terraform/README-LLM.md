# LLM Trending Products System - Terraform Deployment Guide

**Version:** 1.0.0  
**Last Updated:** January 26, 2026

---

## Overview

This guide provides step-by-step instructions for deploying the LLM Trending Products Report Generator infrastructure using Terraform. The system includes API Gateway, Cognito authentication, Lambda orchestrator, DynamoDB logging, S3 PDF storage, and AWS Bedrock integration.

---

## Prerequisites

### Required

1. **AWS Account** with appropriate permissions:
   - IAM role creation
   - Lambda function deployment
   - API Gateway configuration
   - Cognito User Pool management
   - Bedrock model access
   - S3 bucket creation
   - DynamoDB table creation

2. **Terraform** version >= 1.0
   ```bash
   terraform --version
   ```

3. **AWS CLI** configured with credentials
   ```bash
   aws configure
   aws sts get-caller-identity
   ```

4. **Existing Data Lake** infrastructure deployed
   - S3 curated bucket: `very-great-products-processed-us-east-1-{environment}`
   - Glue database: `beauty_products_db`
   - Athena workgroup: `beauty-products-athena-{environment}`

### Optional

- Python 3.10+ for local testing
- Git for version control
- PowerShell or Bash for deployment scripts

---

## Bedrock Model Access Setup

**UPDATE (January 2026)**: The "Model access" page has been retired. Models are now automatically enabled.

### Automatic Model Activation

**Good News**: Serverless foundation models are now **automatically enabled** when first invoked in your account. You no longer need to manually activate model access.

### First-Time Access for Anthropic Models

**Important**: For **Anthropic models** (including Claude 3.7 Sonnet, our primary model), first-time users may need to submit use case details before accessing the model.

**How to Enable Anthropic Models**:

1. **Option 1: Via Bedrock Playground (Recommended)**
   - Navigate to: https://console.aws.amazon.com/bedrock/
   - Click "Playground" in left navigation
   - Select "Text" or "Chat" playground
   - Choose "Claude 3.7 Sonnet" from model dropdown
   - If prompted, fill out the use case form:
     - Use case: "Business Intelligence / Analytics"
     - Description: "Generating trending product reports with AI-enhanced insights"
   - Submit and wait for approval (usually instant to a few minutes)

2. **Option 2: Via API (Automatic)**
   - When Lambda first invokes the model, if access is needed, you'll see an error
   - Check CloudWatch logs for specific instructions
   - Complete the use case form in Bedrock Console if prompted

### Verify Model Access

After enabling (or to check if already enabled):

```bash
# List available models
aws bedrock list-foundation-models --region us-east-1 --query "modelSummaries[?contains(modelId, 'claude-3-7') || contains(modelId, 'nova-pro') || contains(modelId, 'command-r-plus')]"

# Test model invocation (will auto-enable if needed)
aws bedrock-runtime invoke-model \
  --model-id anthropic.claude-3-7-sonnet-20240229-v1:0 \
  --body '{"anthropic_version":"bedrock-2023-05-31","max_tokens":10,"messages":[{"role":"user","content":"test"}]}' \
  --region us-east-1 \
  response.json
```

**Note**: Model availability varies by AWS region. Use `us-east-1` for maximum model selection.

### Access Control

Account administrators can control model access via:
- **IAM Policies**: Restrict which users/roles can invoke specific models
- **Service Control Policies (SCPs)**: Organization-level restrictions

See AWS documentation for details on access control.

---

## Configuration

### Step 1: Configure Variables

Create or update `terraform.tfvars`:

```hcl
# Basic configuration
environment = "poc"  # or "dev", "staging", "prod"
aws_region  = "us-east-1"
alert_email = "your-email@example.com"

# LLM system configuration
enable_llm_system     = true
cognito_domain_prefix = "beauty-products-trending-poc"  # Must be unique across AWS
lambda_memory_size    = 1024  # MB
lambda_timeout        = 60    # seconds
pdf_expiration_days   = 7     # days

# Bedrock models
bedrock_primary_model   = "anthropic.claude-3-7-sonnet-20240229-v1:0"
bedrock_fallback_model  = "amazon.nova-pro-v1:0"
```

**Important**:
- `cognito_domain_prefix` must be globally unique across all AWS accounts
- If you get "domain already exists" error, try a different prefix (e.g., add company name)

### Step 2: Validate Configuration

```bash
cd terraform/
terraform validate
```

---

## Deployment Steps

### Step 1: Initialize Terraform

```bash
cd terraform/
terraform init
```

**Expected output**: Provider plugins downloaded, backend initialized

### Step 2: Review Infrastructure Plan

```bash
terraform plan
```

**Review**:
- Check that `enable_llm_system = true` creates LLM resources
- Verify no changes to existing data lake infrastructure
- Confirm resource counts:
  - 7 new Terraform files
  - ~25-30 new AWS resources
  - Estimated cost: $50-150/month

### Step 3: Deploy Infrastructure

```bash
terraform apply
```

**Confirmation**: Type `yes` when prompted

**Deployment time**: 3-5 minutes

**Resources created**:
- Cognito User Pool and Client
- API Gateway REST API
- Lambda function (placeholder code)
- DynamoDB table
- S3 PDF bucket
- CloudWatch dashboard and alarms
- IAM roles and policies

### Step 4: Capture Outputs

```bash
terraform output
```

**Important outputs**:
```bash
api_gateway_url       = "https://xxxxxx.execute-api.us-east-1.amazonaws.com/poc/trending-products/query"
cognito_user_pool_id  = "us-east-1_xxxxxxxxx"
cognito_client_id     = "xxxxxxxxxxxxxxxxxxxxxxxxxx"
pdf_bucket_name       = "beauty-products-pdfs-us-east-1-poc"
lambda_function_name  = "beauty-products-llm-orchestrator-poc"
```

**Save these values** - you'll need them for chatbot configuration.

---

## Deploy Lambda Code

### Step 1: Create Lambda Placeholder (First Time Only)

**Before first terraform apply**, create the placeholder zip file:

**Option A: PowerShell (Windows)**
```powershell
cd terraform
.\create-lambda-placeholder.ps1
```

**Option B: Bash (Linux/Mac)**
```bash
cd terraform
chmod +x create-lambda-placeholder.sh
./create-lambda-placeholder.sh
```

**Option C: Manual**
Create a simple `lambda_placeholder.py` with `def lambda_handler(event, context): return {"statusCode": 200}` and zip it.

### Step 2: Package and Deploy Lambda Code

**Recommended: Use deployment script**

**Option A: PowerShell (Windows)**
```powershell
cd scripts
.\deploy-lambda-llm.ps1
```

**Option B: Bash (Linux/Mac)**
```bash
cd scripts
chmod +x deploy-lambda-llm.sh
./deploy-lambda-llm.sh
```

**Manual deployment** (if scripts don't work):

**PowerShell:**
```powershell
cd ..\lambda
# Install dependencies
pip install -r requirements.txt -t .
# Create zip
Compress-Archive -Path * -DestinationPath function.zip -Force -Exclude "*.pyc","__pycache__","*.git*","*.md","tests"
```

**Bash:**
```bash
cd ../lambda
# Install dependencies
pip install -r requirements.txt -t .
# Create zip
zip -r function.zip . -x "*.pyc" -x "__pycache__/*" -x "*.git/*" -x "*.md" -x "tests/*"
```

### Step 3: Deploy to Lambda (if using manual method)

```bash
# Get function name from Terraform output
$FUNCTION_NAME = terraform output -raw lambda_function_name

# Update function code
aws lambda update-function-code \
  --function-name $FUNCTION_NAME \
  --zip-file fileb://function.zip

# Wait for update to complete
aws lambda wait function-updated \
  --function-name $FUNCTION_NAME
```

### Step 4: Verify Deployment

```bash
aws lambda get-function --function-name $FUNCTION_NAME
```

**Check**:
- `State: Active`
- `LastUpdateStatus: Successful`
- `Runtime: python3.10`

---

## Testing

### Step 1: Create Test User

```bash
# Get Cognito User Pool ID
$USER_POOL_ID = terraform output -raw cognito_user_pool_id

# Create test user
aws cognito-idp admin-create-user \
  --user-pool-id $USER_POOL_ID \
  --username testuser@example.com \
  --user-attributes Name=email,Value=testuser@example.com \
  --temporary-password "TempPass123!" \
  --message-action SUPPRESS
```

### Step 2: Set Permanent Password

```bash
aws cognito-idp admin-set-user-password \
  --user-pool-id $USER_POOL_ID \
  --username testuser@example.com \
  --password "YourSecurePassword123!" \
  --permanent
```

### Step 3: Get Authentication Token

```bash
# Get client ID
$CLIENT_ID = terraform output -raw cognito_client_id

# Authenticate
aws cognito-idp initiate-auth \
  --auth-flow USER_PASSWORD_AUTH \
  --client-id $CLIENT_ID \
  --auth-parameters USERNAME=testuser@example.com,PASSWORD=YourSecurePassword123!
```

**Save the `IdToken` from the response.**

### Step 4: Test API Gateway Endpoint

```bash
# Get API URL
$API_URL = terraform output -raw api_gateway_url

# Test request
curl -X POST $API_URL \
  -H "Authorization: Bearer YOUR_ID_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the trending products in Skincare?"}'
```

**Expected response**: JSON with report and PDF URL (in ~20-25 seconds)

### Step 5: Run Integration Tests

```bash
cd ../tests

# Set environment for testing
export RUN_INTEGRATION_TESTS=1
export AWS_REGION=us-east-1

# Run tests
python test_llm_integration.py
```

**Expected**: All tests pass

---

## Troubleshooting

### Issue: Terraform Apply Fails

**Error**: `Error creating Cognito User Pool Domain: InvalidParameterException: Domain already exists`

**Solution**: Change `cognito_domain_prefix` in `terraform.tfvars` to a unique value.

---

**Error**: `Error: error creating Lambda Function: InvalidParameterValueException: The role defined for the function cannot be assumed by Lambda`

**Solution**: Wait 10-15 seconds for IAM role to propagate, then run `terraform apply` again.

---

**Error**: `AccessDeniedException: User is not authorized to perform: bedrock:InvokeModel`

**Solution**: 
1. For Anthropic models: Complete use case form in Bedrock Playground (see "Bedrock Model Access Setup" above)
2. Verify IAM role has Bedrock permissions (`bedrock:InvokeModel` action)
3. Check model IDs are correct in variables
4. Verify model is available in your region: `aws bedrock list-foundation-models --region us-east-1`
5. Models auto-enable on first invocation, but Anthropic models may require use case approval first

---

### Issue: Lambda Function Errors

**Error**: `Module not found: fpdf2`

**Solution**: Lambda dependencies not installed. Redeploy with proper packaging:
```bash
cd ../lambda
pip install -r requirements.txt -t .
zip -r function.zip .
aws lambda update-function-code --function-name $FUNCTION_NAME --zip-file fileb://function.zip
```

---

**Error**: `ClientError: An error occurred (ResourceNotFoundException) when calling the GetTable operation`

**Solution**: Athena table not found. Verify data lake is deployed:
```bash
aws glue get-table --database-name beauty_products_db --name curated_beauty_products
```

---

**Error**: `Query timeout after 30 seconds`

**Solution**: Athena query taking too long. Check:
1. Data volume (is it too large?)
2. Partitioning (are year/month partitions working?)
3. Increase timeout in Lambda configuration

---

### Issue: No Products Returned

**Error**: `No trending products found in category 'Skincare'`

**Possible causes**:
1. No data in data lake for last 30 days
2. All products filtered out by quality score (< 0.95)
3. Category name mismatch

**Investigation**:
```sql
-- Check data availability in Athena
SELECT COUNT(*) as product_count, l2_category
FROM beauty_products_db.curated_beauty_products
WHERE data_quality_score >= 0.95
  AND year = 2026
  AND month_num >= 1
GROUP BY l2_category;
```

---

### Issue: High Latency (> 30 seconds)

**Symptoms**: Reports taking longer than target 20-25 seconds

**Investigation**:
1. Check CloudWatch metrics to identify slow component
2. Review Lambda logs for timing breakdown

**Solutions**:
- Increase Lambda memory (improves CPU allocation)
- Enable provisioned concurrency (eliminates cold starts)
- Check Bedrock throttling (may need quota increase)

---

### Issue: Bedrock Throttling

**Error**: `ThrottlingException: Rate exceeded`

**Solution**: Request quota increase:
```
AWS Console → Service Quotas → AWS Bedrock
Request increase for:
- Requests per minute for model
- Tokens per minute
```

**Temporary workaround**: System automatically retries with fallback model (Nova)

---

## Monitoring

### CloudWatch Dashboard

**Access**:
```bash
$DASHBOARD_URL = terraform output -raw cloudwatch_llm_dashboard_url
# Open in browser
```

**Metrics to monitor**:
- Request volume (should be > 0 if users are active)
- Average latency (should be < 25 seconds)
- Error rate (should be < 2%)
- Concurrent executions (should be < 80)

### CloudWatch Logs

**View Lambda logs**:
```bash
aws logs tail /aws/lambda/beauty-products-llm-orchestrator-poc --follow
```

**Search for errors**:
```bash
aws logs filter-log-events \
  --log-group-name /aws/lambda/beauty-products-llm-orchestrator-poc \
  --filter-pattern "ERROR"
```

### DynamoDB Audit Logs

**Query recent requests**:
```bash
aws dynamodb scan \
  --table-name beauty-products-prompt-logs-poc \
  --limit 10 \
  --scan-index-forward false
```

---

## Cost Estimation

### Monthly Cost Breakdown (Approximate)

**Low Usage** (100 queries/month):
- API Gateway: $0.50
- Lambda: $5-10
- Bedrock (Claude 3.7): $15-25
- DynamoDB: $2
- S3 PDFs: $1
- **Total**: ~$25-40/month

**Medium Usage** (1,000 queries/month):
- API Gateway: $5
- Lambda: $30-50
- Bedrock (Claude 3.7): $150-250
- DynamoDB: $10
- S3 PDFs: $5
- **Total**: ~$200-320/month

**High Usage** (10,000 queries/month):
- API Gateway: $35
- Lambda: $200-300
- Bedrock (Claude 3.7): $1,500-2,500
- DynamoDB: $75
- S3 PDFs: $25
- **Total**: ~$1,800-3,000/month

**Cost Optimization Tips**:
- Use Amazon Nova instead of Claude for simpler tasks (50% cheaper)
- Enable query result caching (reduces Athena costs)
- Configure shorter PDF retention (reduces S3 costs)
- Use reserved capacity for high usage (reduces Lambda costs)

---

## Updating Infrastructure

### Modify Configuration

1. Update `terraform.tfvars`
2. Run `terraform plan` to review changes
3. Run `terraform apply` to deploy

### Update Lambda Code

```bash
cd ../lambda
# Make code changes
zip -r function.zip .
aws lambda update-function-code \
  --function-name $(terraform output -raw lambda_function_name) \
  --zip-file fileb://function.zip
```

### Rollback Changes

```bash
# Rollback Terraform
terraform plan -out=current.tfplan
terraform apply current.tfplan

# Rollback Lambda code
aws lambda publish-version --function-name $FUNCTION_NAME
aws lambda update-alias --function-name $FUNCTION_NAME --name PROD --function-version $VERSION
```

---

## Decommissioning

### Step 1: Disable System

```hcl
# In terraform.tfvars
enable_llm_system = false
```

```bash
terraform apply
```

### Step 2: Clean Up Data

```bash
# Empty PDF bucket
aws s3 rm s3://$(terraform output -raw pdf_bucket_name) --recursive

# Optional: Delete DynamoDB logs
aws dynamodb delete-table --table-name beauty-products-prompt-logs-poc
```

### Step 3: Destroy Infrastructure

```bash
terraform destroy
```

**Note**: This does NOT affect existing data lake infrastructure.

---

## Security Best Practices

### Production Checklist

- [ ] Enable MFA for Cognito User Pool
- [ ] Configure custom domain for API Gateway
- [ ] Enable WAF on API Gateway
- [ ] Use AWS Secrets Manager for sensitive config
- [ ] Enable CloudTrail logging
- [ ] Configure VPC for Lambda (optional)
- [ ] Set up GuardDuty for threat detection
- [ ] Regular security audits of IAM policies

### Least Privilege Verification

**Verify Lambda has READ-ONLY access**:
```bash
# Lambda should NOT have these permissions on existing buckets:
# - s3:PutObject (on curated bucket)
# - s3:DeleteObject (on any data lake bucket)
# - glue:UpdateDatabase
# - glue:DeleteTable
```

---

## Advanced Configuration

### Enable Provisioned Concurrency

For production with consistent traffic:

```hcl
# In lambda-llm.tf
resource "aws_lambda_provisioned_concurrency_config" "orchestrator" {
  function_name                     = aws_lambda_function.orchestrator[0].function_name
  provisioned_concurrent_executions = 2
  qualifier                         = aws_lambda_alias.live[0].name
}
```

**Cost**: ~$10-20/month per instance  
**Benefit**: Eliminates cold start latency (2-3 seconds)

### Custom Domain for API

```hcl
# In api-gateway-llm.tf
resource "aws_api_gateway_domain_name" "llm" {
  domain_name              = "trending-api.example.com"
  regional_certificate_arn = var.acm_certificate_arn
  
  endpoint_configuration {
    types = ["REGIONAL"]
  }
}
```

**Requires**: ACM certificate for domain

---

## Support

### Common Commands

**Check Lambda logs**:
```bash
aws logs tail /aws/lambda/beauty-products-llm-orchestrator-poc --follow
```

**Test Lambda directly**:
```bash
aws lambda invoke \
  --function-name beauty-products-llm-orchestrator-poc \
  --payload '{"body": "{\"query\": \"Trending Skincare\"}"}' \
  response.json
```

**Check DynamoDB logs**:
```bash
aws dynamodb query \
  --table-name beauty-products-prompt-logs-poc \
  --index-name user_id-index \
  --key-condition-expression "user_id = :uid" \
  --expression-attribute-values '{":uid":{"S":"test-user-123"}}'
```

### Getting Help

**Documentation**:
- Architecture: [`docs/LLM-TRENDING-PRODUCTS-ARCHITECTURE.md`](../docs/LLM-TRENDING-PRODUCTS-ARCHITECTURE.md)
- User Guide: See architecture doc section "User Guide"
- Operations: [`docs/CLIENT-OPERATIONS-GUIDE.md`](../docs/CLIENT-OPERATIONS-GUIDE.md)

**Support**:
- Technical issues: tech-support@example.com
- Infrastructure questions: devops@example.com

---

## Next Steps

After successful deployment:

1. **Create test users** in Cognito
2. **Test end-to-end** with sample queries
3. **Monitor performance** via CloudWatch dashboard
4. **Review costs** in AWS Cost Explorer
5. **Configure chatbot UI** with API endpoint and Cognito credentials
6. **Train users** on system usage

---

**Deployment checklist complete?** See [`deployment-checklist.md`](../deployment-checklist.md) for comprehensive validation steps.
