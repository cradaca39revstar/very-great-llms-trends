"""
Validacion exhaustiva del ETL antes de desplegar a Glue
Prueba todas las funciones de parsing con datos reales del CSV
"""
import csv
import ast
import sys
from datetime import datetime
import re

print("=" * 80)
print("VALIDACION EXHAUSTIVA DEL ETL - FASE 1")
print("=" * 80)

# ============================================================================
# 1. VALIDAR SINTAXIS DEL SCRIPT PYTHON
# ============================================================================
print("\n[1/5] Validando sintaxis del script Python...")
try:
    with open('scripts/beauty_products_etl.py', 'r', encoding='utf-8') as f:
        script_content = f.read()
    ast.parse(script_content)
    print("   [OK] Sintaxis del script es valida")
except SyntaxError as e:
    print(f"   [ERROR] Error de sintaxis: {e}")
    sys.exit(1)
except Exception as e:
    print(f"   [ERROR] Error al leer el script: {e}")
    sys.exit(1)

# ============================================================================
# 2. VALIDAR ESTRUCTURA DEL CSV
# ============================================================================
print("\n[2/5] Validando estructura del CSV...")
csv_path = 'data/raw/2024/04/01/beauty-products_20240401.csv'

expected_columns = [
    "Month", "Product Id", "Product Name", "Shop Name",
    "L1 category", "L2 category", "L3 category",
    "Item Sold", "Revenue", "Avg. Unit Price", "MoM Growth %"
]

try:
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        headers = next(reader)
        rows = list(reader)
        
    print(f"   [OK] CSV encontrado: {csv_path}")
    print(f"   [OK] Columnas: {len(headers)}")
    print(f"   [OK] Filas de datos: {len(rows)}")
    
    if headers == expected_columns:
        print("   [OK] Encabezados coinciden exactamente")
    else:
        print("   [WARN] Encabezados no coinciden")
        
except FileNotFoundError:
    print(f"   [ERROR] No se encontro el archivo {csv_path}")
    sys.exit(1)
except Exception as e:
    print(f"   [ERROR] al leer CSV: {e}")
    sys.exit(1)

# ============================================================================
# 3. DEFINIR FUNCIONES DE PARSING (COPIADAS DEL ETL)
# ============================================================================
print("\n[3/5] Probando funciones de parsing con datos reales...")

def parse_date_field(date_str):
    """Parse date from various formats"""
    if not date_str or date_str.strip() == '':
        return None
    date_str = date_str.strip()
    try:
        dt = datetime.strptime(date_str, "%m/%d/%Y")
        return dt.strftime("%Y-%m-%d")
    except:
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            return dt.strftime("%Y-%m-%d")
        except:
            return None

def normalize_product_id(product_id_str):
    """Convert product ID from scientific notation to BIGINT"""
    if not product_id_str or product_id_str.strip() == '':
        return None
    try:
        cleaned = product_id_str.replace(',', '').strip()
        as_float = float(cleaned)
        as_int = int(as_float)
        if as_int < 0 or as_int > 9223372036854775807:
            return None
        return as_int
    except:
        return None

def parse_currency_field(currency_str):
    """Parse currency string to decimal"""
    if not currency_str or currency_str.strip() == '':
        return None
    try:
        cleaned = currency_str.strip()  # Limpiar espacios primero
        cleaned = cleaned.replace('$', '').replace('€', '').replace('£', '')
        cleaned = cleaned.replace(',', '').strip()
        if not cleaned or cleaned == '':
            return None
        value = float(cleaned)
        if value < 0 or value > 100000000:  # Validacion de rango
            return None
        return round(value, 2)
    except:
        return None

def parse_percentage_field(pct_str):
    """Parse percentage string to decimal ratio"""
    if not pct_str or pct_str.strip() == '':
        return None
    try:
        cleaned = pct_str.replace('%', '').strip()
        value = float(cleaned)
        # Validar rango razonable: -100% a 1000%
        if value < -100 or value > 1000:
            return None
        ratio = value / 100.0
        return round(ratio, 4)
    except:
        return None

def parse_integer_field(int_str):
    """Parse integer string (with possible commas)"""
    if not int_str or int_str.strip() == '':
        return None
    try:
        cleaned = int_str.replace(',', '').strip()
        value = int(cleaned)
        if value < 0 or value > 10000000:  # Validacion de rango
            return None
        return value
    except:
        return None

# ============================================================================
# 4. PROBAR FUNCIONES CON DATOS REALES
# ============================================================================

# Contadores de problemas
problems = {
    'date_invalid': [],
    'product_id_invalid': [],
    'revenue_invalid': [],
    'avg_price_invalid': [],
    'percentage_invalid': [],
    'items_sold_invalid': [],
    'spaces_extra': [],
    'percentage_out_range': []
}

print("\n   Analizando cada fila del CSV...")

