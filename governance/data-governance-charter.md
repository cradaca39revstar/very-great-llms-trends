# Data Governance Charter
## Beauty Products Data Lake

**Version:** 1.0.0  
**Last Updated:** January 17, 2026  
**Status:** Active  

---

## 1. Executive Summary

This Data Governance Charter establishes the framework, roles, responsibilities, policies, and standards for the Beauty Products Data Lake. It aligns with DAMA-DMBOK principles to ensure data quality, security, compliance, and value realization from data assets.

---

## 2. Purpose and Scope

### 2.1 Purpose

- Establish clear decision rights and accountabilities for data management
- Define policies and standards for data quality, security, and compliance
- Enable trusted, high-quality data for business analytics and decision-making
- Ensure compliance with data protection regulations and company policies

### 2.2 Scope

**In Scope:**
- Beauty products sales data from CSV sources
- Raw, curated, and metadata zones in S3
- AWS Glue ETL pipelines and Data Catalog
- Amazon Athena query access
- Data quality metrics and monitoring

**Out of Scope:**
- Customer personally identifiable information (PII) - to be governed separately if added
- Real-time streaming data (batch processing only)
- Downstream BI tools (governed by BI team)

---

## 3. Governance Organization

### 3.1 Roles and Responsibilities

#### Data Governance Council
- **Chair:** Chief Data Officer (CDO)
- **Members:** VP Analytics, Director of Engineering, Data Architect, Legal Counsel
- **Responsibilities:**
  - Approve data governance policies and standards
  - Resolve escalated data-related disputes
  - Review governance metrics quarterly
  - Approve major schema changes

#### Data Steward - Beauty Products
- **Role Owner:** Analytics Manager
- **Responsibilities:**
  - Own data quality rules and thresholds
  - Review and remediate quarantined data
  - Approve schema changes and new data sources
  - Define business glossary terms
  - Monitor data quality trends
  - Coordinate with source system teams on data issues

#### Data Engineer - Pipeline Owner
- **Role Owner:** Senior Data Engineer
- **Responsibilities:**
  - Maintain ETL pipeline code and infrastructure
  - Implement data quality checks
  - Monitor job performance and failures
  - Version control and deployment
  - Incident response for pipeline failures

#### Data Architect
- **Role Owner:** Enterprise Data Architect
- **Responsibilities:**
  - Define data architecture and storage patterns
  - Review and approve schema designs
  - Ensure alignment with enterprise standards
  - Define data lineage and metadata requirements

#### Data Analyst - Primary Consumer
- **Role Owner:** Business Analysts (multiple)
- **Responsibilities:**
  - Query curated data for insights
  - Report data quality issues
  - Request new data fields or transformations
  - Validate business logic in transformations

---

### 3.2 RACI Matrix

| Activity | Data Steward | Data Engineer | Data Architect | Data Analyst | Governance Council |
|----------|-------------|---------------|----------------|--------------|-------------------|
| Define quality rules | **A** | C | C | C | I |
| ETL code changes | C | **A** | R | I | I |
| Schema changes | **A** | R | **A** | C | **A** (major changes) |
| Quality issue remediation | **A** | R | I | C | I |
| Infrastructure deployment | I | **A** | R | I | **A** (production) |
| Business glossary | **A** | I | C | C | I |
| Query optimization | C | R | **A** | **A** | I |
| Incident response | C | **A** | I | I | I (escalations) |

**Legend:** R = Responsible, A = Accountable, C = Consulted, I = Informed

---

## 4. Data Governance Policies

### 4.1 Data Quality Policy

**Policy Statement:** All data in the curated zone must meet minimum quality standards before being made available for business consumption.

**Standards:**
- Data quality score >= 0.70 for inclusion in curated zone
- Quality scores calculated based on defined validation rules
- Quality reports generated for every ETL job run
- Quarantine process for records scoring < 0.70

**Enforcement:**
- Automated quality checks in Glue ETL job
- CloudWatch alarms for quality score < 0.80 average
- Monthly quality review by Data Steward
- Root cause analysis for quality degradation

---

### 4.2 Data Retention Policy

**Policy Statement:** Data retention periods balance business needs, storage costs, and compliance requirements.

**Retention Periods:**

| Data Zone | Retention Period | Storage Class | Rationale |
|-----------|-----------------|---------------|-----------|
| Raw (Landing) | 90 days standard, then Glacier | S3 Standard → Glacier | Source fidelity, audit trail |
| Raw (Archive) | 1 year, then delete | Glacier | Reprocessing capability |
| Curated | 7 years | S3 Standard (6mo) → IA | Business analytics, compliance |
| Error/Quarantine | 30 days, then delete | S3 Standard | Issue resolution window |
| Quality Reports | 2 years | S3 Standard | Trend analysis |
| Metadata/Lineage | 5 years | S3 Standard | Audit and compliance |

