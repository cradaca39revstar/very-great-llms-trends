# PowerShell script to enable the EVENT-type Glue trigger after Terraform creates it
# This is required because Terraform cannot enable EVENT triggers on creation

$WorkflowName = "beauty-products-etl-workflow"
$TriggerName = "beauty-products-workflow-start-trigger"
$AwsRegion = if ($env:AWS_REGION) { $env:AWS_REGION } else { "us-east-1" }

Write-Host "Checking if trigger exists and is disabled..."

try {
    $trigger = aws glue get-trigger --name $TriggerName --region $AwsRegion --output json | ConvertFrom-Json
    $triggerState = $trigger.Trigger.State
    
    Write-Host "Trigger found. Current state: $triggerState"
    
    if ($triggerState -ne "ACTIVATED") {
        Write-Host "Enabling trigger: $TriggerName"
        aws glue start-trigger --name $TriggerName --region $AwsRegion
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✓ Trigger enabled successfully!" -ForegroundColor Green
        } else {
            Write-Host "✗ Failed to enable trigger" -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "✓ Trigger is already enabled" -ForegroundColor Green
    }
} catch {
    Write-Host "✗ Trigger not found. Run terraform apply first." -ForegroundColor Red
    exit 1
}
