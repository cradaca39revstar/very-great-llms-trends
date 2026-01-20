# PowerShell script to upload CSV files to S3 Raw Zone
# Beauty Products Data Lake - Data Ingestion Script

param(
    [Parameter(Mandatory=$false)]
    [string]$FilePath,
    
    [Parameter(Mandatory=$false)]
    [string]$Date,
    
    [Parameter(Mandatory=$false)]
    [string]$Bucket = "very-great-products-raw-us-east-1-poc",
    
    [Parameter(Mandatory=$false)]
    [string]$Region = "us-east-1"
)

$ErrorActionPreference = "Stop"

function Upload-FileToS3 {
    param(
        [string]$LocalPath,
        [string]$S3Bucket,
        [string]$S3Region,
        [int]$Year,
        [int]$Month,
        [int]$Day
    )
    
    if (-not (Test-Path $LocalPath)) {
        Write-Host "❌ Error: File not found: $LocalPath" -ForegroundColor Red
        return $false
    }
    
    $fileName = Split-Path -Leaf $LocalPath
    $s3Key = "landing/beauty-products/$Year/$($Month.ToString('00'))/$($Day.ToString('00'))/$fileName"
    
    Write-Host "📤 Uploading: $LocalPath" -ForegroundColor Cyan
    Write-Host "   → s3://$S3Bucket/$s3Key" -ForegroundColor Gray
    
    try {
        Write-S3Object -BucketName $S3Bucket `
            -Key $s3Key `
            -File $LocalPath `
            -Region $S3Region `
            -ContentType "text/csv" `
            -ServerSideEncryption AES256 `
            -Metadata @{
                "uploaded-by" = $env:USERNAME
                "upload-date" = (Get-Date -Format "yyyy-MM-ddTHH:mm:ss")
                "source" = "powershell-upload-script"
            }
        
        Write-Host "✅ Successfully uploaded to S3" -ForegroundColor Green
        Write-Host "   Full S3 path: s3://$S3Bucket/$s3Key" -ForegroundColor Gray
        return $true
    }
    catch {
        Write-Host "❌ Error uploading file: $_" -ForegroundColor Red
        return $false
    }
}

function Parse-DateFromPath {
    param([string]$Path)
    
    # Try to extract from directory structure: data/raw/YYYY/MM/DD/file.csv
    if ($Path -match 'data[\\/]raw[\\/](\d{4})[\\/](\d{1,2})[\\/](\d{1,2})') {
        return [int]$matches[1], [int]$matches[2], [int]$matches[3]
    }
    
    # Try to extract from filename: beauty-products_YYYYMMDD.csv
    $fileName = Split-Path -Leaf $Path
    if ($fileName -match 'beauty-products_(\d{4})(\d{2})(\d{2})\.csv') {
        return [int]$matches[1], [int]$matches[2], [int]$matches[3]
    }
    
    # Default to today
    $today = Get-Date
    return $today.Year, $today.Month, $today.Day
}

# Main execution
if ($Date) {
    # Parse date YYYY-MM-DD
    try {
        $dateObj = [DateTime]::ParseExact($Date, "yyyy-MM-dd", $null)
        $year = $dateObj.Year
        $month = $dateObj.Month
        $day = $dateObj.Day
        
        # Upload all CSV files for that date
        $directory = "data\raw\$year\$($month.ToString('00'))\$($day.ToString('00'))"
        if (-not (Test-Path $directory)) {
            Write-Host "❌ Error: Directory not found: $directory" -ForegroundColor Red
            exit 1
        }
        
        $csvFiles = Get-ChildItem -Path $directory -Filter "*.csv"
        if ($csvFiles.Count -eq 0) {
            Write-Host "⚠️  No CSV files found in: $directory" -ForegroundColor Yellow
            exit 0
        }
        
        Write-Host "📁 Found $($csvFiles.Count) CSV file(s) in directory" -ForegroundColor Cyan
        $successCount = 0
        foreach ($file in $csvFiles) {
            if (Upload-FileToS3 -LocalPath $file.FullName -S3Bucket $Bucket -S3Region $Region -Year $year -Month $month -Day $day) {
                $successCount++
            }
            Write-Host ""
        }
        Write-Host "✅ Uploaded $successCount/$($csvFiles.Count) file(s) successfully" -ForegroundColor Green
    }
    catch {
        Write-Host "❌ Error: Invalid date format '$Date'. Use YYYY-MM-DD" -ForegroundColor Red
        exit 1
    }
}
elseif ($FilePath) {
    if (Test-Path $FilePath -PathType Container) {
        # Upload directory
        Write-Host "📁 Uploading all CSV files from directory: $FilePath" -ForegroundColor Cyan
        $csvFiles = Get-ChildItem -Path $FilePath -Filter "*.csv" -Recurse
        if ($csvFiles.Count -eq 0) {
            Write-Host "⚠️  No CSV files found" -ForegroundColor Yellow
            exit 0
        }
        
        $successCount = 0
        foreach ($file in $csvFiles) {
            $year, $month, $day = Parse-DateFromPath -Path $file.FullName
            if (Upload-FileToS3 -LocalPath $file.FullName -S3Bucket $Bucket -S3Region $Region -Year $year -Month $month -Day $day) {
                $successCount++
            }
            Write-Host ""
        }
        Write-Host "✅ Uploaded $successCount/$($csvFiles.Count) file(s) successfully" -ForegroundColor Green
    }
    elseif (Test-Path $FilePath -PathType Leaf) {
        # Upload single file
        $year, $month, $day = Parse-DateFromPath -Path $FilePath
        $success = Upload-FileToS3 -LocalPath $FilePath -S3Bucket $Bucket -S3Region $Region -Year $year -Month $month -Day $day
        exit $(if ($success) { 0 } else { 1 })
    }
    else {
        Write-Host "❌ Error: Path not found: $FilePath" -ForegroundColor Red
        exit 1
    }
}
else {
    Write-Host @"
Usage:
  .\scripts\upload_to_s3.ps1 -FilePath "data\raw\2024\04\17\beauty-products_20240417.csv"
  .\scripts\upload_to_s3.ps1 -Date "2024-04-17"
  .\scripts\upload_to_s3.ps1 -FilePath "data\raw\2024\04\17\" -Bucket "custom-bucket"

Examples:
  # Upload a specific file
  .\scripts\upload_to_s3.ps1 -FilePath "data\raw\2024\04\17\beauty-products_20240417.csv"
  
  # Upload all files for a specific date
  .\scripts\upload_to_s3.ps1 -Date "2024-04-17"
"@
    exit 1
}
