"""
Beauty Products ETL Job
AWS Glue ETL script for transforming raw beauty products CSV data to curated Parquet
with comprehensive data quality checks aligned with DAMA-DMBOK principles.

Version: 1.1.0
Changelog:
    - v1.1.0: Added structured JSON logging for CloudWatch Logs Insights
    - v1.1.0: Added S3 audit trail for data change traceability
    - v1.1.0: Added CloudWatch custom metrics
    - v1.1.0: Adapted logging from rulescore.mdc standards for Glue environment

Logging Patterns (adapted from rulescore.mdc):
    - set_job_context() -> equivalent to @log_handler initialization
    - log_info/log_warning/log_error -> structured logging functions
    - log_data_change() -> data change traceability
    - get_job_run_id() -> equivalent to get_log_request_id()
"""

import sys
import time
from datetime import datetime
import json

from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.sql.functions import (
    col, lit, current_timestamp, when, regexp_replace,
    md5, concat_ws, row_number, udf, monotonically_increasing_id, 
    to_date, year, month, count, avg, concat, abs,
    input_file_name, regexp_extract
)
from pyspark.sql.types import (
    StringType, DecimalType, IntegerType, LongType, DoubleType,
    StructType, StructField
)
from pyspark.sql.window import Window
import boto3

# =============================================================================
# STRUCTURED LOGGING IMPORTS
# Adapted from rulescore.mdc for AWS Glue environment
# =============================================================================

# Import logging utilities (inline for Glue compatibility)
# These would normally be imported from scripts.utils.glue_logger
# but Glue requires all code in a single script or S3-referenced modules

import logging
import traceback
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, TypeVar

# Configure logging for CloudWatch (JSON format)
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("beauty_products_etl")
logger.setLevel(logging.INFO)

# Global job context (adapted from rulescore.mdc request_id pattern)
_job_context: Dict[str, Any] = {
    "job_run_id": None,
    "execution_timestamp": None,
    "job_name": None,
    "environment": None,
    "transformation_version": None,
}


def set_job_context(
    job_run_id: str,
    execution_timestamp: str,
    job_name: Optional[str] = None,
    environment: Optional[str] = None,
    transformation_version: Optional[str] = None,
) -> None:
    """Set global job context for request correlation (adapted from @log_handler)."""
    global _job_context
    _job_context = {
        "job_run_id": job_run_id,
        "execution_timestamp": execution_timestamp,
        "job_name": job_name,
        "environment": environment,
        "transformation_version": transformation_version,
    }


def get_job_run_id() -> str:
    """Get current job run ID (adapted from get_log_request_id)."""
    return _job_context.get("job_run_id") or "unknown"


def log_structured(
    level: str,
    message: str,
    domain: str = "beauty-products-etl",
    event_type: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    error: Optional[Exception] = None,
) -> Dict[str, Any]:
    """Log structured JSON message to CloudWatch."""
    timestamp = datetime.utcnow().isoformat() + "Z"
    log_entry: Dict[str, Any] = {
        "timestamp": timestamp,
        "level": level.upper(),
        "domain": domain,
        "job_run_id": get_job_run_id(),
        "request_id": get_job_run_id(),
        "message": message,
    }
    if event_type:
        log_entry["event_type"] = event_type
    if _job_context.get("job_name"):
        log_entry["job_name"] = _job_context["job_name"]
    if _job_context.get("environment"):
        log_entry["environment"] = _job_context["environment"]
    if _job_context.get("transformation_version"):
        log_entry["transformation_version"] = _job_context["transformation_version"]
    if details:
        log_entry["details"] = details
    if error:
        log_entry["error"] = {
            "type": type(error).__name__,
            "message": str(error),
            "traceback": traceback.format_exc(),
        }
    log_level = getattr(logging, level.upper(), logging.INFO)
    logger.log(log_level, json.dumps(log_entry, default=str))
    return log_entry


