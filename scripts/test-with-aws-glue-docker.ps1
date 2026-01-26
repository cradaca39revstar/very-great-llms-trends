# Script para ejecutar tests usando contenedor Docker de AWS Glue
# Esto evita problemas de sockets en Windows y permite probar con el entorno real de Glue

Write-Host "=== Testing con AWS Glue Docker Container ===" -ForegroundColor Cyan
Write-Host ""

# Cambiar al directorio del proyecto (usar directorio actual del script)
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
Set-Location $projectRoot

# Verificar Docker
Write-Host "Verificando Docker..." -ForegroundColor Cyan
$dockerInstalled = Get-Command docker -ErrorAction SilentlyContinue
if (-not $dockerInstalled) {
    Write-Host "Docker no esta instalado" -ForegroundColor Red
    Write-Host ""
    Write-Host "Instala Docker Desktop desde: https://www.docker.com/products/docker-desktop" -ForegroundColor Yellow
    Write-Host "Luego vuelve a ejecutar este script." -ForegroundColor Yellow
    exit 1
}

$dockerRunning = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker no esta corriendo" -ForegroundColor Red
    Write-Host ""
    Write-Host "Inicia Docker Desktop y vuelve a intentar." -ForegroundColor Yellow
    Write-Host "Verifica que el icono de Docker este visible en la bandeja del sistema." -ForegroundColor Gray
    exit 1
}

Write-Host "Docker esta corriendo" -ForegroundColor Green
Write-Host ""

# Configurar variables
$glueVersion = "4.0"  # Compatible con terraform (glue_version = "4.0")
$imageName = "public.ecr.aws/glue/aws-glue-libs:glue_libs_4.0.0_image_01"
$containerName = "glue-test-container"

Write-Host "=== Configuracion ===" -ForegroundColor Cyan
Write-Host "Imagen: $imageName" -ForegroundColor Gray
Write-Host "Contenedor: $containerName" -ForegroundColor Gray
Write-Host "Proyecto: $projectRoot" -ForegroundColor Gray
Write-Host ""

# Verificar si el contenedor ya existe y eliminarlo
$existingContainer = docker ps -a --filter "name=$containerName" --format '{{.Names}}' 2>&1
if ($existingContainer -eq $containerName) {
    Write-Host "Eliminando contenedor existente..." -ForegroundColor Yellow
    docker rm -f $containerName 2>&1 | Out-Null
}

# Verificar si la imagen existe
Write-Host "Verificando imagen Docker..." -ForegroundColor Cyan
$imageExists = docker images --format '{{.Repository}}:{{.Tag}}' 2>&1 | Select-String -Pattern $imageName
if (-not $imageExists) {
    Write-Host "Imagen no encontrada. Descargando AWS Glue $glueVersion..." -ForegroundColor Yellow
    Write-Host "Esto puede tardar varios minutos (imagen ~7GB)..." -ForegroundColor Gray
    Write-Host ""
    
    docker pull $imageName
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error al descargar la imagen" -ForegroundColor Red
        Write-Host "Verifica tu conexion a internet y vuelve a intentar." -ForegroundColor Yellow
        exit 1
    }
    Write-Host "Imagen descargada exitosamente" -ForegroundColor Green
} else {
    Write-Host "Imagen ya existe localmente" -ForegroundColor Green
}
Write-Host ""

# Ejecutar tests en contenedor
Write-Host "=== Ejecutando Tests de Integracion ===" -ForegroundColor Cyan
Write-Host ""

Write-Host "Iniciando contenedor y ejecutando tests..." -ForegroundColor Yellow
Write-Host ""

# Ejecutar el comando Docker directamente
# Usar --entrypoint para sobrescribir el entrypoint por defecto de la imagen Glue
docker run --rm `
    --name $containerName `
    --entrypoint /bin/sh `
    -v "${projectRoot}:/home/glue_user/workspace" `
    -w /home/glue_user/workspace `
    $imageName `
    -c "cd /home/glue_user/workspace && echo 'Actualizando pip...' && python3 -m pip install --upgrade pip -q && echo 'Instalando dependencias...' && python3 -m pip install -r requirements.txt && echo '' && echo 'Ejecutando tests...' && python3 -m pytest tests/integration_test.py -v --tb=short"

$testExitCode = $LASTEXITCODE

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
if ($testExitCode -eq 0) {
    Write-Host "=== Todos los tests pasaron exitosamente ===" -ForegroundColor Green
} else {
    Write-Host "=== Algunos tests fallaron ===" -ForegroundColor Yellow
    Write-Host "Revisa los resultados arriba para mas detalles." -ForegroundColor Gray
}
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Nota: Este contenedor usa el entorno real de AWS Glue (Linux)" -ForegroundColor Cyan
Write-Host "      Todos los tests deberian funcionar sin problemas de sockets." -ForegroundColor Cyan
Write-Host ""
Write-Host "Para mas informacion, consulta: docs/testing-with-docker.md" -ForegroundColor Gray

exit $testExitCode
