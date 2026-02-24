# Runbook: E2E Test Data Lake → LLM (éxito del proyecto)

**Objetivo:** Llenar la BD con datos de los últimos 30 días en diferentes fechas, dejar **una categoría vacía** para validar el mensaje sin registros, y ejecutar un test E2E completo (DL → LLM) con CloudWatch en varias categorías.

**Categorías L2 (dropdown):** Bath & Body Care, Eye & Ear Care, Fragrance, Haircare & Styling, Hand, Foot & Nail Care, Makeup, Men's Care, Nasal & Oral Care, Personal Care Appliances, Skincare, Special Personal Care.

**Categoría vacía (sin registros):** **Eye & Ear Care** — no se cargará ningún dato para esta categoría.

---

## Rutas S3 (entorno dev)

- **Raw (origen):** `s3://very-great-products-raw-us-east-1-dev/landing/beauty-products/YYYY/MM/DD/beauty-products_YYYYMMDD.csv`
- **Curated (destino ETL):** `s3://very-great-products-processed-us-east-1-dev/curated/beauty-products/year=2026/month_num=2/` (y `month_num=1` si hay datos de enero).

Los datos deben quedar en **curated** con particiones `year=YYYY/month_num=M/` para que Athena y el LLM los usen.

---

## Comandos rápidos (resumen)

```powershell
# 1. Generar datos (últimos 30 días, 4 fechas; todas las categorías menos Eye & Ear Care)
python scripts/generate_sample_data_for_categories.py --output-dir data/raw --empty-category "Eye & Ear Care"

# 2. Subir TODO lo generado a S3 raw (una sola vez)
aws s3 sync data/raw/ s3://very-great-products-raw-us-east-1-dev/landing/beauty-products/ --exclude "*" --include "*.csv"

# 3. Ejecutar ETL Glue
aws glue start-job-run --job-name beauty-products-etl-job

# 4. Esperar que el job termine, luego ejecutar crawler curated
aws glue start-crawler --name beauty-products-curated-crawler

# 5. Cuando el crawler esté READY, E2E multi-categoría
python scripts/e2e-llm-multi-category.py
```

---

## Resumen de pasos

| Paso | Acción | Resultado esperado |
|------|--------|--------------------|
| 1 | Generar CSVs de prueba (varias fechas, todas las categorías excepto Eye & Ear Care) | Archivos en `data/raw/YYYY/MM/DD/` |
| 2 | Subir CSVs a S3 raw | Datos en `s3://{raw-bucket}/landing/beauty-products/` |
| 3 | Ejecutar ETL Glue (y workflow si aplica) | Parquet en `s3://{curated-bucket}/curated/beauty-products/` |
| 4 | Ejecutar crawler de tabla curated | Particiones visibles en Athena |
| 5 | Verificar categoría vacía en Athena | 0 filas para "Eye & Ear Care" |
| 6 | E2E LLM por categoría (varias) | Reporte OK en categorías con datos |
| 7 | E2E LLM en categoría vacía | Mensaje "Category not found in last 30 days" / sin registros |
| 8 | Revisar CloudWatch | Métricas y logs coherentes con las ejecuciones |

---

## Prerrequisitos

- AWS CLI configurado con permisos adecuados.
- Terraform aplicado (buckets, Glue, Lambda, API Gateway, Cognito).
- Lambda LLM desplegada.
- Usuario Cognito de prueba (ej. `verygreat@test.com` / `VeryGreat123!`).
- Variables: `ENVIRONMENT=dev` (o `poc`) según tu despliegue.

---

## Paso 1: Generar datos de prueba

Genera CSVs para **últimos 30 días** (4 fechas por defecto) y **todas las categorías excepto Eye & Ear Care**.

```powershell
# Desde la raíz del repo
python scripts/generate_sample_data_for_categories.py --output-dir data/raw --empty-category "Eye & Ear Care"
```

Esto crea archivos bajo `data/raw/YYYY/MM/DD/beauty-products_YYYYMMDD.csv` (ej. 2026/01/19, 2026/01/29, 2026/02/08, 2026/02/18) con productos en todas las categorías **menos** "Eye & Ear Care". El ETL escribirá particiones `year=2026/month_num=1/` y `year=2026/month_num=2/` en curated.

