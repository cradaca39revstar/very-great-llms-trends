"""
Audit Logging Utility for S3 Data Change Traceability.

This module provides S3-based audit trail functionality for tracking data changes
in the Beauty Products Data Lake. It creates structured JSON audit logs in S3
for long-term traceability and compliance requirements.

Key Features:
    - Structured JSON audit logs in S3
    - Data change tracking (INSERT, UPDATE, DELETE, TRANSFORM)
    - Batch audit logging for performance
    - Full traceability metadata (who, what, when, where)
    - Error resilient with CloudWatch fallback

S3 Structure:
    s3://{bucket}/audit-logs/beauty-products/{YYYY}/{MM}/{DD}/{job_run_id}_{timestamp}_{change_type}.json

Usage:
    from scripts.utils.audit_logger import write_audit_log_to_s3, write_batch_audit_log

    # Single audit log entry
    write_audit_log_to_s3(
        s3_client=boto3.client('s3'),
        bucket="metadata-bucket",
        change_type="INSERT",
        table_name="curated_beauty_products",
        operation="BATCH_INSERT",
        after={"record_count": 8500},
        metadata={"source_file": "s3://..."}
    )

    # Batch audit log for multiple changes
    write_batch_audit_log(
        s3_client=boto3.client('s3'),
        bucket="metadata-bucket",
        changes=[...],
        summary={"total_records": 10000, "pass_rate": 0.95}
    )
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

# Import from glue_logger to maintain consistency
try:
    from scripts.utils.glue_logger import get_job_run_id, log_error, log_info
except ImportError:
    # Fallback for testing or standalone use
    def get_job_run_id() -> str:
        return datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    def log_error(message: str, error: Exception, context: Optional[Dict] = None) -> None:
        print(f"ERROR: {message} - {error}")

    def log_info(message: str, details: Optional[Dict] = None) -> None:
        print(f"INFO: {message}")


def _generate_audit_s3_key(
    change_type: str,
    prefix: str = "audit-logs/beauty-products",
    suffix: Optional[str] = None,
) -> str:
    """
    Generate S3 key for audit log file.

    Args:
        change_type: Type of change (INSERT, UPDATE, DELETE, etc.)
        prefix: S3 prefix for audit logs
        suffix: Optional suffix for the filename

    Returns:
        S3 key string
    """
    timestamp = datetime.utcnow()
    date_prefix = timestamp.strftime("%Y/%m/%d")
    time_suffix = timestamp.strftime("%H%M%S_%f")
    job_run_id = get_job_run_id()

    filename = f"{job_run_id}_{time_suffix}_{change_type}"
    if suffix:
        filename = f"{filename}_{suffix}"
    filename = f"{filename}.json"

    return f"{prefix}/{date_prefix}/{filename}"


def write_audit_log_to_s3(
    s3_client: Any,
    bucket: str,
    change_type: str,
    record_id: Optional[str] = None,
    table_name: Optional[str] = None,
    operation: Optional[str] = None,
    before: Optional[Dict[str, Any]] = None,
    after: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    Write single audit log entry to S3 for traceability.

    This function implements the user story requirement:
    "Log data changes to S3 and/or CloudWatch for traceability"

    Args:
        s3_client: Boto3 S3 client
        bucket: S3 bucket name
        change_type: Type of change (INSERT, UPDATE, DELETE, TRANSFORM, QUALITY_CHECK)
        record_id: Unique identifier of the record (optional for batch operations)
        table_name: Table/dataset name being changed
        operation: Specific operation performed
        before: State before change (for UPDATE/DELETE)
        after: State after change (for INSERT/UPDATE)
        metadata: Additional metadata about the change

    Returns:
        S3 key where the audit log was written, or None if failed

    Example:
        s3_key = write_audit_log_to_s3(
            s3_client=boto3.client('s3'),
            bucket="very-great-products-metadata-us-east-1-poc",
            change_type="INSERT",
            table_name="curated_beauty_products",
            operation="BATCH_INSERT",
            after={"record_count": 8500, "partition": "year=2024/month_num=1"},
            metadata={"source_file": "s3://...", "quality_score_avg": 0.95}
        )
    """
    timestamp = datetime.utcnow()

    # Build audit entry following rulescore.mdc response structure patterns
    audit_entry: Dict[str, Any] = {
        "timestamp": timestamp.isoformat() + "Z",
        "job_run_id": get_job_run_id(),
        "request_id": get_job_run_id(),  # Alias for rulescore.mdc compatibility
        "change_type": change_type,
        "table_name": table_name,
        "operation": operation,
    }

    # Add optional fields only if provided
    if record_id:
        audit_entry["record_id"] = record_id
    if before:
        audit_entry["before"] = before
    if after:
        audit_entry["after"] = after
    if metadata:
        audit_entry["metadata"] = metadata

    # Generate S3 key
    s3_key = _generate_audit_s3_key(change_type)

    try:
        s3_client.put_object(
            Bucket=bucket,
            Key=s3_key,
            Body=json.dumps(audit_entry, indent=2, default=str),
            ContentType="application/json",
            ServerSideEncryption="AES256",
            Metadata={
                "job-run-id": get_job_run_id(),
                "change-type": change_type,
                "table-name": table_name or "unknown",
                "timestamp": timestamp.isoformat(),
            },
        )

        log_info(
            f"Audit log written to S3",
            details={"s3_key": s3_key, "change_type": change_type, "table_name": table_name},
        )

        return s3_key

    except Exception as e:
        # Log error but don't fail the job - audit logging is non-critical
        log_error(
            f"Failed to write audit log to S3: {s3_key}",
            error=e,
            context={"bucket": bucket, "change_type": change_type, "table_name": table_name},
        )
        return None


