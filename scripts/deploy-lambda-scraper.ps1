# PowerShell script to package and deploy Scraper Lambda code
# Usage: .\deploy-lambda-scraper.ps1 [-Environment "poc"] [-FunctionName "beauty-products-llm-scraper-poc"] [-Region "us-east-1"]

param(
    [string]$Environment = "poc",
    [string]$FunctionName = "",
    [string]$Region = "us-east-1"
)

$ErrorActionPreference = "Stop"

Write-Host "=== Scraper Lambda Deployment Script ===" -ForegroundColor Cyan

if ([string]::IsNullOrEmpty($FunctionName)) {
    Write-Host "Getting scraper function name from Terraform..." -ForegroundColor Yellow
    Push-Location (Join-Path $PSScriptRoot "..\terraform")
    try {
        $FunctionName = terraform output -raw lambda_scraper_function_name 2>$null
        if ([string]::IsNullOrEmpty($FunctionName)) {
            throw "Could not get scraper function name from Terraform. Deploy infrastructure first or pass -FunctionName."
        }
        Write-Host "Found function: $FunctionName" -ForegroundColor Green
    } catch {
        Write-Host "Error: $_" -ForegroundColor Red
        Write-Host "Deploy Terraform first or provide -FunctionName (e.g. beauty-products-llm-scraper-poc)" -ForegroundColor Yellow
        Pop-Location
        exit 1
    }
    Pop-Location
}

$ScraperDir = Join-Path $PSScriptRoot "..\lambda_scraper"
if (-not (Test-Path $ScraperDir)) {
    Write-Host "Error: lambda_scraper directory not found at $ScraperDir" -ForegroundColor Red
    exit 1
}

$ReqFile = Join-Path $ScraperDir "requirements-scraper.txt"
if (-not (Test-Path $ReqFile)) {
    Write-Host "Error: requirements-scraper.txt not found" -ForegroundColor Red
    exit 1
}

$BuildDir = Join-Path $Env:TEMP "lambda_scraper_build_$(Get-Random)"
New-Item -ItemType Directory -Path $BuildDir -Force | Out-Null

try {
    Write-Host "`nStep 1: Installing dependencies into build dir..." -ForegroundColor Cyan
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCmd) {
        Write-Host "Error: Python not found in PATH" -ForegroundColor Red
        exit 1
    }
    python -m pip install -r $ReqFile -t $BuildDir --quiet
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error: Failed to install dependencies" -ForegroundColor Red
        exit 1
    }
    Write-Host "Dependencies installed" -ForegroundColor Green

    Copy-Item (Join-Path $ScraperDir "web_product_scraper.py") -Destination $BuildDir -Force
    Write-Host "`nStep 2: Creating deployment package..." -ForegroundColor Cyan

    $ZipFile = Join-Path $BuildDir "scraper.zip"
    if (Test-Path $ZipFile) { Remove-Item $ZipFile -Force }

    $ExcludePatterns = @("*.pyc", "__pycache__", "*.dist-info", "*.egg-info", "boto3", "botocore", "jmespath", "s3transfer")
    $FilesToZip = Get-ChildItem -Path $BuildDir -Recurse -File | Where-Object {
        $exclude = $false
        foreach ($pattern in $ExcludePatterns) {
            if ($_.FullName -like "*$pattern*") { $exclude = $true; break }
        }
        -not $exclude
    }

    $baseLen = $BuildDir.Length + 1
    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [System.IO.Compression.ZipFile]::Open($ZipFile, [System.IO.Compression.ZipArchiveMode]::Create)
    try {
        foreach ($f in $FilesToZip) {
            $rel = $f.FullName.Substring($baseLen).Replace('\', '/')
            [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($archive, $f.FullName, $rel, [System.IO.Compression.CompressionLevel]::Optimal) | Out-Null
        }
    } finally {
        $archive.Dispose()
    }
    $ZipSize = (Get-Item $ZipFile).Length / 1MB
    Write-Host "Created scraper.zip ($([math]::Round($ZipSize, 2)) MB)" -ForegroundColor Green

    Write-Host "`nStep 3: Deploying to Lambda..." -ForegroundColor Cyan
    aws lambda update-function-code `
        --function-name $FunctionName `
        --zip-file "fileb://$ZipFile" `
        --region $Region

    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error: Failed to deploy Lambda code" -ForegroundColor Red
        exit 1
    }

    Write-Host "Waiting for function update..." -ForegroundColor Yellow
    aws lambda wait function-updated --function-name $FunctionName --region $Region

    Write-Host "`nStep 4: Verifying..." -ForegroundColor Cyan
    $info = aws lambda get-function --function-name $FunctionName --region $Region | ConvertFrom-Json
    Write-Host "Deployment complete. State: $($info.Configuration.State)" -ForegroundColor Green
    Write-Host "Handler: $($info.Configuration.Handler)" -ForegroundColor Green
} finally {
    if (Test-Path $BuildDir) {
        Remove-Item -Recurse -Force $BuildDir -ErrorAction SilentlyContinue
    }
}
