"""
Utility modules for Beauty Products Data Lake ETL jobs.

This package provides structured logging, audit trail, and metrics utilities
adapted from rulescore.mdc standards for AWS Glue/PySpark environment.

Modules:
    - glue_logger: Structured JSON logging for CloudWatch
    - audit_logger: S3 audit trail for data changes
    - metrics: CloudWatch custom metrics

Usage:
    from scripts.utils.glue_logger import (
        set_job_context,
        log_info,
        log_warning,
        log_error,
        log_data_change,
        get_job_run_id
    )
    from scripts.utils.audit_logger import write_audit_log_to_s3, write_batch_audit_log
    from scripts.utils.metrics import put_custom_metric
"""

from scripts.utils.glue_logger import (
    set_job_context,
    get_job_run_id,
    log_structured,
    log_info,
    log_warning,
    log_error,
    log_data_change,
    log_function,
)

from scripts.utils.audit_logger import (
    write_audit_log_to_s3,
    write_batch_audit_log,
)

from scripts.utils.metrics import (
    put_custom_metric,
    put_data_quality_metrics,
    put_etl_job_metrics,
)

__all__ = [
    # Logging
    "set_job_context",
    "get_job_run_id",
    "log_structured",
    "log_info",
    "log_warning",
    "log_error",
    "log_data_change",
    "log_function",
    # Audit
    "write_audit_log_to_s3",
    "write_batch_audit_log",
    # Metrics
    "put_custom_metric",
    "put_data_quality_metrics",
    "put_etl_job_metrics",
]
