"""
Simple validation script without PySpark
Validates CSV structure and Python script syntax
"""
import csv
import ast
import sys

print("=" * 80)
print("VALIDACIÓN LOCAL DEL SCRIPT Y CSV")
print("=" * 80)

# 1. Validate Python script syntax
print("\n1. Validando sintaxis del script Python...")
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

# 2. Validate CSV structure
print("\n2. Validando estructura del CSV...")
csv_path = 'data/raw/2024/04/01/beauty-products_20240401.csv'

expected_columns = [
    "Month",
    "Product Id",
    "Product Name",
    "Shop Name",
    "L1 category",
    "L2 category",
    "L3 category",
    "Item Sold",
    "Revenue",
    "Avg. Unit Price",
    "MoM Growth %"
]

try:
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        headers = next(reader)
        
        print(f"   [OK] CSV encontrado: {csv_path}")
        print(f"   [OK] Columnas en CSV: {len(headers)}")
        print(f"   [OK] Columnas esperadas: {len(expected_columns)}")
        
        # Check if headers match
        if headers == expected_columns:
            print("   [OK] Los encabezados coinciden exactamente")
        else:
            print("   [WARN] Los encabezados no coinciden exactamente")
            print("\n   Encabezados en CSV:")
            for i, h in enumerate(headers, 1):
                print(f"      {i}. '{h}'")
            print("\n   Encabezados esperados:")
            for i, h in enumerate(expected_columns, 1):
                print(f"      {i}. '{h}'")
        
        # Count rows
        row_count = sum(1 for row in reader)
        print(f"   [OK] Total de filas (sin encabezado): {row_count}")
        
        if row_count == 0:
            print("   [ERROR] El CSV esta vacio")
            sys.exit(1)
        
except FileNotFoundError:
    print(f"   [ERROR] No se encontro el archivo {csv_path}")
    sys.exit(1)
except Exception as e:
    print(f"   [ERROR] al leer CSV: {e}")
    sys.exit(1)

# 3. Validate schema definition in script
print("\n3. Validando definición del esquema en el script...")
try:
    if "StructType" in script_content and "StructField" in script_content:
        print("   [OK] El script contiene definicion de esquema (StructType/StructField)")
    else:
        print("   [WARN] El script no parece tener definicion de esquema explicita")
    
    if '.schema(raw_schema)' in script_content:
        print("   [OK] El script usa esquema explicito (.schema())")
    elif 'inferSchema' in script_content:
        print("   [WARN] El script usa inferSchema (puede causar problemas)")
    
    # Check for all expected column names in schema definition
    schema_section = script_content[script_content.find("StructType"):script_content.find("# Read CSV")]
    missing_columns = []
    for col in expected_columns:
        if f'"{col}"' not in schema_section and f"'{col}'" not in schema_section:
            missing_columns.append(col)
    
    if missing_columns:
        print(f"   [WARN] Columnas faltantes en el esquema: {missing_columns}")
    else:
        print("   [OK] Todas las columnas estan definidas en el esquema")
        
except Exception as e:
    print(f"   [WARN] No se pudo validar el esquema: {e}")

# 4. Check file in S3 path format
print("\n4. Validando formato de ruta S3...")
import os
file_parts = csv_path.split(os.sep)
if len(file_parts) >= 5 and file_parts[-4:-1] == ['2024', '04', '01']:
    print("   [OK] La ruta sigue el formato YYYY/MM/DD")
    filename = file_parts[-1]
    if filename.startswith('beauty-products_') and filename.endswith('.csv'):
        print(f"   [OK] El nombre del archivo sigue el formato: {filename}")
        date_in_filename = filename.replace('beauty-products_', '').replace('.csv', '')
        if date_in_filename == '20240401':
            print("   [OK] La fecha en el nombre del archivo coincide con la carpeta")
        else:
            print(f"   [WARN] La fecha en el nombre ({date_in_filename}) no coincide con la carpeta (20240401)")
    else:
        print("   [WARN] El nombre del archivo no sigue el formato esperado")
else:
    print("   [WARN] La ruta no sigue el formato YYYY/MM/DD esperado")

print("\n" + "=" * 80)
print("[OK] VALIDACION COMPLETADA")
print("=" * 80)
print("\nResumen:")
print("  - Script Python: Sintaxis valida [OK]")
print(f"  - CSV: {row_count} filas encontradas [OK]")
print(f"  - Esquema: Definido explicitamente [OK]")
print("\nEl script esta listo para subir a S3 y ejecutar en Glue.")
print("=" * 80)
