"""
Beauty Products ETL Job
AWS Glue ETL script for transforming raw beauty products CSV data to curated Parquet
with comprehensive data quality checks aligned with DAMA-DMBOK principles.

Version: 1.0.0
"""

import sys
import hashlib
from datetime import datetime
from decimal import Decimal
import json
import re

from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.sql import DataFrame
from pyspark.sql.functions import (
    col, lit, current_timestamp, when, trim, regexp_replace,
    md5, concat_ws, row_number, udf, monotonically_increasing_id, 
    to_date, year, month, sum as _sum, count, avg, concat, lower, abs
)
from pyspark.sql.types import (
    StringType, DecimalType, IntegerType, LongType, 
    DateType, TimestampType, StructType, StructField
)
from pyspark.sql.window import Window
import boto3

# Initialize contexts
args = getResolvedOptions(sys.argv, [
    'JOB_NAME',
    'SOURCE_BUCKET',
    'CURATED_BUCKET',
    'METADATA_BUCKET',
    'DATABASE_NAME',
    'TRANSFORMATION_VERSION',
    'DQ_PASS_THRESHOLD',
    'DQ_WARN_THRESHOLD',
    'ANOMALY_REVENUE_MAX',
    'ANOMALY_ITEMS_MAX'
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

# Job parameters
SOURCE_BUCKET = args['SOURCE_BUCKET']
CURATED_BUCKET = args['CURATED_BUCKET']
METADATA_BUCKET = args['METADATA_BUCKET']
DATABASE_NAME = args['DATABASE_NAME']
TRANSFORMATION_VERSION = args['TRANSFORMATION_VERSION']
DQ_PASS_THRESHOLD = float(args['DQ_PASS_THRESHOLD'])
DQ_WARN_THRESHOLD = float(args['DQ_WARN_THRESHOLD'])
ANOMALY_REVENUE_MAX = float(args['ANOMALY_REVENUE_MAX'])
ANOMALY_ITEMS_MAX = int(args['ANOMALY_ITEMS_MAX'])

# Job run metadata
job_run_id = args['JOB_RUN_ID'] if 'JOB_RUN_ID' in args else datetime.utcnow().strftime('%Y%m%d_%H%M%S')
execution_timestamp = datetime.utcnow().isoformat() + 'Z'

print(f"Starting Beauty Products ETL Job")
print(f"Job Run ID: {job_run_id}")
print(f"Transformation Version: {TRANSFORMATION_VERSION}")


# ============================================================================
# TRANSFORMATION FUNCTIONS
# ============================================================================

def parse_date_field(date_str):
    """Parse date from various formats to ISO date string"""
    if date_str is None:
        return None
    
    # Convert to string if not already
    if not isinstance(date_str, str):
        date_str = str(date_str)
    
    date_str = date_str.strip()
    if not date_str:
        return None
    
    formats = ['%m/%d/%Y', '%m/%d/%y', '%Y-%m-%d', '%d/%m/%Y']
    
    for fmt in formats:
        try:
            from datetime import datetime
            parsed = datetime.strptime(date_str, fmt)
            return parsed.strftime('%Y-%m-%d')
        except:
            continue
    return None

def normalize_product_id(product_id_str):
    """Convert product ID from scientific notation to BIGINT"""
    if product_id_str is None:
        return None
    
    try:
        # If already an int, just validate and return
        if isinstance(product_id_str, int):
            if 0 <= product_id_str <= 9223372036854775807:
                return product_id_str
            return None
        
        # Handle string input
        if isinstance(product_id_str, str):
            cleaned = product_id_str.replace(',', '').strip()
            if not cleaned:
                return None
            as_float = float(cleaned)
            as_int = int(as_float)
            if 0 <= as_int <= 9223372036854775807:
                return as_int
        
        return None
    except:
        return None

def normalize_text_field(text_str, max_length=500):
    """Normalize text: trim, remove extra spaces, clean encoding"""
    if text_str is None:
        return None
    
    # Convert to string if not already
    if not isinstance(text_str, str):
        text_str = str(text_str)
    
    cleaned = text_str.strip()
    if not cleaned:
        return None
    
    # Replace multiple spaces with single space
    cleaned = ' '.join(cleaned.split())
    
    # Remove non-printable characters (keep basic punctuation)
    cleaned = ''.join(char for char in cleaned if ord(char) >= 32 or char in '\n\t')
    
    # Trim to max length
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length]
    
    return cleaned if cleaned else None

def parse_currency_field(currency_str):
    """Parse currency string to decimal"""
    if currency_str is None:
        return None
    
    try:
        # If already a number, just validate and return
        if isinstance(currency_str, (int, float)):
            value = float(currency_str)
            if 0 <= value <= 100000000:
                return round(value, 2)
            return None
        
        # Handle string input
        if isinstance(currency_str, str):
            cleaned = currency_str.strip()
            if not cleaned:
                return None
            
            # Remove currency symbols and commas
            cleaned = cleaned.replace('$', '').replace('€', '').replace('£', '')
            cleaned = cleaned.replace(',', '').strip()
            
            if not cleaned:
                return None
            
            value = float(cleaned)
            if 0 <= value <= 100000000:
                return round(value, 2)
        
        return None
    except:
        return None

def parse_percentage_field(pct_str):
    """Parse percentage string to decimal ratio"""
    if pct_str is None:
        return None
    
    try:
        # If already a number, assume it's already a ratio or percentage value
        if isinstance(pct_str, (int, float)):
            value = float(pct_str)
            # If value is between -1 and 10, assume it's already a ratio
            if -1 <= value <= 10:
                return round(value, 4)
            # Otherwise assume it's a percentage
            if -100 <= value <= 1000:
                return round(value / 100.0, 4)
            return None
        
        # Handle string input
        if isinstance(pct_str, str):
            cleaned = pct_str.strip()
            if not cleaned:
                return None
            
            # Handle Excel errors
            if cleaned.upper() in ['#DIV/0!', '#N/A', '#VALUE!', '#REF!', '#NAME?', '#NUM!', '#NULL!']:
                return None
            
            # Remove % symbol
            cleaned = cleaned.replace('%', '').strip()
            
            value = float(cleaned)
            if -100 <= value <= 1000:
                return round(value / 100.0, 4)
        
        return None
    except:
        return None

def parse_integer_field(int_str):
    """Parse integer string (with possible commas)"""
    if int_str is None:
        return None
    
    try:
        # If already an int, just validate and return
        if isinstance(int_str, int):
            if 0 <= int_str <= 10000000:
                return int_str
            return None
        
        # Handle string input
        if isinstance(int_str, str):
            cleaned = int_str.strip()
            if not cleaned:
                return None
            
            # Remove commas
            cleaned = cleaned.replace(',', '').strip()
            value = int(float(cleaned))  # Use float() first to handle decimals
            
            if 0 <= value <= 10000000:
                return value
        
        return None
    except:
        return None

# Register UDFs
parse_date_udf = udf(parse_date_field, StringType())
normalize_product_id_udf = udf(normalize_product_id, LongType())
normalize_text_udf = udf(normalize_text_field, StringType())
parse_currency_udf = udf(parse_currency_field, DecimalType(18, 2))
parse_percentage_udf = udf(parse_percentage_field, DecimalType(5, 4))
parse_integer_udf = udf(parse_integer_field, IntegerType())


# ============================================================================
# STEP 1: READ RAW DATA
# ============================================================================

print("=" * 80)
print("Step 1: Reading raw CSV data...")
print("=" * 80)

# Use recursive file lookup to find all CSV files in subdirectories
raw_path = f"s3://{SOURCE_BUCKET}/landing/beauty-products/"

print(f"SOURCE_BUCKET: {SOURCE_BUCKET}")
print(f"Reading from: {raw_path}")

# Read CSV with header and infer schema using recursiveFileLookup
try:
    df_raw = spark.read.format("csv") \
        .option("header", "true") \
        .option("inferSchema", "true") \
        .option("delimiter", ",") \
        .option("quote", '"') \
        .option("escape", '"') \
        .option("encoding", "UTF-8") \
        .option("mode", "PERMISSIVE") \
        .option("columnNameOfCorruptRecord", "_corrupt_record") \
        .option("recursiveFileLookup", "true") \
        .option("pathGlobFilter", "*.csv") \
        .load(raw_path)
    
    print("✓ CSV read operation completed")
except Exception as e:
    print(f"✗ FAILED to read CSV: {str(e)}")
    raise

# Add source metadata with actual file path
from pyspark.sql.functions import input_file_name, regexp_extract

df_raw = df_raw.withColumn("source_file", input_file_name()) \
    .withColumn("source_record_number", monotonically_increasing_id())

# Validate folder structure consistency (production quality check)
print("Validating folder structure consistency...")

# Extract date from folder path (YYYY/MM/DD pattern)
df_raw = df_raw.withColumn(
    "folder_year",
    regexp_extract(col("source_file"), r"/(\d{4})/\d{2}/\d{2}/", 1)
).withColumn(
    "folder_month",
    regexp_extract(col("source_file"), r"/\d{4}/(\d{2})/\d{2}/", 1)
).withColumn(
    "folder_day",
    regexp_extract(col("source_file"), r"/\d{4}/\d{2}/(\d{2})/", 1)
)

# Extract date from filename (beauty-products_YYYYMMDD.csv pattern)
df_raw = df_raw.withColumn(
    "filename_date",
    regexp_extract(col("source_file"), r"beauty-products_(\d{8})\.csv", 1)
)

# Check for inconsistencies (warn but don't block processing)
inconsistent_files = df_raw.filter(
    (col("filename_date") != "") & 
    (col("folder_year") != "") &
    (concat(col("folder_year"), col("folder_month"), col("folder_day")) != col("filename_date"))
).select("source_file", "folder_year", "folder_month", "folder_day", "filename_date").distinct()

inconsistent_count = inconsistent_files.count()
if inconsistent_count > 0:
    print(f"WARNING: Found {inconsistent_count} file(s) with date mismatch between folder and filename")
    print("Files will still be processed, but this may indicate organizational issues:")
    inconsistent_files.show(truncate=False)
else:
    print("[OK] All files have consistent folder/filename dates")

# Drop validation columns (not needed for processing)
df_raw = df_raw.drop("folder_year", "folder_month", "folder_day", "filename_date")

print("Counting records...")
try:
    total_records_read = df_raw.count()
    print(f"✓ Total records read: {total_records_read}")
    
    if total_records_read == 0:
        print("✗ WARNING: Zero records read!")
        print("Checking schema:")
        df_raw.printSchema()
        print("Checking if dataframe is empty:")
        print(f"Is empty: {df_raw.rdd.isEmpty()}")
except Exception as e:
    print(f"✗ FAILED to count records: {str(e)}")
    raise


# ============================================================================
# STEP 2: HANDLE CORRUPT RECORDS
# ============================================================================

print("Step 2: Handling corrupt records...")

if "_corrupt_record" in df_raw.columns:
    df_corrupt = df_raw.filter(col("_corrupt_record").isNotNull())
    corrupt_count = df_corrupt.count()
    
    if corrupt_count > 0:
        print(f"Found {corrupt_count} corrupt records, writing to error bucket...")
        
        df_corrupt_output = df_corrupt.select(
            lit("MALFORMED_CSV").alias("error_reason"),
            col("_corrupt_record").alias("raw_record"),
            current_timestamp().alias("error_timestamp")
        )
        
        error_path = f"s3://{CURATED_BUCKET}/error/beauty-products/{datetime.utcnow().strftime('%Y/%m/%d')}/"
        df_corrupt_output.write.mode("append").parquet(error_path)
    
    # Remove corrupt records from processing
    df_raw = df_raw.filter(col("_corrupt_record").isNull()).drop("_corrupt_record")


# ============================================================================
# STEP 3: APPLY TRANSFORMATIONS AND QUALITY SCORING
# ============================================================================

print("Step 3: Applying transformations and calculating quality scores...")

# Initialize quality score
df = df_raw.withColumn("data_quality_score", lit(1.0000)) \
    .withColumn("quality_flags", lit(""))

# Transform: Month (DATE)
df = df.withColumn("month_parsed", parse_date_udf(col("Month")))
df = df.withColumn("month", to_date(col("month_parsed"), "yyyy-MM-dd"))

# Quality check: Invalid date
df = df.withColumn("quality_flags", 
    when(col("month").isNull(), concat(col("quality_flags"), lit("INVALID_DATE,")))
    .otherwise(col("quality_flags")))
df = df.withColumn("data_quality_score",
    when(col("month").isNull(), col("data_quality_score") - 0.20)
    .otherwise(col("data_quality_score")))

# Transform: Product ID (BIGINT)
df = df.withColumn("product_id", normalize_product_id_udf(col("Product Id")))

# If product_id is null, generate synthetic ID
df = df.withColumn("product_id",
    when(col("product_id").isNull(), 
         abs(col("source_record_number")))
    .otherwise(col("product_id")))

df = df.withColumn("quality_flags",
    when(normalize_product_id_udf(col("Product Id")).isNull(), 
         concat(col("quality_flags"), lit("SYNTHETIC_PRODUCT_ID,")))
    .otherwise(col("quality_flags")))

df = df.withColumn("data_quality_score",
    when(normalize_product_id_udf(col("Product Id")).isNull(), 
         col("data_quality_score") - 0.15)
    .otherwise(col("data_quality_score")))

# Transform: Product Name (STRING)
df = df.withColumn("product_name", normalize_text_udf(col("Product Name")))

df = df.withColumn("quality_flags",
    when(col("product_name").isNull(), concat(col("quality_flags"), lit("MISSING_PRODUCT_NAME,")))
    .otherwise(col("quality_flags")))
df = df.withColumn("data_quality_score",
    when(col("product_name").isNull(), col("data_quality_score") - 0.20)
    .otherwise(col("data_quality_score")))

# Transform: Shop Name (STRING)
df = df.withColumn("shop_name", normalize_text_udf(col("Shop Name")))

# Transform: Categories (STRING)
df = df.withColumn("l1_category", 
    when(normalize_text_udf(col("L1 category")).isNull(), lit("Uncategorized"))
    .otherwise(normalize_text_udf(col("L1 category"))))

df = df.withColumn("l2_category", 
    when(normalize_text_udf(col("L2 category")).isNull(), lit("Uncategorized"))
    .otherwise(normalize_text_udf(col("L2 category"))))

df = df.withColumn("l3_category", 
    when(normalize_text_udf(col("L3 category")).isNull(), lit("Uncategorized"))
    .otherwise(normalize_text_udf(col("L3 category"))))

# Transform: Revenue (DECIMAL)
df = df.withColumn("revenue_usd", parse_currency_udf(col("Revenue")))

df = df.withColumn("revenue_usd",
    when(col("revenue_usd").isNull(), lit(0.00))
    .otherwise(col("revenue_usd")))

df = df.withColumn("quality_flags",
    when(parse_currency_udf(col("Revenue")).isNull(), 
         concat(col("quality_flags"), lit("INVALID_REVENUE,")))
    .otherwise(col("quality_flags")))

df = df.withColumn("data_quality_score",
    when(parse_currency_udf(col("Revenue")).isNull(), 
         col("data_quality_score") - 0.15)
    .otherwise(col("data_quality_score")))

# Transform: Avg Unit Price (DECIMAL)
df = df.withColumn("avg_unit_price_usd", parse_currency_udf(col("`Avg. Unit Price`")))

df = df.withColumn("avg_unit_price_usd",
    when(col("avg_unit_price_usd").isNull(), lit(0.00))
    .otherwise(col("avg_unit_price_usd")))

df = df.withColumn("quality_flags",
    when(parse_currency_udf(col("`Avg. Unit Price`")).isNull(), 
         concat(col("quality_flags"), lit("INVALID_AVG_PRICE,")))
    .otherwise(col("quality_flags")))

df = df.withColumn("data_quality_score",
    when(parse_currency_udf(col("`Avg. Unit Price`")).isNull(), 
         col("data_quality_score") - 0.10)
    .otherwise(col("data_quality_score")))

# Transform: Item Sold (INT)
df = df.withColumn("item_sold", parse_integer_udf(col("Item Sold")))

df = df.withColumn("item_sold",
    when(col("item_sold").isNull(), lit(0))
    .otherwise(col("item_sold")))

df = df.withColumn("quality_flags",
    when(parse_integer_udf(col("Item Sold")).isNull(), 
         concat(col("quality_flags"), lit("MISSING_ITEMS,")))
    .otherwise(col("quality_flags")))

df = df.withColumn("data_quality_score",
    when(parse_integer_udf(col("Item Sold")).isNull(), 
         col("data_quality_score") - 0.10)
    .otherwise(col("data_quality_score")))

# Transform: MoM Growth % (DECIMAL)
df = df.withColumn("mom_growth_pct", parse_percentage_udf(col("MoM Growth %")))

# Check for suspicious growth (>1000% or <-100%)
df = df.withColumn("quality_flags",
    when((col("mom_growth_pct") > 10.0) | (col("mom_growth_pct") < -1.0), 
         concat(col("quality_flags"), lit("SUSPICIOUS_GROWTH,")))
    .otherwise(col("quality_flags")))

df = df.withColumn("data_quality_score",
    when((col("mom_growth_pct") > 10.0) | (col("mom_growth_pct") < -1.0), 
         col("data_quality_score") - 0.05)
    .otherwise(col("data_quality_score")))

# Add governance metadata columns
df = df.withColumn("processed_timestamp", current_timestamp()) \
    .withColumn("transformation_version", lit(TRANSFORMATION_VERSION)) \
    .withColumn("created_by", lit("glue-job-beauty-products"))

# Calculate record hash for deduplication
df = df.withColumn("record_hash", 
    md5(concat_ws("||", 
        col("product_id"), 
        col("month"), 
        col("shop_name"), 
        col("product_name"),
        col("revenue_usd"))))

# Clean up quality_flags (remove trailing comma)
df = df.withColumn("quality_flags", 
    regexp_replace(col("quality_flags"), ",$", ""))

# Add partition columns
df = df.withColumn("year", year(col("month"))) \
    .withColumn("month_num", month(col("month")))

try:
    transform_count = df.count()
    print(f"✓ Transformations completed. Total records: {transform_count}")
except Exception as e:
    print(f"✗ FAILED during transformations: {str(e)}")
    raise


# ============================================================================
# STEP 4: DE-DUPLICATION
# ============================================================================

print("Step 4: De-duplicating records...")

# Define window for deduplication
window_spec = Window.partitionBy("product_id", "month", "shop_name").orderBy("source_record_number")

# Add row number
df = df.withColumn("row_num", row_number().over(window_spec))

# Separate duplicates
df_duplicates = df.filter(col("row_num") > 1)
duplicate_count = df_duplicates.count()
print(f"✓ Found {duplicate_count} duplicates")

if duplicate_count > 0:
    print(f"Found {duplicate_count} duplicate records, writing to error bucket...")
    
    df_duplicates_output = df_duplicates.select(
        lit("DUPLICATE_RECORD").alias("error_reason"),
        concat_ws(", ", 
            concat(lit("product_id="), col("product_id")),
            concat(lit("month="), col("month")),
            concat(lit("shop_name="), col("shop_name"))
        ).alias("raw_record"),
        current_timestamp().alias("error_timestamp")
    )
    
    error_path = f"s3://{CURATED_BUCKET}/error/beauty-products/{datetime.utcnow().strftime('%Y/%m/%d')}/"
    df_duplicates_output.write.mode("append").parquet(error_path)

# Keep only first occurrence
df = df.filter(col("row_num") == 1).drop("row_num")

dedup_count = df.count()
print(f"✓ After deduplication: {dedup_count} records")


# ============================================================================
# STEP 5: QUALITY-BASED ROUTING
# ============================================================================

print("=" * 80)
print("Step 5: Routing records based on quality scores...")
print("=" * 80)

# Split by quality score
df_passed = df.filter(col("data_quality_score") >= DQ_PASS_THRESHOLD)
df_warned = df.filter((col("data_quality_score") >= DQ_WARN_THRESHOLD) & 
                      (col("data_quality_score") < DQ_PASS_THRESHOLD))
df_failed = df.filter(col("data_quality_score") < DQ_WARN_THRESHOLD)

# Check for anomalies (extreme values)
df_anomalies = df.filter((col("revenue_usd") > ANOMALY_REVENUE_MAX) | 
                          (col("item_sold") > ANOMALY_ITEMS_MAX))

passed_count = df_passed.count()
warned_count = df_warned.count()
failed_count = df_failed.count()
anomaly_count = df_anomalies.count()

print(f"✓ Passed: {passed_count}, Warned: {warned_count}, Failed: {failed_count}, Anomalies: {anomaly_count}")

# Combine passed and warned for curated output
df_curated = df_passed.union(df_warned)

# Route failed records to quarantine
if failed_count > 0:
    quarantine_path = f"s3://{CURATED_BUCKET}/quarantine/beauty-products/{datetime.utcnow().strftime('%Y/%m/%d')}/"
    
    df_quarantine_output = df_failed.select(
        lit("LOW_QUALITY_SCORE").alias("quarantine_reason"),
        col("data_quality_score"),
        col("quality_flags"),
        col("product_id"),
        col("product_name"),
        col("month")
    )
    
    df_quarantine_output.write.mode("append").parquet(quarantine_path)
    print(f"Wrote {failed_count} failed records to quarantine")

# Route anomalies to quarantine
if anomaly_count > 0:
    anomaly_path = f"s3://{CURATED_BUCKET}/quarantine/beauty-products/{datetime.utcnow().strftime('%Y/%m/%d')}_anomalies/"
    
    df_anomaly_output = df_anomalies.select(
        lit("ANOMALY_DETECTED").alias("quarantine_reason"),
        col("data_quality_score"),
        col("revenue_usd"),
        col("item_sold"),
        col("product_id"),
        col("product_name")
    )
    
    df_anomaly_output.write.mode("append").parquet(anomaly_path)
    print(f"Wrote {anomaly_count} anomaly records to quarantine")


# ============================================================================
# STEP 6: WRITE CURATED DATA
# ============================================================================

print("=" * 80)
print("Step 6: Writing curated data to S3...")
print("=" * 80)

curated_path = f"s3://{CURATED_BUCKET}/curated/beauty-products/"

# Select final columns for curated table with explicit type casting
df_curated_final = df_curated.select(
    "month",
    "product_id",
    "product_name",
    "shop_name",
    "l1_category",
    "l2_category",
    "l3_category",
    "item_sold",
    col("revenue_usd").cast(DecimalType(18, 2)).alias("revenue_usd"),
    col("avg_unit_price_usd").cast(DecimalType(10, 2)).alias("avg_unit_price_usd"),
    col("mom_growth_pct").cast(DecimalType(5, 4)).alias("mom_growth_pct"),
    "source_file",
    "source_record_number",
    "processed_timestamp",
    "transformation_version",
    col("data_quality_score").cast(DecimalType(5, 4)).alias("data_quality_score"),
    "quality_flags",
    "created_by",
    "record_hash",
    "year",
    "month_num"
)

# Write as partitioned Parquet
df_curated_final.write \
    .mode("append") \
    .partitionBy("year", "month_num") \
    .parquet(curated_path, compression="snappy")

curated_count = df_curated_final.count()
print(f"✓ Wrote {curated_count} records to curated zone")


# ============================================================================
# STEP 7: GENERATE QUALITY REPORT
# ============================================================================

print("=" * 80)
print("Step 7: Generating data quality report...")
print("=" * 80)

# Calculate aggregate quality metrics
quality_stats = df.agg(
    avg("data_quality_score").alias("avg_quality_score"),
    count("*").alias("total_records")
).collect()[0]

# Count quality issues
quality_issues = {}
for flag in ["INVALID_DATE", "SYNTHETIC_PRODUCT_ID", "MISSING_PRODUCT_NAME", 
             "INVALID_REVENUE", "INVALID_AVG_PRICE", "MISSING_ITEMS", "SUSPICIOUS_GROWTH"]:
    issue_count = df.filter(col("quality_flags").contains(flag)).count()
    if issue_count > 0:
        quality_issues[flag] = issue_count

# Create quality report
quality_report = {
    "job_run_id": job_run_id,
    "execution_timestamp": execution_timestamp,
    "source_file": raw_path,
    "total_records": total_records_read,
    "records_passed": passed_count,
    "records_warned": warned_count,
    "records_failed": failed_count,
    "records_duplicates": duplicate_count,
    "records_anomalies": anomaly_count,
    "pass_rate": round(passed_count / total_records_read if total_records_read > 0 else 0, 4),
    "quality_issues": quality_issues,
    "avg_quality_score": round(float(quality_stats["avg_quality_score"]) if quality_stats["avg_quality_score"] is not None else 0.0, 4),
    "transformation_version": TRANSFORMATION_VERSION
}

# Write quality report as JSON
report_path = f"s3://{CURATED_BUCKET}/quality-reports/beauty-products/{datetime.utcnow().strftime('%Y/%m/%d')}/report_{job_run_id}.json"

s3_client = boto3.client('s3')
s3_client.put_object(
    Bucket=CURATED_BUCKET,
    Key=report_path.replace(f"s3://{CURATED_BUCKET}/", ""),
    Body=json.dumps(quality_report, indent=2),
    ContentType='application/json'
)

print(f"✓ Quality report written to {report_path}")
print(f"✓ Average quality score: {quality_report['avg_quality_score']}")

# Log alerts if quality degradation
if quality_report['avg_quality_score'] < 0.80:
    print("QUALITY_SCORE_LOW: Average quality score below 0.80 threshold")

error_rate = (failed_count + duplicate_count) / total_records_read if total_records_read > 0 else 0
if error_rate > 0.05:
    print(f"ERROR_RATE_HIGH: Error rate {error_rate:.2%} exceeds 5% threshold")


# ============================================================================
# STEP 8: WRITE LINEAGE METADATA
# ============================================================================

print("=" * 80)
print("Step 8: Writing lineage metadata...")
print("=" * 80)

lineage_data = [{
    "source_file_path": raw_path,
    "target_file_path": curated_path,
    "job_name": args['JOB_NAME'],
    "job_run_id": job_run_id,
    "transformation_timestamp": execution_timestamp,
    "records_in": total_records_read,
    "records_out": curated_count,
    "records_error": failed_count + duplicate_count
}]

df_lineage = spark.createDataFrame(lineage_data)

lineage_path = f"s3://{METADATA_BUCKET}/lineage/"
df_lineage.write.mode("append").parquet(lineage_path)

print(f"✓ Lineage metadata written to {lineage_path}")


# ============================================================================
# STEP 9: JOB COMPLETION
# ============================================================================

print("Step 9: Job completion and cleanup...")

# Log final metrics
print("="* 80)
print("JOB SUMMARY")
print("="* 80)
print(f"Total records read: {total_records_read}")
print(f"Records written to curated: {curated_count}")
print(f"Records failed (quarantine): {failed_count}")
print(f"Duplicate records: {duplicate_count}")
print(f"Anomaly records: {anomaly_count}")
print(f"Average quality score: {quality_report['avg_quality_score']}")
print(f"Pass rate: {quality_report['pass_rate']:.2%}")
print("="* 80)

job.commit()
print("Beauty Products ETL job completed successfully!")
