"""
Structured Logging Utility for AWS Glue ETL Jobs.

This module provides structured JSON logging adapted from rulescore.mdc standards
for AWS Glue/PySpark environment. All logs are written in JSON format for
CloudWatch Logs Insights compatibility.

Key Features:
    - Structured JSON logging for CloudWatch Logs Insights
    - Request/Job ID correlation (adapted from rulescore.mdc request_id pattern)
    - Data change tracking for traceability
    - Function decorator for automatic logging (adapted from @log decorator)
    - Error handling with full context

Usage:
    from scripts.utils.glue_logger import (
        set_job_context,
        log_info,
        log_warning,
        log_error,
        log_data_change,
        get_job_run_id
    )

    # Initialize at job start
    set_job_context(job_run_id, execution_timestamp)

    # Log informational messages
    log_info("Processing started", details={"source": "s3://bucket/path"})

    # Log data changes for traceability
    log_data_change(
        change_type="INSERT",
        table_name="curated_beauty_products",
        operation="BATCH_INSERT",
        metadata={"record_count": 1000}
    )

    # Log errors with context
    try:
        process_data()
    except Exception as e:
        log_error("Data processing failed", error=e, context={"step": "transform"})
        raise

Adapted from rulescore.mdc logging standards:
    - @log_handler -> set_job_context (for Glue job initialization)
    - @log -> log_function decorator (for internal functions)
    - get_log_request_id() -> get_job_run_id() (for correlation)
    - log_message() -> log_info(), log_warning(), log_error()
"""

import json
import logging
import traceback
from datetime import datetime
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union

# Configure logging for CloudWatch (JSON format)
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s"  # JSON format, no extra formatting needed
)
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

# Type variable for decorator
F = TypeVar("F", bound=Callable[..., Any])


def set_job_context(
    job_run_id: str,
    execution_timestamp: str,
    job_name: Optional[str] = None,
    environment: Optional[str] = None,
    transformation_version: Optional[str] = None,
) -> None:
    """
    Set global job context for request correlation.

    Adapted from rulescore.mdc @log_handler pattern.
    Call this at the start of your Glue job to establish context for all logs.

    Args:
        job_run_id: Unique identifier for this job run (equivalent to request_id)
        execution_timestamp: ISO format timestamp when job started
        job_name: Name of the Glue job
        environment: Environment name (dev, staging, prod, poc)
        transformation_version: Version of the transformation code
    """
    global _job_context
    _job_context = {
        "job_run_id": job_run_id,
        "execution_timestamp": execution_timestamp,
        "job_name": job_name,
        "environment": environment,
        "transformation_version": transformation_version,
    }

    # Log job initialization (equivalent to @log_handler entry log)
    log_structured(
        level="INFO",
        message="Job context initialized",
        event_type="JOB_INIT",
        details={
            "job_run_id": job_run_id,
            "job_name": job_name,
            "environment": environment,
            "transformation_version": transformation_version,
        },
    )


def get_job_run_id() -> str:
    """
    Get current job run ID for correlation.

    Adapted from rulescore.mdc get_log_request_id() function.

    Returns:
        Current job run ID or "unknown" if not set
    """
    return _job_context.get("job_run_id") or "unknown"


def get_job_context() -> Dict[str, Any]:
    """
    Get full job context.

    Returns:
        Dictionary with all job context fields
    """
    return _job_context.copy()


def log_structured(
    level: str,
    message: str,
    domain: str = "beauty-products-etl",
    event_type: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    error: Optional[Exception] = None,
) -> Dict[str, Any]:
    """
    Log structured JSON message to CloudWatch.

    This is the core logging function. All log entries are JSON objects
    that can be parsed by CloudWatch Logs Insights.

    Args:
        level: Log level (INFO, WARNING, ERROR, DEBUG)
        message: Human-readable message
        domain: Domain/component name (default: beauty-products-etl)
        event_type: Type of event (DATA_CHANGE, TRANSFORMATION, ERROR, JOB_INIT, etc.)
        details: Additional structured data as dictionary
        error: Exception object if logging an error

    Returns:
        The log entry dictionary (useful for testing)
    """
    timestamp = datetime.utcnow().isoformat() + "Z"

    log_entry: Dict[str, Any] = {
        "timestamp": timestamp,
        "level": level.upper(),
        "domain": domain,
        "job_run_id": get_job_run_id(),
        "request_id": get_job_run_id(),  # Alias for rulescore.mdc compatibility
        "message": message,
    }

    # Add event type if provided
    if event_type:
        log_entry["event_type"] = event_type

    # Add job context metadata
    if _job_context.get("job_name"):
        log_entry["job_name"] = _job_context["job_name"]
    if _job_context.get("environment"):
        log_entry["environment"] = _job_context["environment"]
    if _job_context.get("transformation_version"):
        log_entry["transformation_version"] = _job_context["transformation_version"]

    # Add details if provided
    if details:
        log_entry["details"] = details

    # Add error information if provided
    if error:
        log_entry["error"] = {
            "type": type(error).__name__,
            "message": str(error),
            "traceback": traceback.format_exc(),
        }

    # Log as JSON string
    log_level = getattr(logging, level.upper(), logging.INFO)
    logger.log(log_level, json.dumps(log_entry, default=str))

    return log_entry


