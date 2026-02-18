# S3 Bucket Structure
## Beauty Products Data Lake

**Version:** 1.0.0  
**Last Updated:** January 17, 2026  

---

## Overview

The Beauty Products Data Lake uses three primary S3 buckets following the **Medallion Architecture** pattern (Bronze → Silver → Gold), adapted to our use case as Raw → Curated → Metadata.

---

## Bucket 1: Raw Zone

**Bucket Name:** `very-great-products-raw-us-east-1-{environment}` (where `{environment}` is `dev`, `staging`, `prod`, or `poc`)

**Purpose:** Immutable storage of source CSV files

**Note:** The environment suffix is configured via Terraform variable `environment` in `terraform.tfvars`. Examples in this document use `dev` as the default environment.

**Characteristics:**
- Data format: CSV (as received from source)
- Retention: 90 days Standard, then Glacier; delete after 1 year
- Versioning: Enabled
- Encryption: AES-256 (SSE-S3)
- Public access: Blocked

### Directory Structure

```
very-great-products-raw-us-east-1-dev/
├── landing/
│   └── beauty-products/
│       └── YYYY/
│           └── MM/
│               └── DD/
│                   ├── file1.csv
│                   ├── file2.csv
│                   └── fileN.csv
│
└── archive/
    └── beauty-products/
        └── YYYY/
            └── MM/
                └── DD/
                    ├── file1_processed_20240417120000.csv
                    └── file2_processed_20240417120500.csv
```

### Path Conventions

**Landing Path:**
- Pattern: `landing/beauty-products/YYYY/MM/DD/filename.csv`
- Example: `landing/beauty-products/2024/04/17/products_20240417.csv`
- Purpose: Active ingestion zone; Glue job reads from here

**Archive Path:**
- Pattern: `archive/beauty-products/YYYY/MM/DD/filename_processed_TIMESTAMP.csv`
- Example: `archive/beauty-products/2024/04/17/products_20240417_processed_20240417120000.csv`
- Purpose: Post-processing archive for reprocessing capability

### Lifecycle Policies

| Prefix | Days | Action |
|--------|------|--------|
| `landing/` | 90 | Transition to Glacier |
| `landing/` | 365 | Delete |
| `archive/` | 90 | Transition to Glacier |
| `archive/` | 365 | Delete |

---

## Bucket 2: Curated Zone

**Bucket Name:** `very-great-products-processed-us-east-1-{environment}` (where `{environment}` is `dev`, `staging`, `prod`, or `poc`)

**Purpose:** Cleaned, validated, and transformed data for analytics

**Characteristics:**
- Data format: Parquet with Snappy compression
- Retention: 7 years (6 months Standard, then Standard-IA)
- Versioning: Enabled
- Encryption: AES-256 (SSE-S3)
- Public access: Blocked

### Directory Structure

```
very-great-products-processed-us-east-1-dev/
├── curated/
│   └── beauty-products/
│       └── year=YYYY/
│           └── month_num=MM/
│               ├── part-00000-{uuid}.snappy.parquet
│               ├── part-00001-{uuid}.snappy.parquet
│               └── part-NNNNN-{uuid}.snappy.parquet
│
├── error/
│   └── beauty-products/
│       └── YYYY/
│           └── MM/
│               └── DD/
│                   └── error-records-{timestamp}.parquet
│
├── quarantine/
│   └── beauty-products/
│       └── YYYY/
│           └── MM/
│               └── DD/
│                   ├── quarantine-low-quality-{timestamp}.parquet
│                   └── quarantine-anomaly-{timestamp}.parquet
│
└── quality-reports/
    └── beauty-products/
        └── YYYY/
            └── MM/
                └── DD/
                    └── report_{job_run_id}.json
```

### Path Conventions

**Curated Path (Partitioned):**
- Pattern: `curated/beauty-products/year=YYYY/month_num=MM/`
- Example: `curated/beauty-products/year=2024/month_num=4/part-00000-abc123.snappy.parquet`
- Purpose: High-quality data for analytics
- Partitioning: Hive-style by year and month for query optimization

**Error Path:**
- Pattern: `error/beauty-products/YYYY/MM/DD/`
- Example: `error/beauty-products/2024/04/17/error-records-123456.parquet`
- Purpose: Malformed CSV rows, duplicates

**Quarantine Path:**
- Pattern: `quarantine/beauty-products/YYYY/MM/DD/`
- Example: `quarantine/beauty-products/2024/04/17/quarantine-low-quality-123456.parquet`
- Purpose: Records with quality score < 0.70 or anomalies (revenue > $10M, items > 1M)

