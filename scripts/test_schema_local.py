"""
Test script to validate CSV schema locally before deploying to Glue
"""
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType

# Initialize Spark session
spark = SparkSession.builder \
    .appName("LocalSchemaTest") \
    .master("local[*]") \
    .getOrCreate()

# Define the same schema as in the ETL script
raw_schema = StructType([
    StructField("Month", StringType(), True),
    StructField("Product Id", StringType(), True),
    StructField("Product Name", StringType(), True),
    StructField("Shop Name", StringType(), True),
    StructField("L1 category", StringType(), True),
    StructField("L2 category", StringType(), True),
    StructField("L3 category", StringType(), True),
    StructField("Item Sold", StringType(), True),
    StructField("Revenue", StringType(), True),
    StructField("Avg. Unit Price", StringType(), True),
    StructField("MoM Growth %", StringType(), True)
])

# Read the CSV file
csv_path = "data/raw/2024/04/01/beauty-products_20240401.csv"

print(f"Reading CSV from: {csv_path}")
print("=" * 80)

try:
    df = spark.read.format("csv") \
        .option("header", "true") \
        .schema(raw_schema) \
        .option("delimiter", ",") \
        .option("quote", '"') \
        .option("escape", '"') \
        .option("encoding", "UTF-8") \
        .option("mode", "PERMISSIVE") \
        .option("columnNameOfCorruptRecord", "_corrupt_record") \
        .option("multiLine", "true") \
        .option("ignoreLeadingWhiteSpace", "true") \
        .option("ignoreTrailingWhiteSpace", "true") \
        .load(csv_path)
    
    print("✓ CSV loaded successfully!")
    print(f"✓ Total rows: {df.count()}")
    print(f"✓ Total columns: {len(df.columns)}")
    print("\nSchema:")
    df.printSchema()
    
    print("\nFirst 5 rows:")
    df.show(5, truncate=False)
    
    print("\nColumn names:")
    for col in df.columns:
        print(f"  - {col}")
    
    # Check for corrupt records
    if "_corrupt_record" in df.columns:
        corrupt_count = df.filter(df["_corrupt_record"].isNotNull()).count()
        if corrupt_count > 0:
            print(f"\n⚠ WARNING: Found {corrupt_count} corrupt records")
            df.filter(df["_corrupt_record"].isNotNull()).show(truncate=False)
        else:
            print("\n✓ No corrupt records found")
    
    print("\n" + "=" * 80)
    print("✓ VALIDATION PASSED - Schema works correctly with the CSV file")
    print("=" * 80)
    
except Exception as e:
    print(f"\n✗ ERROR: {str(e)}")
    print("=" * 80)
    print("✗ VALIDATION FAILED")
    print("=" * 80)
    import traceback
    traceback.print_exc()

finally:
    spark.stop()