def log_info(message: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Log informational message."""
    return log_structured(level="INFO", message=message, details=details)


def log_warning(message: str, details: Optional[Dict[str, Any]] = None, event_type: str = "WARNING") -> Dict[str, Any]:
    """Log warning message."""
    return log_structured(level="WARNING", message=message, event_type=event_type, details=details)


def log_error(message: str, error: Optional[Exception] = None, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Log error with full context."""
    return log_structured(level="ERROR", message=message, event_type="ERROR", details=context, error=error)


def log_data_change(
    change_type: str,
    table_name: Optional[str] = None,
    operation: Optional[str] = None,
    record_count: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Log data changes for traceability (implements user story requirement)."""
    details: Dict[str, Any] = {
        "change_type": change_type,
        "table_name": table_name,
        "operation": operation,
    }
    if record_count is not None:
        details["record_count"] = record_count
    if metadata:
        details["metadata"] = metadata
    return log_structured(
        level="INFO",
        message=f"Data change: {change_type} on {table_name or 'unknown'}",
        event_type="DATA_CHANGE",
        details=details,
    )


def log_step(step_number: int, step_name: str, status: str = "started") -> Dict[str, Any]:
    """Log ETL step progress."""
    return log_structured(
        level="INFO",
        message=f"Step {step_number}: {step_name} - {status}",
        event_type="ETL_STEP",
        details={"step_number": step_number, "step_name": step_name, "status": status},
    )


def log_quality_alert(alert_type: str, threshold: float, actual_value: float, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Log data quality alert."""
    alert_details = {"alert_type": alert_type, "threshold": threshold, "actual_value": actual_value}
    if details:
        alert_details.update(details)
    return log_structured(
        level="WARNING",
        message=f"{alert_type}: Value {actual_value} breached threshold {threshold}",
        event_type="QUALITY_ALERT",
        details=alert_details,
    )


def log_job_summary(
    total_records: int,
    records_passed: int,
    records_warned: int,
    records_failed: int,
    records_duplicates: int,
    records_anomalies: int,
    avg_quality_score: float,
    pass_rate: float,
    duration_seconds: Optional[float] = None,
) -> Dict[str, Any]:
    """Log job summary at completion."""
    return log_structured(
        level="INFO",
        message="Job completed successfully",
        event_type="JOB_SUMMARY",
        details={
            "total_records": total_records,
            "records_passed": records_passed,
            "records_warned": records_warned,
            "records_failed": records_failed,
            "records_duplicates": records_duplicates,
            "records_anomalies": records_anomalies,
            "avg_quality_score": avg_quality_score,
            "pass_rate": pass_rate,
            "duration_seconds": duration_seconds,
        },
    )


def write_audit_log_to_s3(
    s3_client: Any,
    bucket: str,
    change_type: str,
    table_name: Optional[str] = None,
    operation: Optional[str] = None,
    record_count: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """Write audit log entry to S3 for traceability."""
    timestamp = datetime.utcnow()
    audit_entry: Dict[str, Any] = {
        "timestamp": timestamp.isoformat() + "Z",
        "job_run_id": get_job_run_id(),
        "request_id": get_job_run_id(),
        "change_type": change_type,
        "table_name": table_name,
        "operation": operation,
        "record_count": record_count,
        "metadata": metadata or {},
    }
    date_prefix = timestamp.strftime("%Y/%m/%d")
    time_suffix = timestamp.strftime("%H%M%S_%f")
    s3_key = f"audit-logs/beauty-products/{date_prefix}/{get_job_run_id()}_{time_suffix}_{change_type}.json"
    try:
        s3_client.put_object(
            Bucket=bucket,
            Key=s3_key,
            Body=json.dumps(audit_entry, indent=2, default=str),
            ContentType="application/json",
            ServerSideEncryption="AES256",
        )
        log_info(f"Audit log written to S3", details={"s3_key": s3_key, "change_type": change_type})
        return s3_key
    except Exception as e:
        log_error(f"Failed to write audit log to S3", error=e, context={"bucket": bucket, "s3_key": s3_key})
        return None


def write_etl_audit_summary(
    s3_client: Any,
    bucket: str,
    source_path: str,
    target_path: str,
    total_records_in: int,
    total_records_out: int,
    records_passed: int,
    records_warned: int,
    records_failed: int,
    records_duplicates: int,
    records_anomalies: int,
    avg_quality_score: float,
    pass_rate: float,
    quality_issues: Optional[Dict[str, int]] = None,
    duration_seconds: Optional[float] = None,
) -> Optional[str]:
    """Write comprehensive ETL audit summary to S3."""
    timestamp = datetime.utcnow()
    summary: Dict[str, Any] = {
        "timestamp": timestamp.isoformat() + "Z",
        "job_run_id": get_job_run_id(),
        "request_id": get_job_run_id(),
        "log_type": "ETL_AUDIT_SUMMARY",
        "source": {"path": source_path, "records_count": total_records_in},
        "target": {"path": target_path, "records_count": total_records_out},
        "quality_metrics": {
            "records_passed": records_passed,
            "records_warned": records_warned,
            "records_failed": records_failed,
            "records_duplicates": records_duplicates,
            "records_anomalies": records_anomalies,
            "avg_quality_score": avg_quality_score,
            "pass_rate": pass_rate,
        },
        "data_changes": [],
        "duration_seconds": duration_seconds,
    }
    # Add data change entries
    if records_passed + records_warned > 0:
        summary["data_changes"].append({
            "change_type": "INSERT",
            "table_name": "curated_beauty_products",
            "operation": "BATCH_INSERT",
            "record_count": records_passed + records_warned,
        })
    if records_failed > 0:
        summary["data_changes"].append({
            "change_type": "INSERT",
            "table_name": "quarantine_beauty_products",
            "operation": "BATCH_INSERT",
            "record_count": records_failed,
        })
    if records_duplicates > 0:
        summary["data_changes"].append({
            "change_type": "INSERT",
            "table_name": "error_beauty_products",
            "operation": "BATCH_INSERT",
            "record_count": records_duplicates,
        })
    if quality_issues:
        summary["quality_issues"] = quality_issues
    date_prefix = timestamp.strftime("%Y/%m/%d")
    s3_key = f"audit-logs/beauty-products/{date_prefix}/{get_job_run_id()}_ETL_SUMMARY.json"
    try:
        s3_client.put_object(
            Bucket=bucket,
            Key=s3_key,
            Body=json.dumps(summary, indent=2, default=str),
            ContentType="application/json",
            ServerSideEncryption="AES256",
        )
        log_info("ETL audit summary written to S3", details={"s3_key": s3_key})
        return s3_key
    except Exception as e:
        log_error("Failed to write ETL audit summary to S3", error=e, context={"bucket": bucket})
        return None


def put_data_quality_metrics(
    cloudwatch_client: Any,
    avg_quality_score: float,
    pass_rate: float,
    records_passed: int,
    records_warned: int,
    records_failed: int,
    records_duplicates: int,
    job_name: str,
) -> bool:
    """Put data quality metrics to CloudWatch."""
    timestamp = datetime.utcnow()
    dimensions = [{"Name": "JobName", "Value": job_name}]
    total_records = records_passed + records_warned + records_failed + records_duplicates
    error_rate = (records_failed + records_duplicates) / max(total_records, 1) * 100
    metric_data = [
        {"MetricName": "AvgQualityScore", "Value": avg_quality_score, "Unit": "None", "Timestamp": timestamp, "Dimensions": dimensions},
        {"MetricName": "PassRate", "Value": pass_rate * 100, "Unit": "Percent", "Timestamp": timestamp, "Dimensions": dimensions},
        {"MetricName": "RecordsPassed", "Value": records_passed, "Unit": "Count", "Timestamp": timestamp, "Dimensions": dimensions},
        {"MetricName": "RecordsWarned", "Value": records_warned, "Unit": "Count", "Timestamp": timestamp, "Dimensions": dimensions},
        {"MetricName": "RecordsFailed", "Value": records_failed, "Unit": "Count", "Timestamp": timestamp, "Dimensions": dimensions},
        {"MetricName": "RecordsDuplicates", "Value": records_duplicates, "Unit": "Count", "Timestamp": timestamp, "Dimensions": dimensions},
        {"MetricName": "ErrorRate", "Value": error_rate, "Unit": "Percent", "Timestamp": timestamp, "Dimensions": dimensions},
    ]
    try:
        cloudwatch_client.put_metric_data(Namespace="BeautyProducts/DataQuality", MetricData=metric_data)
        log_info("Data quality metrics published to CloudWatch", details={"metrics_count": len(metric_data)})
        return True
    except Exception as e:
        log_error("Failed to publish data quality metrics", error=e)
        return False


# =============================================================================
# INITIALIZE GLUE CONTEXT
# =============================================================================

# Start job timer
job_start_time = time.time()

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

# Initialize job context for structured logging (adapted from @log_handler)
set_job_context(
    job_run_id=job_run_id,
    execution_timestamp=execution_timestamp,
    job_name=args['JOB_NAME'],
    environment="poc",  # Can be parameterized
    transformation_version=TRANSFORMATION_VERSION,
)

# Log job initialization
log_info(
    "Beauty Products ETL Job started",
    details={
        "job_name": args['JOB_NAME'],
        "job_run_id": job_run_id,
        "transformation_version": TRANSFORMATION_VERSION,
        "source_bucket": SOURCE_BUCKET,
        "curated_bucket": CURATED_BUCKET,
        "metadata_bucket": METADATA_BUCKET,
        "dq_pass_threshold": DQ_PASS_THRESHOLD,
        "dq_warn_threshold": DQ_WARN_THRESHOLD,
    }
)

# Initialize S3 and CloudWatch clients for audit logging and metrics
s3_client = boto3.client('s3')
cloudwatch_client = boto3.client('cloudwatch')


# =============================================================================
# TRANSFORMATION FUNCTIONS
# =============================================================================

def parse_date_field(date_str):
    """Parse date from various formats to ISO date string"""
    if date_str is None:
        return None
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
        if isinstance(product_id_str, int):
            if 0 <= product_id_str <= 9223372036854775807:
                return product_id_str
            return None
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
    if not isinstance(text_str, str):
        text_str = str(text_str)
    cleaned = text_str.strip()
    if not cleaned:
        return None
    cleaned = ' '.join(cleaned.split())
    cleaned = ''.join(char for char in cleaned if ord(char) >= 32 or char in '\n\t')
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length]
    return cleaned if cleaned else None


def parse_currency_field(currency_str):
    """Parse currency string to decimal"""
    if currency_str is None:
        return None
    try:
        if isinstance(currency_str, (int, float)):
            value = float(currency_str)
            if 0 <= value <= 100000000:
                return round(value, 2)
            return None
        if isinstance(currency_str, str):
            cleaned = currency_str.strip()
            if not cleaned:
                return None
            cleaned = cleaned.replace('$', '').replace('€', '').replace('£', '')
            cleaned = cleaned.replace(',', '').strip()
            if not cleaned:
                return None
            value = float(cleaned)
            if 0 <= value <= 100000000:
                return round(value, 2)
        return None
    except Exception as e:
        log_error(f"parse_currency failed", error=e, context={"input": str(currency_str)[:50]})
        return None


def parse_percentage_field(pct_str):
    """Parse percentage string to decimal ratio"""
    if pct_str is None:
        return None
    try:
        if isinstance(pct_str, (int, float)):
            value = float(pct_str)
            if -1 <= value <= 10:
                return round(value, 4)
            if -100 <= value <= 1000:
                return round(value / 100.0, 4)
            return None
        if isinstance(pct_str, str):
            cleaned = pct_str.strip()
            if not cleaned:
                return None
            if cleaned.upper() in ['#DIV/0!', '#N/A', '#VALUE!', '#REF!', '#NAME?', '#NUM!', '#NULL!']:
                return None
            cleaned = cleaned.replace('%', '').strip()
            value = float(cleaned)
            if -100 <= value <= 1000:
                return round(value / 100.0, 4)
        return None
    except Exception as e:
        log_error(f"parse_percentage failed", error=e, context={"input": str(pct_str)[:50]})
        return None


def parse_integer_field(int_str):
    """Parse integer string (with possible commas)"""
    if int_str is None:
        return None
    try:
        if isinstance(int_str, int):
            if 0 <= int_str <= 10000000:
                return int_str
            return None
        if isinstance(int_str, str):
            cleaned = int_str.strip()
            if not cleaned:
                return None
            cleaned = cleaned.replace(',', '').strip()
            value = int(float(cleaned))
            if 0 <= value <= 10000000:
                return value
        return None
    except Exception as e:
        log_error(f"parse_integer failed", error=e, context={"input": str(int_str)[:50]})
        return None


# Register UDFs
parse_date_udf = udf(parse_date_field, StringType())
normalize_product_id_udf = udf(normalize_product_id, LongType())
normalize_text_udf = udf(normalize_text_field, StringType())
parse_currency_udf = udf(parse_currency_field, DoubleType())
parse_percentage_udf = udf(parse_percentage_field, DoubleType())
parse_integer_udf = udf(parse_integer_field, IntegerType())


# =============================================================================
# STEP 1: READ RAW DATA
# =============================================================================

log_step(1, "Reading raw CSV data", "started")

raw_path = f"s3://{SOURCE_BUCKET}/landing/beauty-products/"

log_info("Reading source data", details={"source_bucket": SOURCE_BUCKET, "raw_path": raw_path})

# Define explicit schema - all columns as STRING for consistent UDF input
csv_schema = StructType([
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

try:
    df_raw = spark.read.format("csv") \
        .option("header", "true") \
        .schema(csv_schema) \
        .option("delimiter", ",") \
        .option("quote", '"') \
        .option("escape", '"') \
        .option("encoding", "UTF-8") \
        .option("mode", "PERMISSIVE") \
        .option("columnNameOfCorruptRecord", "_corrupt_record") \
        .option("recursiveFileLookup", "true") \
        .option("pathGlobFilter", "*.csv") \
        .load(raw_path)
    
    log_info("CSV read operation completed", details={"schema_columns": len(csv_schema.fields)})
except Exception as e:
    log_error("Failed to read CSV", error=e, context={"raw_path": raw_path})
    raise

# Add source metadata
df_raw = df_raw.withColumn("source_file", input_file_name()) \
    .withColumn("source_record_number", monotonically_increasing_id())

# Validate folder structure consistency
df_raw = df_raw.withColumn("folder_year", regexp_extract(col("source_file"), r"/(\d{4})/\d{2}/\d{2}/", 1)) \
    .withColumn("folder_month", regexp_extract(col("source_file"), r"/\d{4}/(\d{2})/\d{2}/", 1)) \
    .withColumn("folder_day", regexp_extract(col("source_file"), r"/\d{4}/\d{2}/(\d{2})/", 1)) \
    .withColumn("filename_date", regexp_extract(col("source_file"), r"beauty-products_(\d{8})\.csv", 1))

inconsistent_files = df_raw.filter(
    (col("filename_date") != "") & 
    (col("folder_year") != "") &
    (concat(col("folder_year"), col("folder_month"), col("folder_day")) != col("filename_date"))
).select("source_file").distinct()

inconsistent_count = inconsistent_files.count()
if inconsistent_count > 0:
    log_warning(
        f"Found files with date mismatch between folder and filename",
        details={"inconsistent_count": inconsistent_count}
    )

df_raw = df_raw.drop("folder_year", "folder_month", "folder_day", "filename_date")

try:
    total_records_read = df_raw.count()
    log_info("Total records read", details={"total_records": total_records_read})
    
    if total_records_read == 0:
        log_warning("Zero records read from source", details={"raw_path": raw_path})
except Exception as e:
    log_error("Failed to count records", error=e)
    raise

log_step(1, "Reading raw CSV data", "completed")


# =============================================================================
# STEP 2: HANDLE CORRUPT RECORDS
# =============================================================================

log_step(2, "Handling corrupt records", "started")

corrupt_count = 0
if "_corrupt_record" in df_raw.columns:
    df_corrupt = df_raw.filter(col("_corrupt_record").isNotNull())
    corrupt_count = df_corrupt.count()
    
    if corrupt_count > 0:
        log_warning(f"Found corrupt records", details={"corrupt_count": corrupt_count})
        
        df_corrupt_output = df_corrupt.select(
            lit("MALFORMED_CSV").alias("error_reason"),
            col("_corrupt_record").alias("raw_record"),
            current_timestamp().alias("error_timestamp")
        )
        
        error_path = f"s3://{CURATED_BUCKET}/error/beauty-products/{datetime.utcnow().strftime('%Y/%m/%d')}/"
        df_corrupt_output.write.mode("append").parquet(error_path)
        
        # Log data change for corrupt records
        log_data_change(
            change_type="INSERT",
            table_name="error_beauty_products",
            operation="BATCH_INSERT",
            record_count=corrupt_count,
            metadata={"error_reason": "MALFORMED_CSV", "error_path": error_path}
        )
    
    df_raw = df_raw.filter(col("_corrupt_record").isNull()).drop("_corrupt_record")

log_step(2, "Handling corrupt records", "completed")


# =============================================================================
# STEP 3: APPLY TRANSFORMATIONS AND QUALITY SCORING
# =============================================================================

log_step(3, "Applying transformations and quality scoring", "started")

# Initialize quality score
df = df_raw.withColumn("data_quality_score", lit(1.0000)) \
    .withColumn("quality_flags", lit(""))

# Transform: Month (DATE)
df = df.withColumn("month", to_date(parse_date_udf(col("Month")), "yyyy-MM-dd"))
df = df.withColumn("quality_flags", 
    when(col("month").isNull(), concat(col("quality_flags"), lit("INVALID_DATE,")))
    .otherwise(col("quality_flags")))
df = df.withColumn("data_quality_score",
    when(col("month").isNull(), col("data_quality_score") - 0.20)
    .otherwise(col("data_quality_score")))

# Transform: Product ID (BIGINT)
df = df.withColumn("product_id", normalize_product_id_udf(col("Product Id")))
df = df.withColumn("product_id",
    when(col("product_id").isNull(), abs(col("source_record_number")))
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
df = df.withColumn("_revenue_parsed", parse_currency_udf(col("Revenue")))
df = df.withColumn("quality_flags",
    when(col("_revenue_parsed").isNull(), concat(col("quality_flags"), lit("INVALID_REVENUE,")))
    .otherwise(col("quality_flags")))
df = df.withColumn("data_quality_score",
    when(col("_revenue_parsed").isNull(), col("data_quality_score") - 0.15)
    .otherwise(col("data_quality_score")))
df = df.withColumn("revenue_usd",
    when(col("_revenue_parsed").isNull(), lit(0.00)).otherwise(col("_revenue_parsed")))
df = df.drop("_revenue_parsed")

# Transform: Avg Unit Price (DECIMAL)
df = df.withColumn("_avg_price_parsed", parse_currency_udf(col("`Avg. Unit Price`")))
df = df.withColumn("quality_flags",
    when(col("_avg_price_parsed").isNull(), concat(col("quality_flags"), lit("INVALID_AVG_PRICE,")))
    .otherwise(col("quality_flags")))
df = df.withColumn("data_quality_score",
    when(col("_avg_price_parsed").isNull(), col("data_quality_score") - 0.10)
    .otherwise(col("data_quality_score")))
df = df.withColumn("avg_unit_price_usd",
    when(col("_avg_price_parsed").isNull(), lit(0.00)).otherwise(col("_avg_price_parsed")))
df = df.drop("_avg_price_parsed")

# Transform: Item Sold (INT)
df = df.withColumn("_items_parsed", parse_integer_udf(col("Item Sold")))
df = df.withColumn("quality_flags",
    when(col("_items_parsed").isNull(), concat(col("quality_flags"), lit("MISSING_ITEMS,")))
    .otherwise(col("quality_flags")))
df = df.withColumn("data_quality_score",
    when(col("_items_parsed").isNull(), col("data_quality_score") - 0.10)
    .otherwise(col("data_quality_score")))
df = df.withColumn("item_sold",
    when(col("_items_parsed").isNull(), lit(0)).otherwise(col("_items_parsed")))
df = df.drop("_items_parsed")

# Transform: MoM Growth % (DECIMAL)
df = df.withColumn("mom_growth_pct", parse_percentage_udf(col("MoM Growth %")))
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
    md5(concat_ws("||", col("product_id"), col("month"), col("shop_name"), col("product_name"), col("revenue_usd"))))

# Clean up quality_flags
df = df.withColumn("quality_flags", regexp_replace(col("quality_flags"), ",$", ""))

# Add partition columns
df = df.withColumn("year", year(col("month"))) \
    .withColumn("month_num", month(col("month")))

try:
    transform_count = df.count()
    log_info("Transformations completed", details={"transform_count": transform_count})
except Exception as e:
    log_error("Failed during transformations", error=e)
    raise

log_step(3, "Applying transformations and quality scoring", "completed")


# =============================================================================
# STEP 4: DE-DUPLICATION
# =============================================================================

log_step(4, "De-duplicating records", "started")

window_spec = Window.partitionBy("product_id", "month", "shop_name").orderBy("source_record_number")
df = df.withColumn("row_num", row_number().over(window_spec))

df_duplicates = df.filter(col("row_num") > 1)
duplicate_count = df_duplicates.count()

log_info("Duplicate analysis completed", details={"duplicate_count": duplicate_count})

if duplicate_count > 0:
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
    
    # Log data change for duplicates
    log_data_change(
        change_type="INSERT",
        table_name="error_beauty_products",
        operation="BATCH_INSERT",
        record_count=duplicate_count,
        metadata={"error_reason": "DUPLICATE_RECORD", "error_path": error_path}
    )

df = df.filter(col("row_num") == 1).drop("row_num")
dedup_count = df.count()

log_step(4, "De-duplicating records", "completed")


# =============================================================================
# STEP 5: QUALITY-BASED ROUTING
# =============================================================================

log_step(5, "Routing records based on quality scores", "started")

df_passed = df.filter(col("data_quality_score") >= DQ_PASS_THRESHOLD)
df_warned = df.filter((col("data_quality_score") >= DQ_WARN_THRESHOLD) & 
                      (col("data_quality_score") < DQ_PASS_THRESHOLD))
df_failed = df.filter(col("data_quality_score") < DQ_WARN_THRESHOLD)
df_anomalies = df.filter((col("revenue_usd") > ANOMALY_REVENUE_MAX) | 
                          (col("item_sold") > ANOMALY_ITEMS_MAX))

passed_count = df_passed.count()
warned_count = df_warned.count()
failed_count = df_failed.count()
anomaly_count = df_anomalies.count()

log_info(
    "Quality routing completed",
    details={
        "passed_count": passed_count,
        "warned_count": warned_count,
        "failed_count": failed_count,
        "anomaly_count": anomaly_count,
    }
)

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
    
    # Log data change for quarantine
    log_data_change(
        change_type="INSERT",
        table_name="quarantine_beauty_products",
        operation="BATCH_INSERT",
        record_count=failed_count,
        metadata={"quarantine_reason": "LOW_QUALITY_SCORE", "quarantine_path": quarantine_path}
    )

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
    
    # Log data change for anomalies
    log_data_change(
        change_type="INSERT",
        table_name="quarantine_beauty_products",
        operation="BATCH_INSERT",
        record_count=anomaly_count,
        metadata={"quarantine_reason": "ANOMALY_DETECTED", "anomaly_path": anomaly_path}
    )

log_step(5, "Routing records based on quality scores", "completed")


# =============================================================================
# STEP 6: WRITE CURATED DATA
# =============================================================================

log_step(6, "Writing curated data to S3", "started")

curated_path = f"s3://{CURATED_BUCKET}/curated/beauty-products/"

df_curated_final = df_curated.select(
    "month", "product_id", "product_name", "shop_name",
    "l1_category", "l2_category", "l3_category", "item_sold",
    col("revenue_usd").cast(DecimalType(18, 2)).alias("revenue_usd"),
    col("avg_unit_price_usd").cast(DecimalType(10, 2)).alias("avg_unit_price_usd"),
    col("mom_growth_pct").cast(DecimalType(5, 4)).alias("mom_growth_pct"),
    "source_file", "source_record_number", "processed_timestamp", "transformation_version",
    col("data_quality_score").cast(DecimalType(5, 4)).alias("data_quality_score"),
    "quality_flags", "created_by", "record_hash", "year", "month_num"
)

df_curated_final.write \
    .mode("append") \
    .partitionBy("year", "month_num") \
    .parquet(curated_path, compression="snappy")

curated_count = df_curated_final.count()

# Log data change for curated data (implements user story: data change traceability)
log_data_change(
    change_type="INSERT",
    table_name="curated_beauty_products",
    operation="BATCH_INSERT",
    record_count=curated_count,
    metadata={
        "curated_path": curated_path,
        "source_path": raw_path,
        "compression": "snappy",
        "partitions": ["year", "month_num"],
    }
)

# Write audit log to S3 for this data change
write_audit_log_to_s3(
    s3_client=s3_client,
    bucket=METADATA_BUCKET,
    change_type="INSERT",
    table_name="curated_beauty_products",
    operation="BATCH_INSERT",
    record_count=curated_count,
    metadata={
        "curated_path": curated_path,
        "source_path": raw_path,
        "job_run_id": job_run_id,
    }
)

log_step(6, "Writing curated data to S3", "completed")


# =============================================================================
# STEP 7: GENERATE QUALITY REPORT
# =============================================================================

log_step(7, "Generating data quality report", "started")

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

avg_quality_score = round(float(quality_stats["avg_quality_score"]) if quality_stats["avg_quality_score"] is not None else 0.0, 4)
pass_rate = round(passed_count / total_records_read if total_records_read > 0 else 0, 4)

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
    "pass_rate": pass_rate,
    "quality_issues": quality_issues,
    "avg_quality_score": avg_quality_score,
    "transformation_version": TRANSFORMATION_VERSION
}

report_path = f"s3://{CURATED_BUCKET}/quality-reports/beauty-products/{datetime.utcnow().strftime('%Y/%m/%d')}/report_{job_run_id}.json"

s3_client.put_object(
    Bucket=CURATED_BUCKET,
    Key=report_path.replace(f"s3://{CURATED_BUCKET}/", ""),
    Body=json.dumps(quality_report, indent=2),
    ContentType='application/json'
)

log_info("Quality report written", details={"report_path": report_path, "avg_quality_score": avg_quality_score})

# Log quality alerts if thresholds breached
if avg_quality_score < 0.80:
    log_quality_alert(
        alert_type="QUALITY_SCORE_LOW",
        threshold=0.80,
        actual_value=avg_quality_score,
        details={"job_run_id": job_run_id}
    )

error_rate = (failed_count + duplicate_count) / total_records_read if total_records_read > 0 else 0
if error_rate > 0.05:
    log_quality_alert(
        alert_type="ERROR_RATE_HIGH",
        threshold=0.05,
        actual_value=error_rate,
        details={"job_run_id": job_run_id, "failed_count": failed_count, "duplicate_count": duplicate_count}
    )

log_step(7, "Generating data quality report", "completed")


# =============================================================================
# STEP 8: WRITE LINEAGE METADATA
# =============================================================================

log_step(8, "Writing lineage metadata", "started")

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

log_info("Lineage metadata written", details={"lineage_path": lineage_path})

log_step(8, "Writing lineage metadata", "completed")


# =============================================================================
# STEP 9: JOB COMPLETION AND METRICS
# =============================================================================

log_step(9, "Job completion and metrics", "started")

# Calculate job duration
job_end_time = time.time()
job_duration_seconds = round(job_end_time - job_start_time, 2)

# Log job summary (structured JSON for CloudWatch Logs Insights)
log_job_summary(
    total_records=total_records_read,
    records_passed=passed_count,
    records_warned=warned_count,
    records_failed=failed_count,
    records_duplicates=duplicate_count,
    records_anomalies=anomaly_count,
    avg_quality_score=avg_quality_score,
    pass_rate=pass_rate,
    duration_seconds=job_duration_seconds,
)

# Write comprehensive ETL audit summary to S3
write_etl_audit_summary(
    s3_client=s3_client,
    bucket=METADATA_BUCKET,
    source_path=raw_path,
    target_path=curated_path,
    total_records_in=total_records_read,
    total_records_out=curated_count,
    records_passed=passed_count,
    records_warned=warned_count,
    records_failed=failed_count,
    records_duplicates=duplicate_count,
    records_anomalies=anomaly_count,
    avg_quality_score=avg_quality_score,
    pass_rate=pass_rate,
    quality_issues=quality_issues,
    duration_seconds=job_duration_seconds,
)

# Publish CloudWatch custom metrics
put_data_quality_metrics(
    cloudwatch_client=cloudwatch_client,
    avg_quality_score=avg_quality_score,
    pass_rate=pass_rate,
    records_passed=passed_count,
    records_warned=warned_count,
    records_failed=failed_count,
    records_duplicates=duplicate_count,
    job_name=args['JOB_NAME'],
)

log_step(9, "Job completion and metrics", "completed")

job.commit()

log_info(
    "Beauty Products ETL job completed successfully",
    details={
        "job_run_id": job_run_id,
        "duration_seconds": job_duration_seconds,
        "total_records": total_records_read,
        "curated_records": curated_count,
    }
)
