# Beauty Products Data Lake

**Version:** 1.0.0
**Status:** Production Ready
**Framework:** DAMA-DMBOK Aligned

---

## Overview

The Beauty Products Data Lake is an AWS-based data pipeline that ingests, transforms, and curates beauty product sales data using S3, AWS Glue, and Athena. The solution implements comprehensive data quality checks, governance controls, and metadata management aligned with DAMA-DMBOK best practices.

### Key Features

- **End-to-End ETL Pipeline:** Raw CSV to curated Parquet with Snappy compression
- **Data Quality Framework:** 20+ validation rules with per-record quality scoring
- **DAMA-DMBOK Alignment:** Full governance, lineage, and metadata management
- **Automated Monitoring:** CloudWatch alarms and dashboards
- **Partitioned Storage:** Optimized query performance with year/month partitioning
- **Comprehensive Testing:** Unit, integration, and sample data validation

---

## Architecture

```
CSV Source → S3 Raw → Glue ETL → S3 Curated → Athena Queries
                           ↓
                    Quality Reports
                    Error Handling
                    Lineage Tracking
```

### Components

| Component     | Purpose                 | Technology       |
| ------------- | ----------------------- | ---------------- |
| Raw Zone      | Immutable source data   | S3 Standard      |
| Curated Zone  | Cleaned, validated data | S3 + Parquet     |
| ETL Pipeline  | Data transformation     | AWS Glue Spark   |
| Data Catalog  | Schema metadata         | AWS Glue Catalog |
| Query Engine  | SQL analytics           | Amazon Athena    |
| Orchestration | Scheduling              | EventBridge      |
| Monitoring    | Alerts & dashboards     | CloudWatch       |

---

## Data Flow

### 1. Ingestion

- CSV files uploaded to `s3://very-great-products-raw-us-east-1-poc/landing/beauty-products/YYYY/MM/DD/`
- EventBridge triggers Glue job at 2 AM UTC daily

### 2. Transformation

- Parse and normalize all fields
- Calculate quality score for each record
- Apply deduplication logic
- Route records by quality (pass/warn/fail)

### 3. Output

- **Curated:** High-quality records → `s3://.../curated/beauty-products/year=YYYY/month_num=MM/`
- **Quarantine:** Failed records → `s3://.../quarantine/beauty-products/YYYY/MM/DD/`
- **Error:** Malformed records → `s3://.../error/beauty-products/YYYY/MM/DD/`
- **Quality Reports:** JSON metrics → `s3://.../quality-reports/beauty-products/YYYY/MM/DD/`

---

## Schema

### Source CSV Columns

- Month, Product Id, Product Name, Shop Name
- L1 category, L2 category, L3 category
- Item Sold, Revenue, Avg. Unit Price, MoM Growth %

### Curated Parquet Columns

**Business Data:**

- `month` (DATE), `product_id` (BIGINT), `product_name` (STRING)
- `shop_name` (STRING), category fields (STRING)
- `item_sold` (INT), `revenue_usd` (DECIMAL), `avg_unit_price_usd` (DECIMAL)
- `mom_growth_pct` (DECIMAL)

**Governance Metadata:**

- `source_file`, `source_record_number`, `processed_timestamp`
- `transformation_version`, `data_quality_score`, `quality_flags`
- `created_by`, `record_hash`

**Partitions:**

- `year` (INT), `month_num` (INT)

Full schema: [`schemas/curated_beauty_products_v1.json`](schemas/curated_beauty_products_v1.json)

---

## Data Quality

### Quality Dimensions

- **Accuracy:** Data represents reality
- **Completeness:** Required fields populated
- **Consistency:** Follows defined formats
- **Validity:** Conforms to business rules
- **Uniqueness:** No duplicates
- **Timeliness:** Data fresh (< 4 hours)

### Scoring System

**Formula:** Start at 1.0000, subtract penalties

| Issue                | Penalty | Description                    |
| -------------------- | ------- | ------------------------------ |
| INVALID_DATE         | -0.20   | Date cannot be parsed          |
| SYNTHETIC_PRODUCT_ID | -0.15   | Product ID invalid, hash used  |
| MISSING_PRODUCT_NAME | -0.20   | Product name empty             |
| INVALID_REVENUE      | -0.15   | Revenue not parseable          |
| INVALID_AVG_PRICE    | -0.10   | Avg price not parseable        |
| MISSING_ITEMS        | -0.10   | Item sold count invalid        |
| SUSPICIOUS_GROWTH    | -0.05   | Growth outside -100% to +1000% |
| DUPLICATE_RECORD     | -0.10   | Duplicate natural key          |

**Thresholds:**

- `>= 0.95`: PASS → Curated zone
- `0.70 - 0.95`: WARN → Curated zone (flagged)
- `< 0.70`: FAIL → Quarantine zone

---

## Quick Start

### Prerequisites

