# Beauty Products Data Lake

**Version:** 1.0.0  
**Status:** Production Ready  
**Framework:** DAMA-DMBOK Aligned  
**Handoff Date:** _______________

---

## For Clients

**Welcome to the Beauty Products Data Lake!** This system is ready for production use and includes comprehensive documentation for deployment, operations, and support.

### Quick Links

- 📦 **[Client Handoff Package](CLIENT-HANDOFF-PACKAGE.md)** - Executive summary and handoff information
- 🏗️ **[Data Lake Architecture](docs/ARCHITECTURE.md)** - Data lake system architecture and components
- 🤖 **[LLM Trending Products Architecture](docs/LLM-TRENDING-PRODUCTS-ARCHITECTURE.md)** - AI-powered trending products report generator
- 🚀 **[Deployment Guide](docs/CLIENT-DEPLOYMENT-GUIDE.md)** - Step-by-step deployment instructions
- ⚙️ **[Operations Guide](docs/CLIENT-OPERATIONS-GUIDE.md)** - Daily operations and support procedures
- 📋 **[Handoff Checklist](docs/CLIENT-HANDOFF-CHECKLIST.md)** - Knowledge transfer tracking
- 📚 **[Documentation Index](docs/INDEX.md)** - Complete documentation catalog

### Getting Started