def write_batch_audit_log(
    s3_client: Any,
    bucket: str,
    changes: List[Dict[str, Any]],
    summary: Dict[str, Any],
) -> Optional[str]:
    """
    Write batch audit log for multiple changes.

    Use this for batch operations where writing individual audit logs
    would be too costly in terms of S3 API calls.

    Args:
        s3_client: Boto3 S3 client
        bucket: S3 bucket name
        changes: List of change entries
        summary: Summary metadata for the batch

    Returns:
        S3 key where the batch audit log was written, or None if failed

    Example:
        write_batch_audit_log(
            s3_client=boto3.client('s3'),
            bucket="metadata-bucket",
            changes=[
                {
                    "change_type": "INSERT",
                    "table_name": "curated_beauty_products",
                    "operation": "BATCH_INSERT",
                    "after": {"record_count": 8500}
                },
                {
                    "change_type": "INSERT",
                    "table_name": "quarantine_beauty_products",
                    "operation": "BATCH_INSERT",
                    "after": {"record_count": 300}
                }
            ],
            summary={
                "total_records": 10000,
                "records_passed": 8500,
                "records_failed": 300,
                "pass_rate": 0.85
            }
        )
    """
    timestamp = datetime.utcnow()

    batch_log: Dict[str, Any] = {
        "timestamp": timestamp.isoformat() + "Z",
        "job_run_id": get_job_run_id(),
        "request_id": get_job_run_id(),
        "log_type": "BATCH_AUDIT",
        "summary": summary,
        "changes": changes,
        "total_changes": len(changes),
    }

    s3_key = _generate_audit_s3_key("BATCH", suffix="batch")

    try:
        s3_client.put_object(
            Bucket=bucket,
            Key=s3_key,
            Body=json.dumps(batch_log, indent=2, default=str),
            ContentType="application/json",
            ServerSideEncryption="AES256",
            Metadata={
                "job-run-id": get_job_run_id(),
                "change-type": "BATCH",
                "total-changes": str(len(changes)),
                "timestamp": timestamp.isoformat(),
            },
        )

        log_info(
            f"Batch audit log written to S3",
            details={
                "s3_key": s3_key,
                "total_changes": len(changes),
                "summary": summary,
            },
        )

        return s3_key

    except Exception as e:
        log_error(
            f"Failed to write batch audit log to S3",
            error=e,
            context={"bucket": bucket, "total_changes": len(changes)},
        )
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
    additional_metadata: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    Write comprehensive ETL audit summary to S3.

    This creates a complete audit trail of the ETL job execution
    with all relevant metrics and traceability information.

    Args:
        s3_client: Boto3 S3 client
        bucket: S3 bucket name
        source_path: Source data path
        target_path: Target data path
        total_records_in: Total records read from source
        total_records_out: Total records written to target
        records_passed: Records that passed quality checks
        records_warned: Records with warnings
        records_failed: Records that failed quality checks
        records_duplicates: Duplicate records found
        records_anomalies: Anomaly records detected
        avg_quality_score: Average quality score
        pass_rate: Pass rate percentage
        quality_issues: Dictionary of quality issues and counts
        additional_metadata: Any additional metadata

    Returns:
        S3 key where the summary was written, or None if failed
    """
    timestamp = datetime.utcnow()

    summary: Dict[str, Any] = {
        "timestamp": timestamp.isoformat() + "Z",
        "job_run_id": get_job_run_id(),
        "request_id": get_job_run_id(),
        "log_type": "ETL_AUDIT_SUMMARY",
        "source": {
            "path": source_path,
            "records_count": total_records_in,
        },
        "target": {
            "path": target_path,
            "records_count": total_records_out,
        },
        "quality_metrics": {
            "records_passed": records_passed,
            "records_warned": records_warned,
            "records_failed": records_failed,
            "records_duplicates": records_duplicates,
            "records_anomalies": records_anomalies,
            "avg_quality_score": avg_quality_score,
            "pass_rate": pass_rate,
        },
        "data_changes": [
            {
                "change_type": "INSERT",
                "table_name": "curated_beauty_products",
                "operation": "BATCH_INSERT",
                "record_count": records_passed + records_warned,
            },
        ],
    }

    # Add failed records change if any
    if records_failed > 0:
        summary["data_changes"].append({
            "change_type": "INSERT",
            "table_name": "quarantine_beauty_products",
            "operation": "BATCH_INSERT",
            "record_count": records_failed,
        })

    # Add duplicate records change if any
    if records_duplicates > 0:
        summary["data_changes"].append({
            "change_type": "INSERT",
            "table_name": "error_beauty_products",
            "operation": "BATCH_INSERT",
            "record_count": records_duplicates,
        })

    # Add quality issues if provided
    if quality_issues:
        summary["quality_issues"] = quality_issues

    # Add additional metadata if provided
    if additional_metadata:
        summary["additional_metadata"] = additional_metadata

    s3_key = _generate_audit_s3_key("ETL_SUMMARY", suffix="summary")

    try:
        s3_client.put_object(
            Bucket=bucket,
            Key=s3_key,
            Body=json.dumps(summary, indent=2, default=str),
            ContentType="application/json",
            ServerSideEncryption="AES256",
            Metadata={
                "job-run-id": get_job_run_id(),
                "log-type": "ETL_AUDIT_SUMMARY",
                "total-records-in": str(total_records_in),
                "total-records-out": str(total_records_out),
                "pass-rate": str(pass_rate),
                "timestamp": timestamp.isoformat(),
            },
        )

        log_info(
            "ETL audit summary written to S3",
            details={
                "s3_key": s3_key,
                "total_records_in": total_records_in,
                "total_records_out": total_records_out,
                "pass_rate": pass_rate,
            },
        )

        return s3_key

    except Exception as e:
        log_error(
            "Failed to write ETL audit summary to S3",
            error=e,
            context={"bucket": bucket, "total_records_in": total_records_in},
        )
        return None