- AWS Account with appropriate permissions
- Terraform >= 1.0
- AWS CLI configured
- Python 3.10+ (for local testing)

### Deployment

1. **Clone Repository**

   ```bash
   git clone <repo-url>
   cd beauty-products-data-lake
   ```
2. **Configure Variables**

   ```bash
   cd terraform/
   cp terraform.tfvars.example terraform.tfvars
   # Edit variables (environment, region, alert email)
   ```
3. **Deploy Infrastructure**

   ```bash
   terraform init
   terraform plan
   terraform apply
   ```
4. **Upload Test Data**

   ```bash
   aws s3 cp tests/sample-data/valid_input.csv \
     s3://very-great-products-raw-us-east-1-poc/landing/beauty-products/$(date +%Y/%m/%d)/
   ```
5. **Trigger Job**

   ```bash
   aws glue start-job-run --job-name beauty-products-etl-job
   ```
6. **Query Results**

   ```sql
   -- In Athena
   SELECT * FROM beauty_products_db.curated_beauty_products LIMIT 10;
   ```

Full deployment guide: [`deployment-checklist.md`](deployment-checklist.md)

---

## Usage

### Querying Data with Athena

**Basic Query:**

```sql
SELECT product_name, shop_name, SUM(revenue_usd) as total_revenue
FROM beauty_products_db.curated_beauty_products
WHERE data_quality_score >= 0.95
  AND year = 2024
GROUP BY product_name, shop_name
ORDER BY total_revenue DESC
LIMIT 10;
```

**Using Views:**

```sql
-- High-quality data only
SELECT * FROM beauty_products_db.vw_high_quality_products
WHERE month >= DATE '2024-01-01';

-- Sales by category
SELECT * FROM beauty_products_db.vw_sales_by_category_month
WHERE l1_category = 'Beauty & Personal Care'
ORDER BY total_revenue_usd DESC;
```

More examples: [`athena-views.sql`](athena-views.sql)

---

### Monitoring

**CloudWatch Dashboard:**

- URL: AWS Console → CloudWatch → Dashboards → `beauty-products-pipeline-metrics`
- Metrics: Job success rate, quality score trend, record counts, job duration

**Alarms:**

- `beauty-products-job-failure`: Job state = FAILED
- `beauty-products-low-quality`: Avg quality score < 0.80
- `beauty-products-high-error-rate`: Error rate > 5%

**Quality Reports:**

```bash
# Latest report
aws s3 ls s3://very-great-products-processed-us-east-1-poc/quality-reports/beauty-products/ \
  --recursive | sort | tail -1
```

---

### Troubleshooting

**Job Failed?**

- See: [`runbooks/etl-job-failure.md`](runbooks/etl-job-failure.md)

**Low Quality Score?**

- See: [`runbooks/data-quality-investigation.md`](runbooks/data-quality-investigation.md)

**Schema Changed?**

- See: [`runbooks/schema-evolution.md`](runbooks/schema-evolution.md)

**Check Job Logs:**

```bash
aws logs tail /aws-glue/jobs/beauty-products-etl-job --follow
```

**Check Data Freshness:**

```sql
SELECT MAX(processed_timestamp) as last_load 
FROM beauty_products_db.curated_beauty_products;
```

---

## Project Structure

```
.
├── terraform/                  # Infrastructure as Code
│   ├── s3-buckets.tf          # S3 bucket definitions
│   ├── iam.tf                 # IAM roles and policies
│   ├── glue-catalog.tf        # Glue databases and tables
│   ├── glue-jobs.tf           # Glue ETL job config
│   ├── glue-crawlers.tf       # Glue crawler config
│   ├── eventbridge.tf         # Scheduling
│   ├── cloudwatch.tf          # Monitoring and alarms
│   ├── sns.tf                 # Notifications
│   ├── variables.tf           # Input variables
│   ├── outputs.tf             # Output values
│   └── provider.tf            # Terraform config
│
├── scripts/                    # ETL code
│   └── beauty_products_etl.py # Main Glue ETL script
│
├── tests/                      # Test suite
│   ├── test_transformations.py # Unit tests
│   ├── integration_test.py    # Integration tests
│   └── sample-data/           # Test datasets
│       ├── valid_input.csv
│       └── malformed_input.csv
│
├── schemas/                    # Schema definitions
│   ├── curated_beauty_products_v1.json
│   └── quality_report_v1.json
│
├── governance/                 # Governance documents
│   ├── data-governance-charter.md
│   ├── business-glossary.csv
│   └── source-to-target-mapping.xlsx
│
├── runbooks/                   # Operational guides
│   ├── etl-job-failure.md
│   ├── schema-evolution.md
│   └── data-quality-investigation.md
│
├── athena-views.sql           # Athena view definitions
├── deployment-checklist.md    # Deployment guide
└── README.md                  # This file
```

---

## Configuration

### Environment Variables

Set via Terraform variables or Glue job parameters:

