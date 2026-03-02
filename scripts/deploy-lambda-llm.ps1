# PowerShell script to package and deploy Lambda code for LLM Trending Products
# Usage: .\deploy-lambda-llm.ps1 [-Environment "poc"] [-FunctionName "beauty-products-llm-orchestrator-poc"] [-UseDocker $true]
# UseDocker: build deps in Linux container so Pillow works in Lambda (required when building on Windows).

param(
    [string]$Environment = "poc",
    [string]$FunctionName = "",
    [bool]$UseDocker = $false
)

$ErrorActionPreference = "Stop"

Write-Host "=== LLM Lambda Deployment Script ===" -ForegroundColor Cyan

# Get function name from Terraform if not provided
if ([string]::IsNullOrEmpty($FunctionName)) {
    Write-Host "Getting function name from Terraform..." -ForegroundColor Yellow
    Push-Location (Join-Path $PSScriptRoot "..\terraform")
    try {
        $FunctionName = terraform output -raw lambda_function_name 2>$null
        if ([string]::IsNullOrEmpty($FunctionName)) {
            throw "Could not get function name from Terraform. Please deploy infrastructure first or provide -FunctionName parameter."
        }
        Write-Host "Found function: $FunctionName" -ForegroundColor Green
    } catch {
        Write-Host "Error: $_" -ForegroundColor Red
        Write-Host "Please provide -FunctionName parameter or deploy Terraform infrastructure first." -ForegroundColor Yellow
        Pop-Location
        exit 1
    } finally {
        Pop-Location
    }
}

# Navigate to lambda directory
$LambdaDir = Join-Path $PSScriptRoot "..\lambda"
if (-not (Test-Path $LambdaDir)) {
    Write-Host "Error: Lambda directory not found at $LambdaDir" -ForegroundColor Red
    exit 1
}

Push-Location $LambdaDir

$reqFile = "requirements-lambda.txt"
if (-not (Test-Path $reqFile)) {
    Write-Host "Error: $reqFile not found." -ForegroundColor Red
    exit 1
}

