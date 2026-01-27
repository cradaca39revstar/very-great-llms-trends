# Call LLM Trending Products API (Cognito auth + POST /trending-products/query)
# Usage: .\call-api-llm.ps1
# Ensure: terraform applied, Lambda deployed, Cognito user verygreat@test.com created.

$ErrorActionPreference = "Stop"

$TerraformDir = Join-Path $PSScriptRoot "..\terraform"
$Username = "verygreat@test.com"
$Password = "VeryGreat123!"

Write-Host "=== LLM API Test ===" -ForegroundColor Cyan
Push-Location $TerraformDir
try {
    Write-Host "Getting Terraform outputs..." -ForegroundColor Yellow
    $COGNITO_USER_POOL_ID = terraform output -raw cognito_user_pool_id
    $COGNITO_CLIENT_ID   = terraform output -raw cognito_client_id
    $API_URL             = terraform output -raw api_gateway_url
    Write-Host "API URL: $API_URL" -ForegroundColor Gray

    Write-Host "Getting IdToken from Cognito..." -ForegroundColor Yellow
    $authJson = aws cognito-idp initiate-auth `
        --auth-flow USER_PASSWORD_AUTH `
        --client-id $COGNITO_CLIENT_ID `
        --auth-parameters "USERNAME=$Username,PASSWORD=$Password" `
        --query 'AuthenticationResult' `
        --output json
    $auth = $authJson | ConvertFrom-Json
    $token = $auth.IdToken
    if (-not $token) { throw "No IdToken in auth response." }
    Write-Host "Token obtained." -ForegroundColor Green

    Write-Host "Calling API (POST)..." -ForegroundColor Yellow
    $body = @{ query = "What are the top trending products in Skincare?" } | ConvertTo-Json
    $headers = @{
        "Authorization" = "Bearer $token"
        "Content-Type"  = "application/json"
    }
    $response = Invoke-RestMethod -Uri $API_URL -Method POST -Headers $headers -Body $body
    Write-Host "Success." -ForegroundColor Green
    $response | ConvertTo-Json -Depth 10
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
    Write-Host "Tip: Run .\tail-lambda-logs.ps1 to see Lambda logs." -ForegroundColor Yellow
    exit 1
} finally {
    Pop-Location
}
