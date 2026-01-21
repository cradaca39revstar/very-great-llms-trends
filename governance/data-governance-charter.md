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

- **Role Owner:** Data AI Engineer
- **Responsibilities:**
  - Maintain ETL pipeline code and infrastructure
  - Implement data quality checks
  - Monitor job performance and failures
  - Version control and deployment
  - Incident response for pipeline failures
    -  - ---
