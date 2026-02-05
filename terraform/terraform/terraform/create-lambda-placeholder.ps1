# PowerShell script to create Lambda placeholder zip file
# Run this before terraform apply if lambda_placeholder.zip doesn't exist

$placeholderCode = @'
def lambda_handler(event, context):
    return {
        "statusCode": 200,
        "body": "{\"message\": \"Lambda placeholder - deploy real code after terraform apply\"}"
    }
'@

# Create placeholder Python file
$placeholderFile = Join-Path $PSScriptRoot "lambda_placeholder.py"
$placeholderCode | Out-File -FilePath $placeholderFile -Encoding utf8

# Create zip file
$zipFile = Join-Path $PSScriptRoot "lambda_placeholder.zip"
if (Test-Path $zipFile) {
    Remove-Item $zipFile -Force
}

Compress-Archive -Path $placeholderFile -DestinationPath $zipFile -Force

# Clean up Python file
Remove-Item $placeholderFile -Force

Write-Host "Created lambda_placeholder.zip successfully" -ForegroundColor Green
