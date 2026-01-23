"""
CloudWatch Custom Metrics Utility for Beauty Products Data Lake.

This module provides functions to publish custom metrics to CloudWatch
for enhanced monitoring and alerting of ETL jobs and data quality.

Key Features:
    - Custom metrics for data quality tracking
    - ETL job performance metrics
    - Data change tracking metrics
    - Error rate monitoring

Namespaces:
    - BeautyProducts/DataQuality: Quality score, pass rate, error counts
    - BeautyProducts/ETL: Job duration, records processed, throughput
    - BeautyProducts/DataChanges: Insert, update, delete counts

Usage:
    from scripts.utils.metrics import put_custom_metric, put_data_quality_metrics

    # Put single metric
    put_custom_metric(
        namespace="BeautyProducts/DataQuality",
        metric_name="AvgQualityScore",
        value=0.95,
        unit="None",
        dimensions={"JobName": "beauty-products-etl-job"}
    )

    # Put data quality metrics batch
    put_data_quality_metrics(
        cloudwatch_client=boto3.client('cloudwatch'),
        avg_quality_score=0.95,
        pass_rate=0.85,
        records_passed=8500,
        records_failed=300,
        job_name="beauty-products-etl-job"
    )
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

# Import from glue_logger for consistent logging
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


# CloudWatch namespace constants
NAMESPACE_DATA_QUALITY = "BeautyProducts/DataQuality"
NAMESPACE_ETL = "BeautyProducts/ETL"
NAMESPACE_DATA_CHANGES = "BeautyProducts/DataChanges"


def put_custom_metric(
    cloudwatch_client: Any,
    namespace: str,
    metric_name: str,
    value: float,
    unit: str = "Count",
    dimensions: Optional[Dict[str, str]] = None,
) -> bool:
    """
    Put a custom metric to CloudWatch.

    Args:
        cloudwatch_client: Boto3 CloudWatch client
        namespace: CloudWatch namespace (e.g., "BeautyProducts/DataQuality")
        metric_name: Name of the metric
        value: Metric value
        unit: Unit type (Count, Percent, Seconds, None, etc.)
        dimensions: Optional dimensions for the metric

    Returns:
        True if metric was published successfully, False otherwise

    Example:
        put_custom_metric(
            cloudwatch_client=boto3.client('cloudwatch'),
            namespace="BeautyProducts/DataQuality",
            metric_name="AvgQualityScore",
            value=0.95,
            unit="None",
            dimensions={"JobName": "beauty-products-etl-job"}
        )
    """
    timestamp = datetime.utcnow()

    metric_data: Dict[str, Any] = {
        "MetricName": metric_name,
        "Value": value,
        "Unit": unit,
        "Timestamp": timestamp,
    }

    # Add dimensions if provided
    if dimensions:
        metric_data["Dimensions"] = [
            {"Name": k, "Value": v} for k, v in dimensions.items()
        ]

    try:
        cloudwatch_client.put_metric_data(
            Namespace=namespace,
            MetricData=[metric_data],
        )

        log_info(
            f"Custom metric published to CloudWatch",
            details={
                "namespace": namespace,
                "metric_name": metric_name,
                "value": value,
                "unit": unit,
            },
        )

        return True

    except Exception as e:
        log_error(
            f"Failed to publish metric to CloudWatch",
            error=e,
            context={
                "namespace": namespace,
                "metric_name": metric_name,
                "value": value,
            },
        )
        return False


def put_data_quality_metrics(
    cloudwatch_client: Any,
    avg_quality_score: float,
    pass_rate: float,
    records_passed: int,
    records_warned: int,
    records_failed: int,
    records_duplicates: int,
    job_name: str,
    environment: Optional[str] = None,
) -> bool:
    """
    Put data quality metrics batch to CloudWatch.

    This function publishes all data quality related metrics in a single call.

    Args:
        cloudwatch_client: Boto3 CloudWatch client
        avg_quality_score: Average quality score (0.0 - 1.0)
        pass_rate: Pass rate percentage (0.0 - 1.0)
        records_passed: Number of records that passed quality checks
        records_warned: Number of records with warnings
        records_failed: Number of records that failed quality checks
        records_duplicates: Number of duplicate records
        job_name: Name of the Glue job
        environment: Environment name (optional)

    Returns:
        True if metrics were published successfully, False otherwise
    """
    timestamp = datetime.utcnow()

    # Build dimensions
    dimensions = [{"Name": "JobName", "Value": job_name}]
    if environment:
        dimensions.append({"Name": "Environment", "Value": environment})

    # Build metric data
    metric_data: List[Dict[str, Any]] = [
        {
            "MetricName": "AvgQualityScore",
            "Value": avg_quality_score,
            "Unit": "None",
            "Timestamp": timestamp,
            "Dimensions": dimensions,
        },
        {
            "MetricName": "PassRate",
            "Value": pass_rate * 100,  # Convert to percentage
            "Unit": "Percent",
            "Timestamp": timestamp,
            "Dimensions": dimensions,
        },
        {
            "MetricName": "RecordsPassed",
            "Value": records_passed,
            "Unit": "Count",
            "Timestamp": timestamp,
            "Dimensions": dimensions,
        },
        {
            "MetricName": "RecordsWarned",
            "Value": records_warned,
            "Unit": "Count",
            "Timestamp": timestamp,
            "Dimensions": dimensions,
        },
        {
            "MetricName": "RecordsFailed",
            "Value": records_failed,
            "Unit": "Count",
            "Timestamp": timestamp,
            "Dimensions": dimensions,
        },
        {
            "MetricName": "RecordsDuplicates",
            "Value": records_duplicates,
            "Unit": "Count",
            "Timestamp": timestamp,
            "Dimensions": dimensions,
        },
        {
            "MetricName": "ErrorRate",
            "Value": (records_failed + records_duplicates)
            / max(records_passed + records_warned + records_failed + records_duplicates, 1)
            * 100,
            "Unit": "Percent",
            "Timestamp": timestamp,
            "Dimensions": dimensions,
        },
    ]

    try:
        cloudwatch_client.put_metric_data(
            Namespace=NAMESPACE_DATA_QUALITY,
            MetricData=metric_data,
        )

        log_info(
            "Data quality metrics published to CloudWatch",
            details={
                "namespace": NAMESPACE_DATA_QUALITY,
                "avg_quality_score": avg_quality_score,
                "pass_rate": pass_rate,
                "metrics_count": len(metric_data),
            },
        )

        return True

    except Exception as e:
        log_error(
            "Failed to publish data quality metrics to CloudWatch",
            error=e,
            context={
                "namespace": NAMESPACE_DATA_QUALITY,
                "avg_quality_score": avg_quality_score,
                "pass_rate": pass_rate,
            },
        )
        return False


def put_etl_job_metrics(
    cloudwatch_client: Any,
    total_records_read: int,
    total_records_written: int,
    job_duration_seconds: float,
    job_name: str,
    environment: Optional[str] = None,
) -> bool:
    """
    Put ETL job performance metrics to CloudWatch.

    Args:
        cloudwatch_client: Boto3 CloudWatch client
        total_records_read: Total records read from source
        total_records_written: Total records written to target
        job_duration_seconds: Job duration in seconds
        job_name: Name of the Glue job
        environment: Environment name (optional)

    Returns:
        True if metrics were published successfully, False otherwise
    """
    timestamp = datetime.utcnow()

    # Build dimensions
    dimensions = [{"Name": "JobName", "Value": job_name}]
    if environment:
        dimensions.append({"Name": "Environment", "Value": environment})

    # Calculate throughput (records per second)
    throughput = total_records_read / max(job_duration_seconds, 1)

    # Build metric data
    metric_data: List[Dict[str, Any]] = [
        {
            "MetricName": "TotalRecordsRead",
            "Value": total_records_read,
            "Unit": "Count",
            "Timestamp": timestamp,
            "Dimensions": dimensions,
        },
        {
            "MetricName": "TotalRecordsWritten",
            "Value": total_records_written,
            "Unit": "Count",
            "Timestamp": timestamp,
            "Dimensions": dimensions,
        },
        {
            "MetricName": "JobDuration",
            "Value": job_duration_seconds,
            "Unit": "Seconds",
            "Timestamp": timestamp,
            "Dimensions": dimensions,
        },
        {
            "MetricName": "Throughput",
            "Value": throughput,
            "Unit": "Count/Second",
            "Timestamp": timestamp,
            "Dimensions": dimensions,
        },
    ]

    try:
        cloudwatch_client.put_metric_data(
            Namespace=NAMESPACE_ETL,
            MetricData=metric_data,
        )

        log_info(
            "ETL job metrics published to CloudWatch",
            details={
                "namespace": NAMESPACE_ETL,
                "total_records_read": total_records_read,
                "job_duration_seconds": job_duration_seconds,
                "throughput": throughput,
            },
        )

        return True

    except Exception as e:
        log_error(
            "Failed to publish ETL job metrics to CloudWatch",
            error=e,
            context={
                "namespace": NAMESPACE_ETL,
                "total_records_read": total_records_read,
            },
        )
        return False


def put_data_change_metrics(
    cloudwatch_client: Any,
    inserts: int,
    updates: int,
    deletes: int,
    table_name: str,
    job_name: str,
    environment: Optional[str] = None,
) -> bool:
    """
    Put data change metrics to CloudWatch.

    Track INSERT, UPDATE, DELETE operations for data change traceability.

    Args:
        cloudwatch_client: Boto3 CloudWatch client
        inserts: Number of inserts
        updates: Number of updates
        deletes: Number of deletes
        table_name: Target table name
        job_name: Name of the Glue job
        environment: Environment name (optional)

    Returns:
        True if metrics were published successfully, False otherwise
    """
    timestamp = datetime.utcnow()

    # Build dimensions
    dimensions = [
        {"Name": "JobName", "Value": job_name},
        {"Name": "TableName", "Value": table_name},
    ]
    if environment:
        dimensions.append({"Name": "Environment", "Value": environment})

    # Build metric data
    metric_data: List[Dict[str, Any]] = [
        {
            "MetricName": "Inserts",
            "Value": inserts,
            "Unit": "Count",
            "Timestamp": timestamp,
            "Dimensions": dimensions,
        },
        {
            "MetricName": "Updates",
            "Value": updates,
            "Unit": "Count",
            "Timestamp": timestamp,
            "Dimensions": dimensions,
        },
        {
            "MetricName": "Deletes",
            "Value": deletes,
            "Unit": "Count",
            "Timestamp": timestamp,
            "Dimensions": dimensions,
        },
        {
            "MetricName": "TotalChanges",
            "Value": inserts + updates + deletes,
            "Unit": "Count",
            "Timestamp": timestamp,
            "Dimensions": dimensions,
        },
    ]

    try:
        cloudwatch_client.put_metric_data(
            Namespace=NAMESPACE_DATA_CHANGES,
            MetricData=metric_data,
        )

        log_info(
            "Data change metrics published to CloudWatch",
            details={
                "namespace": NAMESPACE_DATA_CHANGES,
                "table_name": table_name,
                "inserts": inserts,
                "updates": updates,
                "deletes": deletes,
            },
        )

        return True

    except Exception as e:
        log_error(
            "Failed to publish data change metrics to CloudWatch",
            error=e,
            context={
                "namespace": NAMESPACE_DATA_CHANGES,
                "table_name": table_name,
            },
        )
        return False
