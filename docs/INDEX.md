# Documentation Index
## Beauty Products Data Lake

**Version:** 1.0.0  
**Last Updated:** January 26, 2026

---

## Overview

This index organizes all documentation for the Beauty Products Data Lake by category and purpose. Use this guide to quickly find the information you need.

---

## Getting Started

**For New Users:**
1. Start with [README.md](../README.md) for project overview
2. Review [CLIENT-HANDOFF-PACKAGE.md](../CLIENT-HANDOFF-PACKAGE.md) for executive summary
3. Read [ARCHITECTURE.md](ARCHITECTURE.md) to understand the system
4. Follow [CLIENT-DEPLOYMENT-GUIDE.md](CLIENT-DEPLOYMENT-GUIDE.md) for deployment

**For Operations:**
1. Review [CLIENT-OPERATIONS-GUIDE.md](CLIENT-OPERATIONS-GUIDE.md) for daily tasks
2. Bookmark [Runbooks](../runbooks/) for troubleshooting
3. Reference [CLIENT-HANDOFF-CHECKLIST.md](CLIENT-HANDOFF-CHECKLIST.md) for handoff activities

---

## Documentation Categories

### 1. Getting Started

Essential documents for understanding and deploying the system.

| Document | Description | Audience |
|----------|-------------|----------|
| [README.md](../README.md) | Main project overview, features, and quick start | All users |
| [CLIENT-HANDOFF-PACKAGE.md](../CLIENT-HANDOFF-PACKAGE.md) | Executive summary and handoff information | Management, Project Leads |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Data Lake system architecture, components, and data flow | Technical teams |
| [LLM-TRENDING-PRODUCTS-ARCHITECTURE.md](LLM-TRENDING-PRODUCTS-ARCHITECTURE.md) | LLM Trending Products Report Generator architecture | Technical teams, Stakeholders |
| [CLIENT-DEPLOYMENT-GUIDE.md](CLIENT-DEPLOYMENT-GUIDE.md) | Step-by-step deployment instructions | DevOps, Engineers |
| [AMPLIFY-CLIENT-LINK.md](AMPLIFY-CLIENT-LINK.md) | Generate client link via AWS Amplify Hosting (LLM frontend) | DevOps, Project leads |
| [CLIENT-HANDOFF-CHECKLIST.md](CLIENT-HANDOFF-CHECKLIST.md) | Knowledge transfer tracking checklist | Project managers |

---

### 2. Operations

Daily operations, maintenance, and support procedures.

| Document | Description | Audience |
|----------|-------------|----------|
| [CLIENT-OPERATIONS-GUIDE.md](CLIENT-OPERATIONS-GUIDE.md) | Daily operations, monitoring, and common tasks | Operations team |
| [runbooks/etl-job-failure.md](../runbooks/etl-job-failure.md) | ETL job failure recovery procedures | Operations, Engineers |
| [runbooks/data-quality-investigation.md](../runbooks/data-quality-investigation.md) | Data quality issue investigation | Data stewards, Analysts |
| [runbooks/schema-evolution.md](../runbooks/schema-evolution.md) | Schema change procedures | Engineers, Data architects |
| [runbooks/validation-and-testing.md](../runbooks/validation-and-testing.md) | Testing and validation (data quality, crawlers, Athena, dashboard, LLM API) | QA, Engineers |

---

### 3. Technical Reference

Technical specifications, schemas, and code documentation.

| Document | Description | Audience |
|----------|-------------|----------|
| [schemas/curated_beauty_products_v1.json](../schemas/curated_beauty_products_v1.json) | Curated table schema definition | Engineers, Analysts |
| [schemas/quality_report_v1.json](../schemas/quality_report_v1.json) | Quality report schema definition | Engineers, Analysts |
| [athena-views.sql](../athena-views.sql) | Athena SQL view definitions | Analysts, Data engineers |
| [s3-bucket-structure.md](s3-bucket-structure.md) | S3 bucket organization and structure | Engineers, Operations |
| [testing-with-docker.md](testing-with-docker.md) | Docker-based testing procedures | Engineers, QA |
| [quality-report-template.json](quality-report-template.json) | Quality report JSON template | Engineers, Analysts |

---

### 4. Governance

Data governance, business definitions, and compliance documentation.

| Document | Description | Audience |
|----------|-------------|----------|
| [governance/data-governance-charter.md](../governance/data-governance-charter.md) | Data governance framework and policies | Data stewards, Management |
| [governance/business-glossary.csv](../governance/business-glossary.csv) | Business terms and definitions | All users |
| [governance/source-to-target-mapping.xlsx](../governance/source-to-target-mapping.xlsx) | Data lineage and mapping | Data architects, Analysts |
| [runbooks/lake-formation-security-review.md](../runbooks/lake-formation-security-review.md) | Security review procedures | Security, Engineers |

---

### 5. Code Documentation

Source code, infrastructure, and test documentation.

| Document | Description | Audience |
|----------|-------------|----------|
| [scripts/beauty_products_etl.py](../scripts/beauty_products_etl.py) | Main ETL script with inline documentation | Engineers |
| [scripts/utils/](../scripts/utils/) | Utility modules (logger, metrics, audit) | Engineers |
| [terraform/](../terraform/) | Infrastructure as Code (Terraform) | DevOps, Engineers |
| [tests/integration_test.py](../tests/integration_test.py) | Integration test suite | Engineers, QA |
| [tests/sample-data/](../tests/sample-data/) | Sample test data files | Engineers, QA |
| [requirements.txt](../requirements.txt) | Python dependencies | Engineers |

