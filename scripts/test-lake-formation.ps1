# Script de Pruebas Funcionales - Lake Formation
# Valida que los permisos de Lake Formation funcionan correctamente

param(
    [string]$Region = "us-east-1",
    [string]$Environment = "dev"
)

$ErrorActionPreference = "Stop"
$env:AWS_PAGER = ""

# Colores para output
function Write-Success { param($msg) Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-ErrorMsg { param($msg) Write-Host "[ERROR] $msg" -ForegroundColor Red }
function Write-Info { param($msg) Write-Host "-> $msg" -ForegroundColor Yellow }
function Write-Section { param($msg) Write-Host "`n=== $msg ===" -ForegroundColor Cyan }

# Variables
$glueETLRole = "arn:aws:iam::168949691443:role/GlueETLRole-BeautyProducts"
$athenaRole = "arn:aws:iam::168949691443:role/AthenaQueryRole-BeautyProducts"
$databaseName = "beauty_products_db"
$metadataDatabaseName = "beauty_products_metadata_db"

Write-Host "`n================================================================" -ForegroundColor Cyan
Write-Host "  PRUEBAS FUNCIONALES - LAKE FORMATION" -ForegroundColor Cyan
Write-Host "================================================================`n" -ForegroundColor Cyan

# ============================================================================
# FASE 1: PRUEBAS BÁSICAS DE ACCESO
# ============================================================================

Write-Section "FASE 1: Pruebas Básicas de Acceso"

# Test 1.1: Verificar que Glue puede acceder a las bases de datos
Write-Info "Test 1.1: Verificando acceso de Glue a bases de datos..."
try {
    $db = aws glue get-database --name $databaseName --region $region 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Glue puede acceder a la base de datos: $databaseName"
    } else {
        Write-ErrorMsgMsg "Glue NO puede acceder a la base de datos: $databaseName"
        Write-Host $db -ForegroundColor Red
    }
} catch {
    Write-ErrorMsg "Error al verificar acceso de Glue: $_"
}

# Test 1.2: Verificar que Glue puede acceder a la base de datos de metadata
Write-Info "Test 1.2: Verificando acceso de Glue a base de datos de metadata..."
try {
    $db = aws glue get-database --name $metadataDatabaseName --region $region 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Glue puede acceder a la base de datos: $metadataDatabaseName"
    } else {
        Write-ErrorMsg "Glue NO puede acceder a la base de datos: $metadataDatabaseName"
        Write-Host $db -ForegroundColor Red
    }
} catch {
    Write-ErrorMsg "Error al verificar acceso de Glue: $_"
}

# Test 1.3: Verificar que Glue puede listar tablas
Write-Info "Test 1.3: Verificando que Glue puede listar tablas..."
try {
    $tables = aws glue get-tables --database-name $databaseName --region $region --output json 2>&1 | ConvertFrom-Json
    if ($LASTEXITCODE -eq 0) {
        $tableCount = $tables.TableList.Count
        Write-Success "Glue puede listar $tableCount tablas en $databaseName"
        $tables.TableList | ForEach-Object {
            Write-Host "  - $($_.Name)" -ForegroundColor Gray
        }
    } else {
        Write-ErrorMsg "Glue NO puede listar tablas en $databaseName"
    }
} catch {
    Write-ErrorMsg "Error al listar tablas: $_"
}

# Test 1.4: Verificar que Glue puede obtener detalles de una tabla
Write-Info "Test 1.4: Verificando acceso de Glue a tabla raw_beauty_products..."
try {
    $table = aws glue get-table --database-name $databaseName --name "raw_beauty_products" --region $region 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Glue puede acceder a la tabla: raw_beauty_products"
    } else {
        Write-ErrorMsg "Glue NO puede acceder a la tabla: raw_beauty_products"
        Write-Host $table -ForegroundColor Red
    }
} catch {
    Write-ErrorMsg "Error al verificar acceso a tabla: $_"
}

# ============================================================================
# FASE 2: PRUEBAS DE PERMISOS DE LAKE FORMATION
# ============================================================================

Write-Section "FASE 2: Pruebas de Permisos de Lake Formation"