**Verificación:** Lista las fechas generadas: `Get-ChildItem -Path data/raw -Recurse -Filter "*.csv" | Select-Object FullName`

---

## Paso 2: Subir datos a S3 (raw)

Bucket raw para entorno **dev**: `very-great-products-raw-us-east-1-dev`. La ruta en S3 debe ser `landing/beauty-products/YYYY/MM/DD/beauty-products_YYYYMMDD.csv`.

**Opción A – Subir todo de una vez (recomendado):**

```powershell
aws s3 sync data/raw/ s3://very-great-products-raw-us-east-1-dev/landing/beauty-products/ --exclude "*" --include "*.csv"
```

**Opción B – Por fecha** (si ya sabes las fechas generadas):

```powershell
python scripts/upload_to_s3.py --date 2026-01-19 --bucket very-great-products-raw-us-east-1-dev
python scripts/upload_to_s3.py --date 2026-01-29 --bucket very-great-products-raw-us-east-1-dev
python scripts/upload_to_s3.py --date 2026-02-08 --bucket very-great-products-raw-us-east-1-dev
python scripts/upload_to_s3.py --date 2026-02-18 --bucket very-great-products-raw-us-east-1-dev
```

**Verificación:** En S3 deben aparecer rutas como `s3://very-great-products-raw-us-east-1-dev/landing/beauty-products/2026/02/18/beauty-products_20260218.csv`.

---

## Paso 3: Ejecutar ETL Glue

El ETL lee desde `s3://very-great-products-raw-us-east-1-dev/landing/beauty-products/` y escribe Parquet en `s3://very-great-products-processed-us-east-1-dev/curated/beauty-products/`.

```powershell
aws glue start-job-run --job-name beauty-products-etl-job
```

Anota el `JobRunId` del resultado y revisa el estado hasta que sea `SUCCEEDED`:

```powershell
aws glue get-job-run --job-name beauty-products-etl-job --run-id <JobRunId>
```

**Verificación:** En S3 deben existir carpetas como:
- `s3://very-great-products-processed-us-east-1-dev/curated/beauty-products/year=2026/month_num=1/`
- `s3://very-great-products-processed-us-east-1-dev/curated/beauty-products/year=2026/month_num=2/`

con archivos `.parquet` dentro. Si el job leyó 0 registros, revisa que los CSV estén en `landing/beauty-products/YYYY/MM/DD/` y que el formato de la columna Month sea válido (ej. `2/18/2026`).

---

## Paso 4: Ejecutar crawler de tabla curated

Para que Athena vea las particiones nuevas:

```powershell
aws glue start-crawler --name beauty-products-curated-crawler
aws glue get-crawler --name beauty-products-curated-crawler --query "Crawler.State"
```

Espera a que el crawler termine (state = READY).

**Verificación en Athena:**

```sql
SELECT DISTINCT year, month_num
FROM beauty_products_db.curated_beauty_products
ORDER BY year DESC, month_num DESC;
```

Deben aparecer las particiones cargadas (ej. 2026/2, 2026/1).

---

## Paso 5: Verificar categoría vacía (Eye & Ear Care)

En Athena:

```sql
SELECT l2_category, COUNT(*) AS cnt
FROM beauty_products_db.curated_beauty_products
WHERE LOWER(TRIM(l2_category)) = 'eye & ear care'
GROUP BY l2_category;
```

**Resultado esperado:** 0 filas (o `cnt = 0`). Así se valida que la categoría vacía no tiene registros.

---

## Paso 6: E2E LLM en categorías con datos

Ejecuta el test E2E para varias categorías que **sí** tienen datos (Skincare, Makeup, Haircare & Styling, etc.):

```powershell
cd c:\RevStar\very-great-llms-trends
python scripts/e2e-llm-report.py --category "Skincare"
python scripts/e2e-llm-report.py --category "Makeup"
python scripts/e2e-llm-report.py --category "Haircare & Styling"
python scripts/e2e-llm-report.py --category "Bath & Body Care"
```

O ejecuta el script multi-categoría (varias categorías + categoría vacía en un solo comando):

```powershell
python scripts/e2e-llm-multi-category.py
# Opcional: solo algunas categorías
python scripts/e2e-llm-multi-category.py --categories "Skincare" "Makeup" "Haircare & Styling"
```