**Quality Reports Path:**
- Pattern: `quality-reports/beauty-products/YYYY/MM/DD/report_{job_run_id}.json`
- Example: `quality-reports/beauty-products/2024/04/17/report_jr_20240417_123456.json`
- Purpose: Aggregate data quality metrics per job run

### Lifecycle Policies

| Prefix | Days | Action |
|--------|------|--------|
| `curated/` | 180 | Transition to Standard-IA |
| `error/` | 30 | Delete |
| `quarantine/` | 30 | Delete |
| `quality-reports/` | 730 | Transition to Standard-IA (2 years) |

---

## Bucket 3: Metadata Zone

**Bucket Name:** `very-great-products-metadata-us-east-1-{environment}` (where `{environment}` is `dev`, `staging`, `prod`, or `poc`)

**Purpose:** Lineage, audit logs, and governance metadata

**Characteristics:**
- Data format: Parquet (lineage), JSON (audit)
- Retention: 5 years
- Versioning: Enabled
- Encryption: AES-256 (SSE-S3)
- Public access: Blocked

### Directory Structure

```
very-great-products-metadata-us-east-1-dev/
├── lineage/
│   ├── part-00000-{uuid}.parquet
│   └── part-NNNNN-{uuid}.parquet
│
├── audit/
│   └── YYYY/
│       └── MM/
│           └── DD/
│               └── audit-{timestamp}.json
│
└── schemas/
    ├── v1.0.0.json
    ├── v1.1.0.json
    └── latest.json
```

### Path Conventions

**Lineage Path:**
- Pattern: `lineage/`
- Purpose: Source-to-target lineage tracking (Parquet table)
- Schema: source_file_path, target_file_path, job_name, job_run_id, transformation_timestamp, records_in, records_out, records_error

**Audit Path:**
- Pattern: `audit/YYYY/MM/DD/`
- Purpose: Change history, governance events (JSON logs)

**Schemas Path:**
- Pattern: `schemas/vX.Y.Z.json`
- Purpose: Versioned schema definitions for curated tables

---

## Bucket 4: Glue Scripts (Supporting)

**Bucket Name:** `very-great-products-glue-scripts-us-east-1-{environment}` (where `{environment}` is `dev`, `staging`, `prod`, or `poc`)

**Purpose:** Storage for Glue ETL scripts and dependencies

**Characteristics:**
- Data format: Python scripts
- Versioning: Enabled
- Encryption: AES-256 (SSE-S3)

### Directory Structure

```
very-great-products-glue-scripts-us-east-1-dev/
├── scripts/
│   ├── beauty_products_etl.py
│   └── backup/
│       ├── beauty_products_etl_v0.9.0.py
│       └── beauty_products_etl_v1.0.0.py
│
└── spark-logs/
    └── {job-run-id}/
        └── spark-events.log
```

---

## Access Patterns

### Read Access

**Glue ETL Job:**
- Reads: `raw-bucket/landing/`
- Writes: `curated-bucket/curated/`, `curated-bucket/error/`, `curated-bucket/quarantine/`, `curated-bucket/quality-reports/`, `metadata-bucket/lineage/`

**Athena Queries:**
- Reads: `curated-bucket/curated/`, `curated-bucket/quarantine/`, `curated-bucket/quality-reports/`, `metadata-bucket/lineage/`

**Data Analysts:**
- Athena read access to curated zone only
- No direct S3 access to raw zone

**Data Engineers:**
- Full read/write access to all buckets
- For troubleshooting and reprocessing

---

## Naming Conventions

### Buckets
- Format: `{project}-{zone}-{region}-{environment}`
- Example: `very-great-products-raw-us-east-1-dev` (for dev environment)

### Prefixes
- Format: `{zone}/{data-domain}/YYYY/MM/DD/` (for time-based data)
- Format: `{zone}/{data-domain}/year=YYYY/month_num=MM/` (for partitioned data)

### Files
- CSV: `{dataset}_{YYYYMMDD}.csv`
- Parquet: `part-{NNNNN}-{uuid}.snappy.parquet` (Spark default)
- JSON: `{report-type}_{job-run-id}.json`

---

## Tagging Strategy

All S3 objects should be tagged with:

| Tag Key | Tag Value | Purpose |
|---------|-----------|---------|
| `Project` | `BeautyProductsDataLake` | Project identification |
| `Environment` | `poc` / `dev` / `staging` / `prod` | Environment separation |
| `DataZone` | `raw` / `curated` / `metadata` | Data zone classification |
| `ManagedBy` | `Terraform` | Infrastructure management |
| `CostCenter` | `{cost-center-code}` | Cost allocation |
| `DataClassification` | `Internal` / `Confidential` | Security classification |