---

### 6. Project Management

Project history, changes, and planning documents.

| Document | Description | Audience |
|----------|-------------|----------|
| [CHANGELOG.md](../CHANGELOG.md) | Version history and changes | All users |
| [CLIENT-HANDOFF-PACKAGE.md](../CLIENT-HANDOFF-PACKAGE.md) | Handoff summary and deliverables | Management, Project leads |

---

## Quick Reference by Task

### I want to...

**Deploy the system:**
→ [CLIENT-DEPLOYMENT-GUIDE.md](CLIENT-DEPLOYMENT-GUIDE.md)

**Get a client link for the LLM Trending Products app:**
→ [AMPLIFY-CLIENT-LINK.md](AMPLIFY-CLIENT-LINK.md)

**Test the system after deployment / Test the LLM API:**
→ [README.md](../README.md) (see "How to test the agent" and Quick Start)
→ [LLM-TRENDING-PRODUCTS-ARCHITECTURE.md](LLM-TRENDING-PRODUCTS-ARCHITECTURE.md#testing-the-api-with-postman-or-api-clients) (Testing the API with Postman)
→ [terraform/README-LLM.md](../terraform/README-LLM.md#testing) (LLM deployment and testing)

**Understand the architecture:**
→ [ARCHITECTURE.md](ARCHITECTURE.md) (Data Lake)
→ [LLM-TRENDING-PRODUCTS-ARCHITECTURE.md](LLM-TRENDING-PRODUCTS-ARCHITECTURE.md) (AI/LLM System)

**Upload data files:**
→ [CLIENT-OPERATIONS-GUIDE.md](CLIENT-OPERATIONS-GUIDE.md#data-upload-procedures)

**Query data with Athena:**
→ [CLIENT-OPERATIONS-GUIDE.md](CLIENT-OPERATIONS-GUIDE.md#how-to-query-data-with-athena)
→ [athena-views.sql](../athena-views.sql)

**Troubleshoot a job failure:**
→ [runbooks/etl-job-failure.md](../runbooks/etl-job-failure.md)
→ [CLIENT-OPERATIONS-GUIDE.md](CLIENT-OPERATIONS-GUIDE.md#how-to-handle-job-failures)

**Investigate data quality issues:**
→ [runbooks/data-quality-investigation.md](../runbooks/data-quality-investigation.md)
→ [CLIENT-OPERATIONS-GUIDE.md](CLIENT-OPERATIONS-GUIDE.md#how-to-investigate-quality-issues)

**Change the schema:**
→ [runbooks/schema-evolution.md](../runbooks/schema-evolution.md)

**Review governance policies:**
→ [governance/data-governance-charter.md](../governance/data-governance-charter.md)

**Understand data quality rules:**
→ [README.md](../README.md#data-quality)
→ [ARCHITECTURE.md](ARCHITECTURE.md#quality-framework)

**Modify the ETL script:**
→ [scripts/beauty_products_etl.py](../scripts/beauty_products_etl.py)
→ [testing-with-docker.md](testing-with-docker.md)

**Update infrastructure:**
→ [terraform/](../terraform/)
→ [CLIENT-DEPLOYMENT-GUIDE.md](CLIENT-DEPLOYMENT-GUIDE.md)

---

## Documentation Standards

### Document Status

- ✅ **Complete**: Document is finalized and ready for use
- 🔄 **In Progress**: Document is being updated
- 📝 **Draft**: Document is in draft form
- ⚠️ **Needs Review**: Document requires review

### Update Frequency

- **Core Documentation**: Updated with each version release
- **Operations Guides**: Updated as procedures change
- **Runbooks**: Updated when new scenarios are identified
- **Technical Reference**: Updated with code changes

### Contributing

To update documentation:
1. Make changes in appropriate file
2. Update "Last Updated" date
3. Review for accuracy and completeness
4. Update this index if adding new documents

---

## Related Resources

### External Documentation

- [AWS Glue Documentation](https://docs.aws.amazon.com/glue/)
- [Amazon Athena User Guide](https://docs.aws.amazon.com/athena/)
- [AWS S3 Documentation](https://docs.aws.amazon.com/s3/)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [DAMA-DMBOK Framework](https://www.dama.org/cpages/body-of-knowledge)

### Internal Resources

- Data Lake Architecture Diagram: [diagrams/DataLake-Architecture.png](diagrams/DataLake-Architecture.png)
- LLM Architecture Diagram: [diagrams/arquitectura_llm.png](diagrams/arquitectura_llm.png)
- Sample Data: [tests/sample-data/](../tests/sample-data/)
- Schema Definitions: [schemas/](../schemas/)

---

## Support

For questions about documentation:
1. Check this index for relevant documents
2. Review the appropriate guide or runbook
3. Contact your system administrator
4. Refer to [CLIENT-OPERATIONS-GUIDE.md](CLIENT-OPERATIONS-GUIDE.md#support-contacts) for support contacts

---

**Last Updated:** January 26, 2026  
**Maintained By:** Data Engineering Team