**Resultado esperado:** Cada ejecución termina con `status=success`, reporte con `market_context`, `brand_proposal`, `product_ideas`, `pdf_url`.

---

## Paso 7: E2E en categoría vacía (mensaje sin registros)

Ejecuta el flujo para la categoría **Eye & Ear Care**:

```powershell
python scripts/e2e-llm-report.py --category "Eye & Ear Care"
```

**Resultado esperado:** El API debe devolver error o estado `failed` con mensaje **"Category not found in last 30 days"**. El front debe mostrar ese mensaje cuando no hay registros (sin generar reporte completo).

---

## Paso 8: CloudWatch – validación del éxito del proyecto

1. **Logs Lambda (orchestrator)**  
   - Log group: `/aws/lambda/beauty-products-llm-orchestrator-{env}`.  
   - Filtrar por `request_id` o por texto "Athena", "Brand proposal", "Product ideas", "PDF".  
   - Para categoría vacía: mensaje de "Category not found in last 30 days".

2. **Métricas custom**  
   - Namespace: `BeautyProducts/LLM`.  
   - Métricas: `TrendingReportRequests`, `TotalReportDuration`, `AthenaQueryDuration`, `BedrockCallDuration`, `PDFGenerationDuration`.  
   - Debe haber solicitudes exitosas para categorías con datos y comportamiento coherente para la categoría vacía (ej. menos tiempo si falla antes de Bedrock).

3. **Glue / ETL**  
   - Log group del job Glue y métricas de Glue para confirmar que el ETL corrió y procesó los archivos subidos.

4. **Athena**  
   - Queries ejecutadas desde la Lambda aparecen en el historial de Athena; se puede revisar duración y estado.

**Criterio de éxito:** Flujo completo (DL → ETL → Athena → LLM → PDF) funciona en varias categorías, la categoría vacía muestra el mensaje esperado y CloudWatch refleja las ejecuciones.

---

## Si algo no funciona (troubleshooting)

| Síntoma | Qué revisar |
|--------|----------------|
| Glue job leyó 0 registros | Los CSV deben estar en `s3://very-great-products-raw-us-east-1-dev/landing/beauty-products/YYYY/MM/DD/`. Comprueba con `aws s3 ls s3://very-great-products-raw-us-east-1-dev/landing/beauty-products/ --recursive`. La columna **Month** en el CSV debe ser fecha válida (ej. `2/18/2026`). |
| No aparecen particiones en curated | Espera a que el job Glue termine en estado `SUCCEEDED`. Luego lista: `aws s3 ls s3://very-great-products-processed-us-east-1-dev/curated/beauty-products/ --recursive` |
| Athena no ve datos | Ejecuta el crawler `beauty-products-curated-crawler` y espera a que el estado sea `READY`. En Athena usa workgroup `beauty-products-athena-dev` (o el de tu entorno). |
| LLM devuelve "Category not found in last 30 days" en todas las categorías | La tabla `beauty_products_db.curated_beauty_products` debe tener filas con `data_quality_score >= 0.95` y `l2_category` coincidente. Ejecuta en Athena: `SELECT l2_category, COUNT(*) FROM beauty_products_db.curated_beauty_products WHERE year = 2026 GROUP BY l2_category;` |
| upload_to_s3.py falla con "Directory not found" | Si usas `--date`, la carpeta `data/raw/YYYY/MM/DD/` debe existir. Mejor usa el comando `aws s3 sync` del Paso 2 (Opción A) después de generar con el script del Paso 1. |

---

## Checklist final

- [ ] Datos en raw S3 para al menos 2 fechas (últimos 30 días).
- [ ] ETL ejecutado; Parquet en curated con particiones correctas.
- [ ] Crawler curated ejecutado; particiones visibles en Athena.
- [ ] Categoría **Eye & Ear Care** sin registros (0 filas en Athena).
- [ ] E2E LLM exitoso en al menos 3 categorías con datos (ej. Skincare, Makeup, Haircare & Styling).
- [ ] E2E en “Eye & Ear Care” devuelve mensaje "Category not found in last 30 days" / error controlado.
- [ ] CloudWatch: logs y métricas coherentes con las pruebas.

Cuando todos los ítems están cumplidos, el E2E DL → LLM con CloudWatch en diferentes categorías y la categoría vacía se considera exitoso.