try {
    Write-Host "`nStep 1: Installing dependencies..." -ForegroundColor Cyan
    $depsOk = $false
    if ($UseDocker) {
        try {
            $null = docker info 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Host "Using Docker (Lambda-compatible Linux for Pillow)..." -ForegroundColor Yellow
                $lambdaAbs = (Get-Location).Path.Replace('\', '/')
                docker run --rm --platform linux/amd64 `
                    -v "${lambdaAbs}:/src" `
                    -w /src `
                    public.ecr.aws/lambda/python:3.10 `
                    pip install -r requirements-lambda.txt -t . --quiet
                if ($LASTEXITCODE -eq 0) {
                    $depsOk = $true
                    Write-Host "Dependencies installed via Docker" -ForegroundColor Green
                }
            }
        } catch {
            Write-Host "Docker failed: $_" -ForegroundColor Yellow
        }
    }
    if (-not $depsOk) {
        $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
        if (-not $pythonCmd) {
            Write-Host "Warning: Python not found in PATH. Skipping dependency installation." -ForegroundColor Yellow
        } else {
            Write-Host "Step 1a: Pillow for Lambda (Linux x86_64)..." -ForegroundColor Yellow
            if (Test-Path "PIL") { Remove-Item -Recurse -Force "PIL" }
            Get-ChildItem -Directory -Filter "Pillow*.dist-info" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
            python -m pip install Pillow -t . --quiet --platform manylinux2014_x86_64 --implementation cp --python-version 3.10 --only-binary=:all: --upgrade
            if ($LASTEXITCODE -ne 0) {
                Write-Host "Error: Failed to install Pillow for Linux" -ForegroundColor Red
                exit 1
            }
            Write-Host "Step 1b: fpdf2, python-dateutil, requests (pure Python)..." -ForegroundColor Yellow
            python -m pip install fpdf2 python-dateutil requests -t . --quiet
            if ($LASTEXITCODE -ne 0) {
                Write-Host "Error: Failed to install dependencies" -ForegroundColor Red
                exit 1
            }
            Write-Host "Dependencies installed (Pillow=Linux, rest=pure Python)" -ForegroundColor Green
            $depsOk = $true
        }
    }
    
    Write-Host "`nStep 2: Creating deployment package..." -ForegroundColor Cyan
    
    $ZipFile = "function.zip"
    if (Test-Path $ZipFile) {
        Remove-Item $ZipFile -Force
        Write-Host "Removed existing $ZipFile" -ForegroundColor Yellow
    }
    
    # Create zip excluding unnecessary files.
    # Exclude boto3/botocore/jmespath/s3transfer (Lambda runtime provides them; bundling can cause ast.NodeVisitor errors).
    $ExcludePatterns = @(
        "*.pyc",
        "__pycache__",
        "*.git*",
        "*.zip",
        "*.md",
        ".pytest_cache",
        "*.pytest_cache",
        "tests",
        "test_*",
        "boto3",
        "botocore",
        "jmespath",
        "s3transfer"
    )
    
    $FilesToZip = Get-ChildItem -Recurse -File | Where-Object {
        $exclude = $false
        foreach ($pattern in $ExcludePatterns) {
            if ($_.FullName -like "*$pattern*") {
                $exclude = $true
                break
            }
        }
        -not $exclude
    }
    
    # Build zip with relative paths so Lambda gets fontTools/, fpdf/, utils/, etc. (Compress-Archive flattens)
    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $baseDir = (Get-Location).Path.TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
    $zipPath = (Join-Path (Get-Location) $ZipFile)
    $archive = [System.IO.Compression.ZipFile]::Open($zipPath, [System.IO.Compression.ZipArchiveMode]::Create)
    try {
        foreach ($f in $FilesToZip) {
            $rel = $f.FullName.Substring($baseDir.Length).Replace('\', '/')
            [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($archive, $f.FullName, $rel, [System.IO.Compression.CompressionLevel]::Optimal) | Out-Null
        }
    } finally {
        $archive.Dispose()
    }
    $ZipSize = (Get-Item $ZipFile).Length / 1MB
    
    Write-Host "Created $ZipFile ($([math]::Round($ZipSize, 2)) MB)" -ForegroundColor Green
    
    Write-Host "`nStep 3: Deploying to Lambda..." -ForegroundColor Cyan
    Write-Host "Function: $FunctionName" -ForegroundColor Yellow
    
    # Deploy to Lambda
    aws lambda update-function-code `
        --function-name $FunctionName `
        --zip-file "fileb://$ZipFile" `
        --region us-east-1
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error: Failed to deploy Lambda code" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "Waiting for function update to complete..." -ForegroundColor Yellow
    aws lambda wait function-updated --function-name $FunctionName --region us-east-1
    
    Write-Host "`nStep 4: Verifying deployment..." -ForegroundColor Cyan
    
    $FunctionInfo = aws lambda get-function --function-name $FunctionName --region us-east-1 | ConvertFrom-Json
    $State = $FunctionInfo.Configuration.State
    $LastUpdateStatus = $FunctionInfo.Configuration.LastUpdateStatus
    
    if ($State -eq "Active" -and $LastUpdateStatus -eq "Successful") {
        Write-Host "Deployment successful!" -ForegroundColor Green
        Write-Host "  State: $State" -ForegroundColor Green
        Write-Host "  Last Update Status: $LastUpdateStatus" -ForegroundColor Green
        Write-Host "  Runtime: $($FunctionInfo.Configuration.Runtime)" -ForegroundColor Green
        Write-Host "  Handler: $($FunctionInfo.Configuration.Handler)" -ForegroundColor Green
    } else {
        Write-Host "Warning: Function state may not be ready" -ForegroundColor Yellow
        Write-Host "  State: $State" -ForegroundColor Yellow
        Write-Host "  Last Update Status: $LastUpdateStatus" -ForegroundColor Yellow
    }
    
    Write-Host "`n=== Deployment Complete ===" -ForegroundColor Cyan
    Write-Host "Next steps:" -ForegroundColor Yellow
    Write-Host "  1. Test the function with a sample query" -ForegroundColor White
    Write-Host "  2. Check CloudWatch logs for any errors" -ForegroundColor White
    Write-Host "  3. Monitor performance via CloudWatch dashboard" -ForegroundColor White
    
} catch {
    Write-Host "`nError: $_" -ForegroundColor Red
    exit 1
} finally {
    Pop-Location
}
