# Tail Lambda logs (LLM orchestrator) for debugging
# Usage: .\tail-lambda-logs.ps1 [-Minutes 30]

param([int]$Minutes = 30)

$ErrorActionPreference = "Stop"
$TerraformDir = Join-Path $PSScriptRoot "..\terraform"

Push-Location $TerraformDir
try {
    $fn = terraform output -raw lambda_function_name 2>$null
    if (-not $fn) { throw "Could not get lambda_function_name from Terraform." }
    Pop-Location
} catch {
    Pop-Location
    throw
}

Write-Host "Tailing /aws/lambda/$fn (last $Minutes minutes)..." -ForegroundColor Cyan
aws logs tail "/aws/lambda/$fn" --since "${Minutes}m"