| Variable                | Description                         | Default                   |
| ----------------------- | ----------------------------------- | ------------------------- |
| `environment`         | Environment name (dev/staging/prod) | `poc`                   |
| `aws_region`          | AWS region for resources            | `us-east-1`             |
| `alert_email`         | Email for CloudWatch alerts         | `data-team@example.com` |
| `DQ_PASS_THRESHOLD`   | Quality score pass threshold        | `0.95`                  |
| `DQ_WARN_THRESHOLD`   | Quality score warning threshold     | `0.70`                  |
| `ANOMALY_REVENUE_MAX` | Revenue anomaly threshold           | `10000000`              |
| `ANOMALY_ITEMS_MAX`   | Items sold anomaly threshold        | `1000000`               |

---

## Testing

### Run Unit Tests

```bash
cd tests/
pytest test_transformations.py -v
```

### Run Integration Tests

```bash
pytest integration_test.py -v
```

### Test with Sample Data

```bash
# Upload sample file
aws s3 cp tests/sample-data/valid_input.csv \
  s3://very-great-products-raw-us-east-1-poc/landing/beauty-products/test/

# Run job
aws glue start-job-run --job-name beauty-products-etl-job

# Check results
# (See queries in deployment-checklist.md)
```

---

## Performance

### Current Benchmarks

- **File Size:** 10K records (~ 2MB CSV)
- **Job Duration:** ~ 5-8 minutes
- **Worker Config:** G.1X, 2 workers
- **Throughput:** ~ 2,000 records/minute
- **Query Performance:** < 5 seconds (standard aggregations)

### Optimization Tips

- Increase workers for files > 1GB
- Use G.2X workers for complex transformations
- Add partition pruning to queries (filter by year/month)
- Use views for common query patterns

---

## Cost Estimation

**Monthly Costs (10K records/day):**

- S3 Storage: ~ $5
- Glue Job Runs: ~ $30 (30 runs × $0.44/DPU-hour × 2 DPUs × 0.15 hours)
- Athena Queries: ~ $10 (100 queries × 100MB scanned)
- CloudWatch Logs: ~ $2
- **Total:** ~ $50/month

_Costs will vary based on data volume and query frequency_

---

## Security

### Data Protection

- **Encryption at Rest:** AES-256 (S3 SSE)
- **Encryption in Transit:** TLS 1.2+
- **Public Access:** Blocked on all buckets
- **IAM:** Least privilege principle
- **Logging:** CloudTrail enabled

### Compliance

- GDPR ready (PII handling if needed)
- SOX controls for financial data
- Audit trail maintained (7 years)

---

## Governance (DAMA-DMBOK)

### Implemented DAMA Knowledge Areas

1. **Data Governance:** Charter, roles, policies
2. **Data Quality:** 20+ rules, scoring, monitoring
3. **Data Architecture:** Medallion pattern (raw → curated)
4. **Data Storage & Operations:** Parquet, partitioning, lifecycle
5. **Metadata Management:** Glue Catalog, business glossary
6. **Data Lineage:** Job tracking, source-to-target mapping
7. **Data Integration:** ETL jobs, standard formats
8. **Master Data Management:** Product/shop reference data (future)

Full governance documentation: [`governance/data-governance-charter.md`](governance/data-governance-charter.md)

---

## Roadmap

### Phase 2 (Future Enhancements)

- [ ] Incremental processing (CDC)
- [ ] Real-time streaming (Kinesis)
- [ ] ML model integration (SageMaker)
- [ ] Advanced anomaly detection
- [ ] Data catalog search (AWS DataZone)
- [ ] Column-level lineage
- [ ] Data quality dashboard (QuickSight)
- [ ] API layer (API Gateway + Lambda)

---

## Contributing

### Development Workflow

1. Create feature branch: `git checkout -b feature/my-feature`
2. Make changes and test locally
3. Run linters and tests: `pytest tests/`
4. Commit with descriptive message
5. Push and create pull request
6. Get 2+ approvals
7. Merge to main

### Code Standards

- Python: PEP 8, type hints preferred
- Terraform: Standard formatting (`terraform fmt`)
- Documentation: Markdown with clear headings
- Tests: Unit tests for all transformations

---

## Support

### Contacts

- **Data Engineering Team:** #data-engineering (Slack)
- **Data Steward:** data-steward@company.com
- **On-Call:** PagerDuty or #data-oncall (Slack)

### Resources

- [DAMA-DMBOK Framework](https://www.dama.org/cpages/body-of-knowledge)
- [AWS Glue Documentation](https://docs.aws.amazon.com/glue/)
- [Athena Best Practices](https://docs.aws.amazon.com/athena/latest/ug/performance-tuning.html)

---

## License

[Your License Here]

---

## Changelog

### v1.0.0 (2026-01-17)

- Initial production release
- Complete ETL pipeline with quality framework
- Full DAMA-DMBOK alignment
- Comprehensive testing and documentation