def log_info(message: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Log informational message.

    Adapted from rulescore.mdc log_message() function.

    Args:
        message: Human-readable message
        details: Additional structured data

    Returns:
        The log entry dictionary
    """
    return log_structured(level="INFO", message=message, details=details)


def log_warning(
    message: str,
    details: Optional[Dict[str, Any]] = None,
    event_type: str = "WARNING",
) -> Dict[str, Any]:
    """
    Log warning message.

    Args:
        message: Human-readable warning message
        details: Additional structured data
        event_type: Type of warning event

    Returns:
        The log entry dictionary
    """
    return log_structured(
        level="WARNING", message=message, event_type=event_type, details=details
    )


def log_error(
    message: str,
    error: Optional[Exception] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Log error with full context.

    Adapted from rulescore.mdc error handling patterns.

    Args:
        message: Human-readable error message
        error: Exception object
        context: Additional context about the error

    Returns:
        The log entry dictionary
    """
    return log_structured(
        level="ERROR",
        message=message,
        event_type="ERROR",
        details=context,
        error=error,
    )


def log_data_change(
    change_type: str,
    record_id: Optional[str] = None,
    table_name: Optional[str] = None,
    operation: Optional[str] = None,
    before: Optional[Dict[str, Any]] = None,
    after: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Log data changes for traceability.

    This function is specifically designed for tracking data changes
    as required by the user story: "Log data changes to S3 and/or CloudWatch for traceability"

    Args:
        change_type: Type of change (INSERT, UPDATE, DELETE, TRANSFORM, QUALITY_CHECK)
        record_id: Unique identifier of the record (optional for batch operations)
        table_name: Table/dataset name being changed
        operation: Specific operation performed (BATCH_INSERT, SINGLE_UPDATE, etc.)
        before: State before change (for UPDATE/DELETE operations)
        after: State after change (for INSERT/UPDATE operations)
        metadata: Additional metadata about the change

    Returns:
        The log entry dictionary

    Example:
        log_data_change(
            change_type="INSERT",
            table_name="curated_beauty_products",
            operation="BATCH_INSERT",
            after={"record_count": 8500, "partition": "year=2024/month_num=1"},
            metadata={"source_file": "s3://bucket/...", "quality_score_avg": 0.95}
        )
    """
    details: Dict[str, Any] = {
        "change_type": change_type,
        "table_name": table_name,
        "operation": operation,
    }

    if record_id:
        details["record_id"] = record_id
    if before:
        details["before"] = before
    if after:
        details["after"] = after
    if metadata:
        details["metadata"] = metadata

    return log_structured(
        level="INFO",
        message=f"Data change: {change_type} on {table_name or 'unknown'}",
        event_type="DATA_CHANGE",
        details=details,
    )


def log_step(step_number: int, step_name: str, status: str = "started") -> Dict[str, Any]:
    """
    Log ETL step progress.

    Args:
        step_number: Step number in the ETL process
        step_name: Name of the step
        status: Status (started, completed, failed)

    Returns:
        The log entry dictionary
    """
    return log_structured(
        level="INFO",
        message=f"Step {step_number}: {step_name} - {status}",
        event_type="ETL_STEP",
        details={
            "step_number": step_number,
            "step_name": step_name,
            "status": status,
        },
    )


def log_quality_alert(
    alert_type: str,
    threshold: float,
    actual_value: float,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Log data quality alert.

    Args:
        alert_type: Type of alert (QUALITY_SCORE_LOW, ERROR_RATE_HIGH, etc.)
        threshold: Threshold that was breached
        actual_value: Actual value that triggered the alert
        details: Additional context

    Returns:
        The log entry dictionary
    """
    alert_details = {
        "alert_type": alert_type,
        "threshold": threshold,
        "actual_value": actual_value,
    }
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
    records_failed: int,
    records_duplicates: int,
    records_anomalies: int,
    avg_quality_score: float,
    pass_rate: float,
    duration_seconds: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Log job summary at completion.

    Args:
        total_records: Total records processed
        records_passed: Records that passed quality checks
        records_failed: Records that failed quality checks
        records_duplicates: Duplicate records found
        records_anomalies: Anomaly records detected
        avg_quality_score: Average quality score
        pass_rate: Pass rate percentage
        duration_seconds: Job duration in seconds

    Returns:
        The log entry dictionary
    """
    return log_structured(
        level="INFO",
        message="Job completed successfully",
        event_type="JOB_SUMMARY",
        details={
            "total_records": total_records,
            "records_passed": records_passed,
            "records_failed": records_failed,
            "records_duplicates": records_duplicates,
            "records_anomalies": records_anomalies,
            "avg_quality_score": avg_quality_score,
            "pass_rate": pass_rate,
            "duration_seconds": duration_seconds,
        },
    )


def log_function(func: F) -> F:
    """
    Decorator to log function execution.

    Adapted from rulescore.mdc @log() decorator for internal functions.
    Use this on transformation functions to automatically log their execution.

    Usage:
        @log_function
        def transform_data(df):
            # transformation logic
            return transformed_df

    Args:
        func: Function to decorate

    Returns:
        Decorated function with automatic logging
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        func_name = func.__name__

        # Log function start
        log_structured(
            level="DEBUG",
            message=f"Function {func_name} started",
            event_type="FUNCTION_START",
            details={
                "function": func_name,
                "args_count": len(args),
                "kwargs_keys": list(kwargs.keys()),
            },
        )

        try:
            result = func(*args, **kwargs)

            # Log function completion
            log_structured(
                level="DEBUG",
                message=f"Function {func_name} completed",
                event_type="FUNCTION_END",
                details={"function": func_name, "success": True},
            )

            return result

        except Exception as e:
            # Log function failure with full context
            log_error(
                message=f"Function {func_name} failed",
                error=e,
                context={
                    "function": func_name,
                    "args_preview": str(args)[:200] if args else None,
                    "kwargs_preview": str(kwargs)[:200] if kwargs else None,
                },
            )
            raise

    return wrapper  # type: ignore