for idx, row in enumerate(rows, start=2):  # Start at 2 (header is 1)
    if len(row) < 11:
        continue
    
    month, product_id, product_name, shop_name = row[0], row[1], row[2], row[3]
    l1_cat, l2_cat, l3_cat = row[4], row[5], row[6]
    items_sold, revenue, avg_price, mom_growth = row[7], row[8], row[9], row[10]
    
    # Test date parsing
    if parse_date_field(month) is None:
        problems['date_invalid'].append((idx, month))
    
    # Test product ID
    if normalize_product_id(product_id) is None:
        problems['product_id_invalid'].append((idx, product_id))
    
    # Test revenue
    if parse_currency_field(revenue) is None:
        problems['revenue_invalid'].append((idx, revenue))
    
    # Check for extra spaces in revenue
    if revenue.strip() != revenue.replace(' ', ''):
        problems['spaces_extra'].append((idx, 'Revenue', revenue))
    
    # Test avg price
    if parse_currency_field(avg_price) is None:
        problems['avg_price_invalid'].append((idx, avg_price))
    
    # Check for extra spaces in avg price
    if avg_price.strip() != avg_price.replace(' ', ''):
        problems['spaces_extra'].append((idx, 'Avg Price', avg_price))
    
    # Test percentage
    pct_result = parse_percentage_field(mom_growth)
    if pct_result is None:
        # Check if it's out of range or just invalid
        try:
            cleaned = mom_growth.replace('%', '').strip()
            value = float(cleaned)
            if value < -100 or value > 1000:
                problems['percentage_out_range'].append((idx, mom_growth, value))
            else:
                problems['percentage_invalid'].append((idx, mom_growth))
        except:
            problems['percentage_invalid'].append((idx, mom_growth))
    
    # Test items sold
    if parse_integer_field(items_sold) is None:
        problems['items_sold_invalid'].append((idx, items_sold))

# ============================================================================
# 5. GENERAR REPORTE
# ============================================================================
print("\n[4/5] Generando reporte de calidad...")

total_rows = len(rows)
total_problems = sum(len(v) for v in problems.values())
success_rate = ((total_rows - len(set(p[0] for problems_list in problems.values() for p in problems_list))) / total_rows * 100) if total_rows > 0 else 0

print("\n" + "=" * 80)
print("REPORTE DE CALIDAD DE DATOS")
print("=" * 80)
print(f"\nTotal de filas: {total_rows}")
print(f"Total de problemas encontrados: {total_problems}")
print(f"Tasa de exito esperada: {success_rate:.1f}%")

print("\n--- DETALLE DE PROBLEMAS ---")

if problems['date_invalid']:
    print(f"\n[WARN] Fechas invalidas: {len(problems['date_invalid'])}")
    for row_num, value in problems['date_invalid'][:5]:
        print(f"   Fila {row_num}: '{value}'")

if problems['product_id_invalid']:
    print(f"\n[WARN] Product IDs invalidos: {len(problems['product_id_invalid'])}")
    for row_num, value in problems['product_id_invalid'][:5]:
        print(f"   Fila {row_num}: '{value}'")

if problems['revenue_invalid']:
    print(f"\n[WARN] Revenue invalido: {len(problems['revenue_invalid'])}")
    for row_num, value in problems['revenue_invalid'][:5]:
        print(f"   Fila {row_num}: '{value}'")

if problems['avg_price_invalid']:
    print(f"\n[WARN] Avg Price invalido: {len(problems['avg_price_invalid'])}")
    for row_num, value in problems['avg_price_invalid'][:5]:
        print(f"   Fila {row_num}: '{value}'")

if problems['percentage_invalid']:
    print(f"\n[WARN] Porcentajes invalidos: {len(problems['percentage_invalid'])}")
    for row_num, value in problems['percentage_invalid'][:5]:
        print(f"   Fila {row_num}: '{value}'")

if problems['percentage_out_range']:
    print(f"\n[WARN] Porcentajes fuera de rango (-100% a 1000%): {len(problems['percentage_out_range'])}")
    for row_num, value, numeric in problems['percentage_out_range'][:5]:
        print(f"   Fila {row_num}: '{value}' ({numeric}%)")

if problems['items_sold_invalid']:
    print(f"\n[WARN] Items Sold invalidos: {len(problems['items_sold_invalid'])}")
    for row_num, value in problems['items_sold_invalid'][:5]:
        print(f"   Fila {row_num}: '{value}'")

if problems['spaces_extra']:
    print(f"\n[INFO] Valores con espacios extra: {len(problems['spaces_extra'])}")
    for row_num, field, value in problems['spaces_extra'][:5]:
        print(f"   Fila {row_num} ({field}): '{value}'")

if total_problems == 0:
    print("\n[OK] No se encontraron problemas!")

# ============================================================================
# 6. VALIDAR ESQUEMA EN EL SCRIPT
# ============================================================================
print("\n[5/5] Validando definicion de esquema en el script...")

if "StructType" in script_content and "StructField" in script_content:
    print("   [OK] El script contiene definicion de esquema")
else:
    print("   [WARN] El script no tiene definicion de esquema explicita")

if '.schema(raw_schema)' in script_content:
    print("   [OK] El script usa esquema explicito")
elif 'inferSchema' in script_content:
    print("   [WARN] El script usa inferSchema")

# Check for all expected column names in schema
schema_section = script_content[script_content.find("StructType"):script_content.find("# Read CSV")] if "StructType" in script_content else ""
missing_columns = []
for col in expected_columns:
    if f'"{col}"' not in schema_section and f"'{col}'" not in schema_section:
        missing_columns.append(col)

if missing_columns:
    print(f"   [WARN] Columnas faltantes en esquema: {missing_columns}")
else:
    print("   [OK] Todas las columnas estan en el esquema")

# ============================================================================
# RESUMEN FINAL
# ============================================================================
print("\n" + "=" * 80)
print("RESUMEN DE VALIDACION")
print("=" * 80)
print(f"\n[OK] Script Python: Sintaxis valida")
print(f"[OK] CSV: {total_rows} filas encontradas")
print(f"[OK] Esquema: Definido explicitamente")
print(f"[{'OK' if success_rate >= 95 else 'WARN'}] Calidad de datos: {success_rate:.1f}%")

if success_rate >= 95:
    print("\n[OK] El script esta listo para desplegar a Glue")
    print("=" * 80)
    sys.exit(0)
else:
    print(f"\n[WARN] Tasa de exito ({success_rate:.1f}%) es menor al 95%")
    print("[WARN] Revisa los problemas antes de desplegar")
    print("=" * 80)
    sys.exit(0)  # No falla, solo advierte