**Enforcement:**
- S3 lifecycle policies configured in Terraform
- Annual review of retention requirements
- Legal hold process for litigation

---

### 4.3 Data Access Policy

**Policy Statement:** Access to data is granted based on role and business need, following least privilege principle.

**Access Levels:**

| Role | Raw Zone | Curated Zone | Metadata | Athena Query | Glue Jobs |
|------|----------|--------------|----------|--------------|-----------|
| Data Engineer | Read/Write | Read/Write | Read/Write | Read/Write | Execute |
| Data Analyst | No Access | Read | Read | Read | No Access |
| Data Steward | Read | Read/Write | Read/Write | Read/Write | View |
| BI Developer | No Access | Read | Read | Read | No Access |

**Enforcement:**
- IAM roles with specific S3 bucket permissions
- Athena query access via IAM role assumption
- AWS CloudTrail logging all access
- Quarterly access review

---

### 4.4 Data Privacy and Security Policy

**Policy Statement:** Data must be protected at rest and in transit; PII must be handled with additional controls.

**Security Controls:**
- Encryption at rest: AES-256 (S3 SSE)
- Encryption in transit: TLS 1.2+
- S3 bucket public access blocked
- VPC endpoints for Glue and Athena (production)
- IAM policies enforce least privilege
- CloudTrail logging enabled for audit

**PII Handling (future requirement):**
- Identify PII fields in source data
- Apply tokenization or masking in ETL
- Separate PII data to dedicated S3 bucket with enhanced controls
- Data classification tags applied

**Enforcement:**
- Terraform infrastructure as code enforces encryption
- Security audit every 6 months
- Penetration testing annually

---

### 4.5 Change Management Policy

**Policy Statement:** All changes to ETL code, infrastructure, and schemas must follow a controlled process.

**Change Categories:**

| Category | Examples | Approval Required | Testing Required |
|----------|----------|------------------|------------------|
| Minor | Bug fixes, performance tuning | Data Engineer | Unit tests |
| Moderate | New transformation rules, schema additions | Data Steward | Unit + Integration tests |
| Major | Architecture changes, new data sources | Governance Council | Full regression testing |

**Process:**
1. Change request submitted (Jira/ServiceNow ticket)
2. Impact analysis and testing plan
3. Approval obtained per category
4. Development in `dev` environment
5. Code review (2+ approvers)
6. Deployment to `staging` for validation
7. Production deployment (change window)
8. Post-deployment validation
9. Rollback plan documented

**Enforcement:**
- Git branching strategy (main, dev, feature branches)
- Pull request required for merge to main
- CI/CD pipeline enforces testing
- Deployment checklist required for production

---

### 4.6 Data Lineage Policy

**Policy Statement:** Data lineage must be captured and maintained to support impact analysis, compliance, and troubleshooting.

**Requirements:**
- Source-to-target mappings documented
- Glue job lineage captured in metadata tables
- Transformation version tracked in curated data
- Column-level lineage for sensitive fields (future)

**Artifacts:**
- `transformation_lineage` table in metadata database
- Source-to-target mapping spreadsheet
- Glue job DAG visualization in Glue Studio
- Business glossary linking terms to physical columns

**Enforcement:**
- ETL job writes lineage record for each run
- Quarterly lineage review and update
- Lineage verification in change impact analysis

---

## 5. Data Standards

### 5.1 Naming Conventions

**S3 Buckets:**
- Format: `{project}-{zone}-{region}-{environment}`
- Example: `very-great-products-raw-us-east-1-poc`

**S3 Prefixes:**
- Format: `{data_domain}/{data_type}/YYYY/MM/DD/`
- Example: `landing/beauty-products/2024/04/17/`

**Glue Databases:**
- Format: `{domain}_{zone}_db`
- Example: `beauty_products_db`

**Glue Tables:**
- Format: `{zone}_{entity_name}`
- Example: `curated_beauty_products`

**Glue Jobs:**
- Format: `{domain}-{function}-job`
- Example: `beauty-products-etl-job`

**Columns:**
- snake_case (lowercase with underscores)
- Descriptive, avoid abbreviations
- Example: `avg_unit_price_usd`, not `avgPrice`

---

### 5.2 Data Type Standards

