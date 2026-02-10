# Import existing DynamoDB tables into Terraform state (run from terraform/)
# Use when tables already exist in AWS and Terraform fails with "Table already exists"
# Usage: .\import-dynamodb.ps1  or  .\import-dynamodb.ps1 -Environment dev

param([string]$Environment = "dev")

$ErrorActionPreference = "Stop"
Push-Location $PSScriptRoot

Write-Host "Importing DynamoDB tables (environment: $Environment)..." -ForegroundColor Cyan

terraform import 'aws_dynamodb_table.web_insights_cache[0]' "beauty-products-web-insights-cache-$Environment"
if ($LASTEXITCODE -ne 0) { Pop-Location; exit 1 }
Write-Host "  web_insights_cache: OK" -ForegroundColor Green

terraform import 'aws_dynamodb_table.report_status[0]' "beauty-products-report-status-$Environment"
if ($LASTEXITCODE -ne 0) { Pop-Location; exit 1 }
Write-Host "  report_status: OK" -ForegroundColor Green

Pop-Location
Write-Host "Done. Run terraform plan to verify." -ForegroundColor Cyan
