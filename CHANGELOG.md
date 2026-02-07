# Changelog

## Beauty Products Data Lake

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.0.0] - 2026-02-03

### Changed – LLM System V2 (Product Innovation Engine)

- **Report model**: From “top 5 existing products” to “market context + 1 brand + 5 product ideas” with AI-generated images.
- **Backend**: New Bedrock prompts (`generate_brand_proposal`, `generate_product_ideas`), Titan Image Generator for product concept images, single orchestrator flow (no scraper).
- **PDF**: Title page, market context table, brand proposal page, product idea pages with embedded Titan images.
- **API**: Success response includes `brand_name`; error responses use `HTTPStatus`, `request_id`, and `msg_code` (TRD001–TRD007).
- **Frontend**: New types (`MarketProduct`, `BrandProposal`, `ProductIdea`), `BrandProposalCard`, `MarketContextSection`, `ProductIdeaCard`, and styles.
- **Terraform**: Titan IAM permission for `amazon.titan-image-generator-v2:0`; scraper Lambda and invoke-scraper policy gated by `enable_scraper_lambda` (default `false`); orchestrator env no longer includes `SCRAPER_FUNCTION_NAME` or `KNOWLEDGE_BASE_ID`.
- **Lambda**: Removed `requests` from requirements; added `Pillow` for PDF image handling.

### Removed

- Scraper Lambda from default deploy (`enable_scraper_lambda = false`).
- Legacy PDF helpers: `add_product_page`, `parse_trend_text` from `pdf_generator.py`.
- Legacy Bedrock helpers: brand-name/product-search/trends prompts and related functions from `bedrock_helper.py`.

---

## [1.0.0] - 2026-01-17

### Added - Initial Production Release

#### Infrastructure

- AWS S3 buckets for raw, curated, and metadata zones
- IAM roles and policies with least privilege access
- AWS Glue Data Catalog with 6 tables across 2 databases
- AWS Glue ETL job (`beauty-products-etl-job`)
- AWS Glue Crawlers for raw zone and quality reports
- EventBridge scheduling (daily at 2 AM UTC)
- CloudWatch alarms and monitoring dashboard
- SNS topic for alerts

#### ETL Pipeline

- Complete ETL script (`beauty_products_etl.py`) with:
  - 20+ data quality validation rules
  - Per-record quality scoring (0.0000-1.0000)
  - Deduplication logic based on natural key
  - Quality-based routing (pass/warn/fail)
  - Anomaly detection (revenue > $10M, items > 1M)
  - Error handling for malformed CSV rows
  - Lineage tracking for every job run

#### Data Quality Framework

- Quality score calculation with configurable penalties
- Three quality tiers: Pass (>=0.95), Warn (0.70-0.95), Fail (<0.70)
- Eight quality flag types: INVALID_DATE, SYNTHETIC_PRODUCT_ID, MISSING_PRODUCT_NAME, INVALID_REVENUE, INVALID_AVG_PRICE, MISSING_ITEMS, SUSPICIOUS_GROWTH, DUPLICATE_RECORD
- JSON quality reports for each job run
- Quarantine and error routing with reasons

#### Schema

- Raw table: 11 columns (all STRING) for schema-on-read
- Curated table: 21 columns (business + governance metadata) with Parquet format
- Partitioning by year and month for query optimization
- Versioned schema definitions (JSON)

#### Governance (DAMA-DMBOK Aligned)

- Data Governance Charter with roles and policies
- Business Glossary (30+ terms)
- Source-to-Target Mapping (11 source columns → 21 target columns)
- Data retention policies (7 years curated, 1 year raw)
- Data lineage tracking
- Audit trail via CloudTrail

#### Documentation

- README with quick start guide
- Deployment checklist (22 steps)
- Three operational runbooks:
  - ETL Job Failure Recovery
  - Schema Evolution
  - Data Quality Investigation
- S3 bucket structure documentation
- Quality report template
- Athena views and query examples

#### Testing

- Unit tests for all transformation functions
- Integration tests for end-to-end pipeline
- Sample data files (valid and malformed)
- Performance benchmarks documented

#### Athena Views

- `vw_high_quality_products` - Filter for production analytics
- `vw_sales_by_category_month` - Aggregated sales metrics
- `vw_quality_trends` - Track quality over time
- `vw_product_performance` - Product lifetime metrics
- `vw_shop_leaderboard` - Rank shops by performance

#### Monitoring

- CloudWatch dashboard: `beauty-products-pipeline-metrics`
- Three CloudWatch alarms:
  - Job failure detection
  - Low quality score alert (< 0.80)
  - High error rate alert (> 5%)
- Quality report generation for every job run

### Technical Details

#### Dependencies

- AWS Glue 4.0 (Python 3.10, Spark 3.3)
- Terraform >= 1.0
- boto3 (for S3 operations in ETL)
- PySpark (Glue managed)

#### Performance

- Worker type: G.1X (2 workers)
- Average job duration: 5-8 minutes (10K records)
- Throughput: ~2,000 records/minute
- Storage compression: ~80% (Parquet/Snappy vs CSV)

#### Security

- Encryption at rest: AES-256 (SSE-S3)
- Encryption in transit: TLS 1.2+
- S3 public access: Blocked
- IAM: Least privilege principle
- CloudTrail: Enabled for audit

## Version Numbering Convention

**Format:** MAJOR.MINOR.PATCH

- **MAJOR:** Breaking changes (partition key changes, data model restructuring)
- **MINOR:** Additive changes (new columns, new transformations, new features)
- **PATCH:** Bug fixes, performance improvements, documentation updates

**Examples:**

- Add new column: v1.0.0 → v1.1.0
- Fix currency parsing bug: v1.1.0 → v1.1.1
- Change partition strategy: v1.1.1 → v2.0.0

---

## Migration Notes

### From v0.x to v1.0.0

- Initial release - no migration needed
- First production deployment

---

## Known Issues

### v1.0.0

None at release time.

---

## Deprecations

### v1.0.0

None at release time.

---

## Contributors

- Revstar DATA AI Team

---

## Related Links

- [DAMA-DMBOK Framework](https://www.dama.org/cpages/body-of-knowledge)
- [Project Repository](https://github.com/your-org/beauty-products-data-lake)

---

**Note:** For detailed changes within a version, see Git commit history.