1. **New to the system?** Start with the [Client Handoff Package](CLIENT-HANDOFF-PACKAGE.md)
2. **Deploying?** Follow the [Deployment Guide](docs/CLIENT-DEPLOYMENT-GUIDE.md)
3. **Operating?** Review the [Operations Guide](docs/CLIENT-OPERATIONS-GUIDE.md)
4. **Need help?** Check the [Documentation Index](docs/INDEX.md) or [Operations Guide Support section](docs/CLIENT-OPERATIONS-GUIDE.md#support-contacts)

### Support

For questions or issues:
- Review the [Operations Guide](docs/CLIENT-OPERATIONS-GUIDE.md) troubleshooting section
- Check [Runbooks](runbooks/) for specific scenarios
- Contact your system administrator

---

## Overview

The Beauty Products Data Lake is an AWS-based data pipeline that ingests, transforms, and curates beauty product sales data using S3, AWS Glue, and Athena. The solution implements comprehensive data quality checks, governance controls, and metadata management aligned with DAMA-DMBOK best practices.

### LLM Trending Products System (V2 – Product Innovation Engine)

**V2**: AI-powered **Product Innovation Report** generator. Uses real top-5 market data as context to generate one new brand proposal and five AI product ideas, with Titan-generated concept images.

**Key Features**:
- Natural language queries (English) by L2 category
- **Market context**: Athena top 5 real products (revenue, growth, rank)
- **Brand proposal**: One AI-generated brand (name, tagline, story, values, positioning)
- **Product ideas**: Five AI product concepts with descriptions, price, ingredients, trends
- **AI images**: Amazon Titan Image Generator v2 for each product concept
- Professional PDF reports in ~15–22 seconds
- Secure authentication via AWS Cognito
- Scraper Lambda disabled by default (`enable_scraper_lambda = false`)

**Documentation**:
- Architecture: [`docs/LLM-TRENDING-PRODUCTS-ARCHITECTURE.md`](docs/LLM-TRENDING-PRODUCTS-ARCHITECTURE.md)
- Deployment: [`terraform/README-LLM.md`](terraform/README-LLM.md)
- User Guide: See [LLM Architecture Doc - User Guide Section](docs/LLM-TRENDING-PRODUCTS-ARCHITECTURE.md#user-guide)
- Frontend (UI): [`frontend/README.md`](frontend/README.md) — local dev and Amplify Hosting

**How to test the agent**: Prerequisites: Terraform applied, Lambda deployed (`.\scripts\deploy-lambda-llm.ps1`), and a Cognito test user created once (see [Testing in terraform/README-LLM.md](terraform/README-LLM.md#testing)). Then run `.\scripts\call-api-llm.ps1` from the project root.

**Quick Start**:
```bash
# 1. Enable Bedrock models in AWS Console
# 2. Configure terraform.tfvars
enable_llm_system = true

# 3. Deploy infrastructure
cd terraform/
terraform apply

# 4. Deploy Lambda code (PowerShell)
.\scripts\deploy-lambda-llm.ps1

# 5. Create Cognito test user once, then test the agent
.\scripts\call-api-llm.ps1
```

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

- CSV files uploaded to `s3://very-great-products-raw-us-east-1-{environment}/landing/beauty-products/YYYY/MM/DD/` (where `{environment}` is `dev`, `staging`, `prod`, or `poc`)
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

**Note:** DUPLICATE_RECORD is handled separately in the deduplication step (Step 4) and does not affect quality score. Duplicate records are routed to the error bucket.

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
   # Replace {environment} with your environment (dev, staging, prod, poc)
   aws s3 cp tests/sample-data/valid_input.csv \
     s3://very-great-products-raw-us-east-1-{environment}/landing/beauty-products/$(date +%Y/%m/%d)/
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

**Detailed Guides:**
- [Client Deployment Guide](docs/CLIENT-DEPLOYMENT-GUIDE.md) - Step-by-step deployment instructions

---

## Usage

### Querying Data with Athena

**Workgroup:** Use workgroup `beauty-products-athena-{environment}` (e.g. `beauty-products-athena-poc` for default). Get it via `terraform output -raw athena_workgroup_name`.

**Result location:** Query results are written to `s3://<metadata-bucket>/athena-results/`. The exact path is in `terraform output athena_workgroup_result_location`. Set the workgroup in the Athena Query Editor (workgroup selector) or use `--work-group` with the AWS CLI before running queries.

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
# Latest report (replace {environment} with your environment)
aws s3 ls s3://very-great-products-processed-us-east-1-{environment}/quality-reports/beauty-products/ \
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
├── docs/                      # Documentation
│   ├── ARCHITECTURE.md        # System architecture
│   ├── CLIENT-DEPLOYMENT-GUIDE.md  # Deployment guide
│   ├── CLIENT-OPERATIONS-GUIDE.md  # Operations guide
│   ├── CLIENT-HANDOFF-CHECKLIST.md # Handoff checklist
│   ├── INDEX.md               # Documentation index
│   ├── diagrams/              # Architecture diagrams
│   └── ...                    # Additional documentation
│
├── athena-views.sql           # Athena view definitions
├── CLIENT-HANDOFF-PACKAGE.md  # Executive handoff summary
└── README.md                  # This file
```

---

## Configuration

### Environment Variables

Set via Terraform variables or Glue job parameters:

| Variable                | Description                             | Default                   |
| ----------------------- | --------------------------------------- | ------------------------- |
| `environment`         | Environment name (dev/staging/prod/poc) | `poc`                   |
| `aws_region`          | AWS region for resources                | `us-east-1`             |
| `alert_email`         | Email for CloudWatch alerts             | `data-team@example.com` |
| `DQ_PASS_THRESHOLD`   | Quality score pass threshold            | `0.95`                  |
| `DQ_WARN_THRESHOLD`   | Quality score warning threshold         | `0.70`                  |
| `ANOMALY_REVENUE_MAX` | Revenue anomaly threshold               | `10000000`              |
| `ANOMALY_ITEMS_MAX`   | Items sold anomaly threshold            | `1000000`               |

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
# Upload sample file (replace {environment} with your environment)
aws s3 cp tests/sample-data/valid_input.csv \
  s3://very-great-products-raw-us-east-1-{environment}/landing/beauty-products/test/

# Run job
aws glue start-job-run --job-name beauty-products-etl-job

# Check results
# (See queries in docs/CLIENT-DEPLOYMENT-GUIDE.md and athena-views.sql)
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
2. Make changes and test locally using Docker (see `docs/testing-with-docker.md`)
3. Run integration tests: `pytest tests/integration_test.py -v`
4. Commit with descriptive message
5. Push and create pull request
6. Get 2+ approvals
7. Merge to main

### Code Standards

- Python: PEP 8, type hints preferred
- Terraform: Standard formatting (`terraform fmt`)
- Documentation: Markdown with clear headings
- Tests: Unit tests for all transformations

**Note:** For client deployments, refer to [Client Deployment Guide](docs/CLIENT-DEPLOYMENT-GUIDE.md) instead of development procedures.

---

## Support

### Client Support

- **Operations Guide**: [docs/CLIENT-OPERATIONS-GUIDE.md](docs/CLIENT-OPERATIONS-GUIDE.md) - Daily operations and troubleshooting
- **Documentation Index**: [docs/INDEX.md](docs/INDEX.md) - Complete documentation catalog
- **Runbooks**: [runbooks/](runbooks/) - Detailed operational procedures

### External Resources

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
