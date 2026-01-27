#!/bin/bash
# Bash script to create Lambda placeholder zip file
# Run this before terraform apply if lambda_placeholder.zip doesn't exist

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLACEHOLDER_FILE="${SCRIPT_DIR}/lambda_placeholder.py"
ZIP_FILE="${SCRIPT_DIR}/lambda_placeholder.zip"

# Create placeholder Python file
cat > "$PLACEHOLDER_FILE" << 'EOF'
def lambda_handler(event, context):
    return {
        "statusCode": 200,
        "body": '{"message": "Lambda placeholder - deploy real code after terraform apply"}'
    }
EOF

# Create zip file
if [ -f "$ZIP_FILE" ]; then
    rm "$ZIP_FILE"
fi

zip "$ZIP_FILE" "$PLACEHOLDER_FILE"

# Clean up Python file
rm "$PLACEHOLDER_FILE"

echo "Created lambda_placeholder.zip successfully"