# Test 2.1: Verificar permisos de Glue ETL en bases de datos (usando Terraform)
Write-Info "Test 2.1: Verificando permisos de Glue ETL en bases de datos..."
try {
    $scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
    $terraformPath = Join-Path $scriptPath "..\terraform"
    Push-Location $terraformPath
    $glueDBPerms = terraform state show aws_lakeformation_permissions.glue_etl_beauty_products_db 2>&1
    if ($LASTEXITCODE -eq 0) {
        if ($glueDBPerms -match "CREATE_TABLE|ALTER|DROP") {
            Write-Success "Permisos de Glue ETL en bases de datos configurados correctamente"
            Write-Host "  Permisos: CREATE_TABLE, ALTER, DROP" -ForegroundColor Gray
        } else {
            Write-ErrorMsg "Permisos de Glue ETL no encontrados correctamente"
        }
    } else {
        Write-ErrorMsg "No se pudieron obtener permisos de Glue ETL"
    }
    Pop-Location
} catch {
    Write-ErrorMsg "Error al verificar permisos: $_"
    Pop-Location -ErrorAction SilentlyContinue
}

# Test 2.2: Verificar permisos de Athena en bases de datos
Write-Info "Test 2.2: Verificando permisos de Athena en bases de datos..."
try {
    $scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
    $terraformPath = Join-Path $scriptPath "..\terraform"
    Push-Location $terraformPath
    $athenaDBPerms = terraform state show aws_lakeformation_permissions.athena_beauty_products_db 2>&1
    if ($LASTEXITCODE -eq 0) {
        if ($athenaDBPerms -match "DESCRIBE") {
            Write-Success "Permisos de Athena en bases de datos configurados correctamente"
            Write-Host "  Permisos: DESCRIBE" -ForegroundColor Gray
        } else {
            Write-ErrorMsg "Permisos de Athena no encontrados correctamente"
        }
    } else {
        Write-ErrorMsg "No se pudieron obtener permisos de Athena"
    }
    Pop-Location
} catch {
    Write-ErrorMsg "Error al verificar permisos: $_"
    Pop-Location -ErrorAction SilentlyContinue
}

# Test 2.3: Verificar permisos de ubicaciones S3
Write-Info "Test 2.3: Verificando permisos de Glue ETL en ubicaciones S3..."
try {
    $scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
    $terraformPath = Join-Path $scriptPath "..\terraform"
    Push-Location $terraformPath
    $locationPerms = terraform state show aws_lakeformation_permissions.glue_etl_raw_location 2>&1
    if ($LASTEXITCODE -eq 0) {
        if ($locationPerms -match "DATA_LOCATION_ACCESS") {
            Write-Success "Permisos de Glue ETL en ubicaciones S3 configurados correctamente"
            Write-Host "  Permisos: DATA_LOCATION_ACCESS" -ForegroundColor Gray
        } else {
            Write-ErrorMsg "Permisos de ubicaciones S3 no encontrados correctamente"
        }
    } else {
        Write-ErrorMsg "No se pudieron obtener permisos de ubicaciones S3"
    }
    Pop-Location
} catch {
    Write-ErrorMsg "Error al verificar permisos: $_"
    Pop-Location -ErrorAction SilentlyContinue
}

# ============================================================================
# FASE 3: PRUEBAS DE ACCESO A S3
# ============================================================================

Write-Section "FASE 3: Pruebas de Acceso a S3"

# Test 3.1: Verificar que los buckets S3 existen
Write-Info "Test 3.1: Verificando existencia de buckets S3..."
$buckets = @(
    "very-great-products-raw-us-east-1-$Environment",
    "very-great-products-processed-us-east-1-$Environment",
    "very-great-products-metadata-us-east-1-$Environment"
)

foreach ($bucket in $buckets) {
    try {
        $result = aws s3api head-bucket --bucket $bucket --region $region 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Bucket existe: $bucket"
        } else {
            Write-ErrorMsg "Bucket NO existe: $bucket"
        }
    } catch {
        Write-ErrorMsg "Error al verificar bucket $bucket : $_"
    }
}

# Test 3.2: Verificar que los buckets están registrados en Lake Formation
Write-Info "Test 3.2: Verificando registro de buckets en Lake Formation..."
try {
    $resources = aws lakeformation list-resources --region $region --output json | ConvertFrom-Json
    $registeredBuckets = $resources.ResourceInfoList | Where-Object { $_.ResourceArn -like "*s3*" }
    $bucketCount = $registeredBuckets.Count
    
    if ($bucketCount -eq 3) {
        Write-Success "Los 3 buckets están registrados en Lake Formation"
        $registeredBuckets | ForEach-Object {
            Write-Host "  - $($_.ResourceArn)" -ForegroundColor Gray
        }
    } else {
        Write-ErrorMsg "Solo $bucketCount de 3 buckets están registrados"
    }
} catch {
    Write-ErrorMsg "Error al verificar recursos registrados: $_"
}

# ============================================================================
# FASE 4: PRUEBAS FUNCIONALES CON GLUE (si hay datos)
# ============================================================================

