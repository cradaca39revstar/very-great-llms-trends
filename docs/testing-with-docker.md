# Testing con Docker Container de AWS Glue

## Overview

Esta guía explica cómo ejecutar tests de integración localmente usando el contenedor Docker oficial de AWS Glue. Esta es la solución recomendada porque:

- ✅ **Mismo entorno que producción**: Usa el mismo entorno Linux que AWS Glue
- ✅ **Sin problemas de compatibilidad**: Evita problemas de sockets en Windows
- ✅ **Todos los tests funcionan**: 100% de cobertura sin limitaciones
- ✅ **Sin costos**: Ejecución local gratuita
- ✅ **Fácil de usar**: Script automatizado incluido

---

## Requisitos Previos

### 1. Docker Desktop

**Instalación:**
- Descarga desde: https://www.docker.com/products/docker-desktop
- Instala y ejecuta Docker Desktop
- Verifica que esté corriendo: `docker info`

**Requisitos del Sistema:**
- Windows 10/11 (64-bit) con WSL 2
- Mínimo 7 GB de espacio en disco (para la imagen)
- 4 GB RAM recomendado

### 2. Proyecto Configurado

- Código del proyecto clonado localmente
- Archivo `requirements.txt` presente
- Tests en `tests/integration_test.py`

---

## Uso Rápido

### Ejecutar Tests con Script Automatizado

```powershell
# Desde la raíz del proyecto
.\scripts\test-with-aws-glue-docker.ps1
```

El script:
1. Verifica que Docker esté instalado y corriendo
2. Descarga la imagen de AWS Glue 4.0 (si no existe)
3. Monta el proyecto como volumen
4. Instala dependencias dentro del contenedor
5. Ejecuta todos los tests de integración
6. Muestra resultados

**Primera ejecución:** Puede tardar 5-10 minutos (descarga de imagen ~7GB)  
**Ejecuciones posteriores:** ~30-60 segundos

---

## Detalles Técnicos

### Imagen Docker Utilizada

- **Repositorio:** `public.ecr.aws/glue/aws-glue-libs`
- **Tag:** `glue_libs_4.0.0_image_01` (compatible con `glue_version = "4.0"` en terraform)
- **Tamaño:** ~7 GB
- **Sistema Operativo:** Amazon Linux 2023
- **Incluye:**
  - AWS Glue ETL Library
  - Apache Spark 3.5.4
  - Python 3.11
  - Todas las librerías de Glue

### Configuración del Contenedor

```powershell
docker run --rm `
    --name glue-test-container `
    -v "${projectRoot}:/home/glue_user/workspace" `
    -w /home/glue_user/workspace `
    public.ecr.aws/glue/aws-glue-libs:4.0 `
    /bin/bash -c "comandos..."
```

**Parámetros:**
- `--rm`: Elimina el contenedor automáticamente al terminar
- `-v`: Monta el proyecto como volumen (cambios se reflejan inmediatamente)
- `-w`: Establece el directorio de trabajo
- `public.ecr.aws/glue/aws-glue-libs:4.0`: Imagen oficial de AWS Glue

---

## Ejecución Manual

Si prefieres ejecutar manualmente:

### 1. Descargar Imagen

```powershell
docker pull public.ecr.aws/glue/aws-glue-libs:4.0
```

### 2. Ejecutar Contenedor Interactivo

```powershell
# Reemplazar <project-path> con la ruta a tu proyecto
docker run -it --rm `
    -v "<project-path>:/home/glue_user/workspace" `
    -w /home/glue_user/workspace `
    public.ecr.aws/glue/aws-glue-libs:4.0 `
    /bin/bash
```

### 3. Dentro del Contenedor

```bash
# Instalar dependencias
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

# Ejecutar tests
python3 -m pytest tests/integration_test.py -v

# O ejecutar un test específico
python3 -m pytest tests/integration_test.py::TestETLIntegration::test_csv_read_valid_data -v
```

---

## Troubleshooting

### Docker no está corriendo

**Error:**
```
Cannot connect to the Docker daemon
```

**Solución:**
1. Abre Docker Desktop
2. Espera a que termine de iniciar (ícono en la bandeja del sistema)
3. Verifica: `docker info`

### Imagen no descarga

**Error:**
```
Error response from daemon: pull access denied
```

**Solución:**
- La imagen es pública, no requiere autenticación
- Verifica conexión a internet
- Intenta: `docker pull public.ecr.aws/glue/aws-glue-libs:4.0`

### Tests fallan dentro del contenedor

**Posibles causas:**
1. **Dependencias no instaladas**: Verifica que `requirements.txt` esté completo
2. **Rutas incorrectas**: Asegúrate de que el volumen esté montado correctamente
3. **Permisos**: El contenedor corre como `glue_user`, verifica permisos de archivos

**Debug:**
```powershell
# Ejecutar contenedor interactivo para investigar
# Reemplazar <project-path> con la ruta a tu proyecto
docker run -it --rm `
    -v "<project-path>:/home/glue_user/workspace" `
    -w /home/glue_user/workspace `
    public.ecr.aws/glue/aws-glue-libs:4.0 `
    /bin/bash

# Dentro del contenedor:
ls -la /home/glue_user/workspace
python3 --version
python3 -m pip list
```

### Espacio en disco insuficiente

**Error:**
```
no space left on device
```

**Solución:**
- Libera espacio en disco (mínimo 7 GB para la imagen)
- Limpia imágenes Docker no usadas: `docker system prune -a`

---

## Comparación con Otras Opciones

| Método | Ventajas | Desventajas |
|--------|----------|-------------|
| **Docker Glue** ✅ | Mismo entorno que producción, todos los tests funcionan, sin costos | Requiere Docker instalado |
| **Windows Local** | No requiere Docker | Solo 30% de tests funcionan, problemas de sockets |
| **AWS Glue Real** | Proceso completo validado | Requiere infraestructura desplegada, costo mínimo |

---

## Integración con CI/CD

### GitHub Actions

```yaml
name: Integration Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run tests with Glue Docker
        run: |
          docker pull public.ecr.aws/glue/aws-glue-libs:4.0
          docker run --rm \
            -v ${{ github.workspace }}:/home/glue_user/workspace \
            -w /home/glue_user/workspace \
            public.ecr.aws/glue/aws-glue-libs:4.0 \
            /bin/bash -c "pip install -r requirements.txt && pytest tests/integration_test.py -v"
```

### GitLab CI

```yaml
test:
  image: public.ecr.aws/glue/aws-glue-libs:4.0
  script:
    - pip install -r requirements.txt
    - pytest tests/integration_test.py -v
```

---

## Referencias

- [AWS Glue Local Development Guide](https://docs.aws.amazon.com/glue/latest/dg/develop-local-docker-image.html)
- [AWS Glue Docker Images](https://hub.docker.com/r/amazon/aws-glue-libs)
- [Docker Desktop for Windows](https://docs.docker.com/desktop/install/windows-install/)

---

**Última actualización:** 24 de enero de 2026