---

## Monitoring and Alerts

### S3 Metrics to Monitor

**Storage Metrics:**
- Bucket size by prefix
- Object count by prefix
- Storage class distribution

**Access Metrics:**
- GetObject requests (read activity)
- PutObject requests (write activity)
- 4xx/5xx errors

**Cost Metrics:**
- Storage costs by bucket
- Request costs
- Data transfer costs

### CloudWatch Alarms

- Storage > 1TB: Review data retention policies
- 4xx errors > 100/hour: Investigate access issues
- 5xx errors > 10/hour: AWS service issue escalation

---

## Backup and Disaster Recovery

### Backup Strategy

**S3 Versioning:** Enabled on all buckets
- Protects against accidental deletion
- 30-day retention of deleted versions

**Cross-Region Replication (Production):**
- Curated bucket replicated to `us-west-2` (disaster recovery)
- Metadata bucket replicated to `us-west-2`

**Backup Schedule:**
- Continuous (via versioning and replication)
- No scheduled backups needed for S3 (built-in durability)

### Recovery Procedures

**Scenario 1: Accidental File Deletion**
```bash
# List deleted versions
aws s3api list-object-versions --bucket BUCKET_NAME --prefix PREFIX

# Restore specific version
aws s3api copy-object \
  --bucket BUCKET_NAME \
  --copy-source BUCKET_NAME/KEY?versionId=VERSION_ID \
  --key KEY
```

**Scenario 2: Bucket Deletion (if versioning disabled)**
- Restore from cross-region replica
- Re-run Glue jobs to regenerate curated data from raw archive

**RTO (Recovery Time Objective):** 4 hours  
**RPO (Recovery Point Objective):** 0 (continuous replication)

---

## Compliance and Audit

### Audit Requirements

**S3 Access Logging:**
- Enabled on all production buckets
- Logs stored in dedicated audit bucket
- Retention: 7 years

**CloudTrail Logging:**
- Data events enabled for all buckets
- Tracks all API calls (GetObject, PutObject, DeleteObject)
- Retention: 7 years

**Compliance Reports:**
- Quarterly review of bucket policies
- Annual security audit of access controls
- Monthly cost optimization review

---

## Cost Optimization

### Storage Optimization

**Lifecycle Transitions:**
- Raw data: Standard (90 days) → Glacier → Delete (365 days)
- Curated data: Standard (180 days) → Standard-IA (no expiration configured)
- Error/quarantine: Delete after 30 days
- Quality reports: No lifecycle policy configured (indefinite retention)
- Metadata/Lineage: No lifecycle policy configured (indefinite retention)

**Compression:**
- Parquet with Snappy: ~80% compression ratio vs. CSV
- Estimated savings: $100/month per TB

**Right-Sizing:**
- Monitor unused data in quarantine/error prefixes
- Delete after remediation window

### Query Optimization

**Partitioning:**
- Partition by year/month reduces scan size
- Typical query scans only relevant partitions (95% reduction)

**File Sizing:**
- Target: 128MB-256MB per Parquet file
- Prevents small file problem (slow queries)
- Use coalesce/repartition in Spark if needed

---

## FAQs

**Q: Why separate buckets for raw, curated, and metadata?**  
A: Separation enables different lifecycle policies, access controls, and simplifies governance. Raw data is immutable with short retention; curated data is long-term analytical; metadata is governance-critical.

**Q: Can I write directly to curated bucket?**  
A: No. Only the Glue ETL job should write to curated. This ensures all data passes through quality checks and transformations.

**Q: What if I need to reprocess historical data?**  
A: Copy files from `archive/` back to `landing/` and disable Glue job bookmarks for that run.

**Q: How do I query quarantine data?**  
A: Use Athena table `beauty_products_db.quarantine_beauty_products` or download directly from S3.

**Q: What's the difference between error and quarantine?**  
A: **Error** = malformed CSV, duplicates (structural issues). **Quarantine** = low quality score, anomalies (data quality issues).

---

## Related Documentation

- [Data Governance Charter](../governance/data-governance-charter.md)
- [ETL Job Failure Runbook](../runbooks/etl-job-failure.md)
- [CLIENT-DEPLOYMENT-GUIDE.md](CLIENT-DEPLOYMENT-GUIDE.md)

---

**Questions:** Contact #data-engineering on Slack