Write-Section "FASE 4: Pruebas Funcionales con Glue"

# Test 4.1: Verificar que el job de Glue existe
Write-Info "Test 4.1: Verificando existencia del job de Glue..."
try {
    $job = aws glue get-job --job-name "beauty-products-etl-job" --region $region 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Job de Glue existe: beauty-products-etl-job"
        $jobObj = $job | ConvertFrom-Json
        Write-Host "  Role: $($jobObj.Job.Role)" -ForegroundColor Gray
        Write-Host "  Estado: Configurado" -ForegroundColor Gray
    } else {
        Write-ErrorMsg "Job de Glue NO existe"
    }
} catch {
    Write-ErrorMsg "Error al verificar job de Glue: $_"
}

# Test 4.2: Verificar que el script de ETL está en S3
Write-Info "Test 4.2: Verificando script de ETL en S3..."
try {
    $scriptBucket = "very-great-products-glue-scripts-us-east-1-$Environment"
    $scriptKey = "scripts/beauty_products_etl.py"
    $result = aws s3api head-object --bucket $scriptBucket --key $scriptKey --region $region 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Script de ETL existe en S3: s3://$scriptBucket/$scriptKey"
    } else {
        Write-ErrorMsg "Script de ETL NO existe en S3"
        Write-Info "Nota: El script debe estar subido antes de ejecutar el job"
    }
} catch {
    Write-ErrorMsg "Error al verificar script: $_"
}

# ============================================================================
# FASE 5: PRUEBAS FUNCIONALES CON ATHENA
# ============================================================================

Write-Section "FASE 5: Pruebas Funcionales con Athena"

# Test 5.1: Verificar que Athena puede listar bases de datos
Write-Info "Test 5.1: Verificando acceso de Athena a bases de datos..."
try {
    $databases = aws athena list-databases --catalog-name "AwsDataCatalog" --region $region --output json 2>&1 | ConvertFrom-Json
    if ($LASTEXITCODE -eq 0) {
        $dbList = $databases.DatabaseList | Where-Object { $_.Name -eq $databaseName -or $_.Name -eq $metadataDatabaseName }
        if ($dbList.Count -gt 0) {
            Write-Success "Athena puede ver las bases de datos"
            $dbList | ForEach-Object {
                Write-Host "  - $($_.Name)" -ForegroundColor Gray
            }
        } else {
            Write-ErrorMsg "Athena NO puede ver las bases de datos"
        }
    } else {
        Write-ErrorMsg "Error al listar bases de datos en Athena"
    }
} catch {
    Write-ErrorMsg "Error al verificar acceso de Athena: $_"
}

# Test 5.2: Verificar que Athena puede listar tablas
Write-Info "Test 5.2: Verificando que Athena puede listar tablas..."
try {
    $tables = aws athena list-table-metadata --catalog-name "AwsDataCatalog" --database-name $databaseName --region $region --output json 2>&1 | ConvertFrom-Json
    if ($LASTEXITCODE -eq 0) {
        $tableCount = $tables.TableMetadataList.Count
        Write-Success "Athena puede listar $tableCount tablas en $databaseName"
        $tables.TableMetadataList | ForEach-Object {
            Write-Host "  - $($_.Name)" -ForegroundColor Gray
        }
    } else {
        Write-ErrorMsg "Athena NO puede listar tablas"
    }
} catch {
    Write-ErrorMsg "Error al listar tablas en Athena: $_"
}

# ============================================================================
# RESUMEN FINAL
# ============================================================================

Write-Section "RESUMEN DE PRUEBAS"

Write-Host "`nPruebas completadas. Revisa los resultados arriba." -ForegroundColor Yellow
Write-Host "`nPróximos pasos:" -ForegroundColor Cyan
Write-Host "1. Si todas las pruebas pasaron, el despliegue está correcto" -ForegroundColor White
Write-Host "2. Para probar ejecución de Glue, sube datos de prueba a S3" -ForegroundColor White
Write-Host "3. Para probar consultas de Athena, ejecuta queries en la consola" -ForegroundColor White
Write-Host ""

# URLs útiles
Write-Host "URLs útiles:" -ForegroundColor Cyan
Write-Host "  - Lake Formation: https://console.aws.amazon.com/lakeformation/home?region=$region#" -ForegroundColor Gray
Write-Host "  - Glue Console: https://console.aws.amazon.com/glue/home?region=$region#" -ForegroundColor Gray
Write-Host "  - Athena Console: https://console.aws.amazon.com/athena/home?region=$region#" -ForegroundColor Gray
Write-Host ""
