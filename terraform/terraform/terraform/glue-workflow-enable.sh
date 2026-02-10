#!/bin/bash
# Script to enable the EVENT-type Glue trigger after Terraform creates it
# This is required because Terraform cannot enable EVENT triggers on creation

WORKFLOW_NAME="beauty-products-etl-workflow"
TRIGGER_NAME="beauty-products-workflow-start-trigger"
AWS_REGION="${AWS_REGION:-us-east-1}"

echo "Checking if trigger exists and is disabled..."
TRIGGER_STATE=$(aws glue get-trigger --name "$TRIGGER_NAME" --region "$AWS_REGION" --query 'Trigger.State' --output text 2>/dev/null)

if [ $? -eq 0 ]; then
    echo "Trigger found. Current state: $TRIGGER_STATE"
    
    if [ "$TRIGGER_STATE" != "ACTIVATED" ]; then
        echo "Enabling trigger: $TRIGGER_NAME"
        aws glue start-trigger --name "$TRIGGER_NAME" --region "$AWS_REGION"
        
        if [ $? -eq 0 ]; then
            echo "✓ Trigger enabled successfully!"
        else
            echo "✗ Failed to enable trigger"
            exit 1
        fi
    else
        echo "✓ Trigger is already enabled"
    fi
else
    echo "✗ Trigger not found. Run terraform apply first."
    exit 1
fi