| Business Type | Physical Type | Precision | Example |
|--------------|---------------|-----------|---------|
| Date | DATE | N/A | 2024-04-01 |
| Timestamp | TIMESTAMP | microseconds | 2024-04-01T12:34:56.123456Z |
| Currency | DECIMAL | (18,2) | 1234567.89 |
| Percentage (ratio) | DECIMAL | (5,4) | 0.1234 (12.34%) |
| Count/Quantity | INT or BIGINT | N/A | 12345 |
| Identifier | BIGINT or STRING | N/A | 1234567890 |
| Text | STRING | UTF-8 | Product Name |

---

### 5.3 Documentation Standards

**Required Documentation:**
- Schema definition with column descriptions
- Business glossary for domain terms
- Source-to-target mappings
- Transformation business rules
- Runbooks for operational procedures

**Documentation Format:**
- Markdown for text documents
- JSON for schema definitions
- Mermaid for diagrams
- SQL comments for query logic

**Documentation Location:**
- Git repository: `/docs`, `/schemas`, `/runbooks`
- S3 metadata bucket: `s3://{metadata-bucket}/documentation/`

---

## 6. Data Quality Framework

### 6.1 Quality Dimensions

Aligned with DAMA-DMBOK:

1. **Accuracy:** Data correctly represents reality
2. **Completeness:** Required fields are populated
3. **Consistency:** Data follows defined formats
4. **Validity:** Data conforms to business rules
5. **Uniqueness:** No duplicate records
6. **Timeliness:** Data is current and available within SLA

### 6.2 Quality Metrics

**Per-Record Metrics:**
- `data_quality_score`: 0.0000 to 1.0000
- `quality_flags`: Comma-separated list of issues

**Aggregate Metrics:**
- Pass rate: % of records with score >= 0.95
- Average quality score
- Issue breakdown by type
- Trend over time

### 6.3 Quality SLAs

| Metric | Target | Threshold | Action |
|--------|--------|-----------|--------|
| Pass Rate | >= 95% | < 90% | Alert Data Steward |
| Average Quality Score | >= 0.95 | < 0.80 | Escalate to Governance Council |
| Job Failure Rate | < 1% | >= 5% | Incident response |
| Data Freshness | < 4 hours | > 8 hours | Alert on-call engineer |

---

## 7. Compliance and Audit

### 7.1 Regulatory Compliance

**Applicable Regulations:**
- General Data Protection Regulation (GDPR) - if EU customers added
- California Consumer Privacy Act (CCPA) - if CA customers added
- SOX compliance for financial reporting (if public company)

**Compliance Controls:**
- Data classification and tagging
- Access logging and monitoring
- Data retention enforcement
- Privacy impact assessments for new data

### 7.2 Audit Requirements

**Audit Logs:**
- AWS CloudTrail: All API calls to S3, Glue, Athena
- Glue job logs: Transformation execution details
- S3 access logs: Object-level access tracking

**Audit Reports:**
- Quarterly data quality report
- Annual data governance effectiveness review
- Access review every 6 months
- Security audit annually

**Audit Retention:** 7 years for compliance

---

## 8. Metrics and KPIs

### 8.1 Operational Metrics

- ETL job success rate: Target > 99%
- Average job duration: Target < 15 minutes
- Data quality pass rate: Target >= 95%
- Query performance: Target < 5 seconds (standard queries)

### 8.2 Business Metrics

- Data coverage: 100% of source files processed
- User adoption: 10+ business users within 3 months
- Time to insight: Data available within 4 hours of source arrival
- Cost per GB stored: Track and optimize

### 8.3 Governance Maturity

**Current Maturity Level:** 1 (Initial/Ad Hoc)  
**Target Maturity Level:** 3 (Defined) within 6 months  
**Assessment Framework:** DAMA-DMBOK DCAM

**Evidence of Maturity:**
- Documented processes and policies ✓
- Defined roles and responsibilities ✓
- Quality monitoring and reporting ✓
- Lineage tracking ✓
- Metadata management ✓

---

## 9. Governance Review and Updates

### 9.1 Review Schedule

- **Monthly:** Data quality metrics review (Data Steward)
- **Quarterly:** Governance effectiveness review (Governance Council)
- **Annually:** Policy and charter comprehensive review

### 9.2 Charter Amendment Process

1. Proposed changes submitted to Governance Council
2. Impact analysis conducted
3. Stakeholder consultation
4. Council vote (majority approval required)
5. Updated charter published
6. Training on changes provided

---

## 10. Approval and Acknowledgment

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Chief Data Officer | [Name] | [Signature] | [Date] |
| VP Analytics | [Name] | [Signature] | [Date] |
| Director of Engineering | [Name] | [Signature] | [Date] |
| Data Steward | [Name] | [Signature] | [Date] |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2026-01-17 | Data Governance Team | Initial charter creation |

---

**Questions or Feedback:** Contact data-governance@company.com
