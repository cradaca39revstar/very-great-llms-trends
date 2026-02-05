#!/bin/bash
# Bash script to package and deploy Lambda code for LLM Trending Products
# Usage: ./deploy-lambda-llm.sh [environment] [function-name]

set -e

ENVIRONMENT="${1:-poc}"
FUNCTION_NAME="${2:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAMBDA_DIR="${SCRIPT_DIR}/../lambda"
TERRAFORM_DIR="${SCRIPT_DIR}/../terraform"

echo "=== LLM Lambda Deployment Script ==="

# Get function name from Terraform if not provided
if [ -z "$FUNCTION_NAME" ]; then
    echo "Getting function name from Terraform..."
    cd "$TERRAFORM_DIR"
    FUNCTION_NAME=$(terraform output -raw lambda_function_name 2>/dev/null || echo "")
    
    if [ -z "$FUNCTION_NAME" ]; then
        echo "Error: Could not get function name from Terraform."
        echo "Please deploy infrastructure first or provide function name as second argument."
        exit 1
    fi
    
    echo "Found function: $FUNCTION_NAME"
    cd - > /dev/null
fi

# Navigate to lambda directory
if [ ! -d "$LAMBDA_DIR" ]; then
    echo "Error: Lambda directory not found at $LAMBDA_DIR"
    exit 1
fi

cd "$LAMBDA_DIR"

echo ""
echo "Step 1: Installing dependencies..."

# Check if Python is available
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo "Warning: Python not found. Skipping dependency installation."
    echo "Make sure dependencies are installed in lambda/ directory before packaging."
else
    PYTHON_CMD=$(command -v python3 || command -v python)
    REQ_FILE="requirements-lambda.txt"
    if [ ! -f "$REQ_FILE" ]; then
        REQ_FILE="requirements.txt"
    fi
    echo "Installing packages from $REQ_FILE (for Amazon Linux 2 / Lambda)..."
    # Must use --platform manylinux2014_x86_64 so Pillow/fpdf2 get Linux binaries.
    # Otherwise PIL fails to load on Lambda and pdf.image() raises 'NoneType' has no attribute 'Image'.
    $PYTHON_CMD -m pip install -r "$REQ_FILE" -t . \
        --platform manylinux2014_x86_64 \
        --implementation cp \
        --python-version 3.10 \
        --only-binary=:all: \
        --upgrade \
        --quiet
    echo "Dependencies installed successfully (Linux-compatible)"
fi

echo ""
echo "Step 2: Creating deployment package..."

ZIP_FILE="function.zip"
if [ -f "$ZIP_FILE" ]; then
    rm "$ZIP_FILE"
    echo "Removed existing $ZIP_FILE"
fi

# Create zip excluding unnecessary files
zip -r "$ZIP_FILE" . \
    -x "*.pyc" \
    -x "__pycache__/*" \
    -x "*.git/*" \
    -x "*.zip" \
    -x "*.md" \
    -x ".pytest_cache/*" \
    -x "tests/*" \
    -x "test_*" \
    > /dev/null

ZIP_SIZE=$(du -h "$ZIP_FILE" | cut -f1)
echo "Created $ZIP_FILE ($ZIP_SIZE)"

echo ""
echo "Step 3: Deploying to Lambda..."
echo "Function: $FUNCTION_NAME"

# Deploy to Lambda
aws lambda update-function-code \
    --function-name "$FUNCTION_NAME" \
    --zip-file "fileb://$ZIP_FILE" \
    --region us-east-1

echo "Waiting for function update to complete..."
aws lambda wait function-updated \
    --function-name "$FUNCTION_NAME" \
    --region us-east-1

echo ""
echo "Step 4: Verifying deployment..."

FUNCTION_INFO=$(aws lambda get-function \
    --function-name "$FUNCTION_NAME" \
    --region us-east-1)

STATE=$(echo "$FUNCTION_INFO" | jq -r '.Configuration.State')
LAST_UPDATE_STATUS=$(echo "$FUNCTION_INFO" | jq -r '.Configuration.LastUpdateStatus')
RUNTIME=$(echo "$FUNCTION_INFO" | jq -r '.Configuration.Runtime')
HANDLER=$(echo "$FUNCTION_INFO" | jq -r '.Configuration.Handler')

if [ "$STATE" = "Active" ] && [ "$LAST_UPDATE_STATUS" = "Successful" ]; then
    echo "Deployment successful!"
    echo "  State: $STATE"
    echo "  Last Update Status: $LAST_UPDATE_STATUS"
    echo "  Runtime: $RUNTIME"
    echo "  Handler: $HANDLER"
else
    echo "Warning: Function state may not be ready"
    echo "  State: $STATE"
    echo "  Last Update Status: $LAST_UPDATE_STATUS"
fi

echo ""
echo "=== Deployment Complete ==="
echo "Next steps:"
echo "  1. Test the function with a sample query"
echo "  2. Check CloudWatch logs for any errors"
echo "  3. Monitor performance via CloudWatch dashboard"
