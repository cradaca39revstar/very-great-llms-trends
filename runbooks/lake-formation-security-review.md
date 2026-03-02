# Runbook: Lake Formation Security Review
## Beauty Products Data Lake

**Version:** 1.0.0  
**Last Updated:** January 24, 2026  
**Owner:** Data Engineering Team  

---

## Overview

This runbook supports the backlog **"Iterate Lake Formation security"** (Iterate Lake Formation and define role-based access policies for data access control). It provides the quarterly (or team-defined) procedure to review and validate Lake Formation configuration.

**Frequency:** Quarterly, or as defined in the [Data Governance Charter](../governance/data-governance-charter.md).

---

## Prerequisites

**Required Access:**

- AWS Console Lake Formation access (Data Lake Settings, permissions)
- Terraform codebase access
- Permissions to run `terraform plan` (and `terraform apply` if remediating drift)

**Required Tools:**

- AWS CLI installed and configured
- Terraform >= 1.0

---

## Procedure

### Step 1: Review Admins and Trusted Owners

Compare Lake Formation console (Data Lake Settings) with Terraform.

**Console:** AWS Lake Formation > Data lake permissions > Data lake admins, and Settings > Trusted resource owners.

**Terraform:** [terraform/lake-formation.tf](../terraform/lake-formation.tf) — `aws_lakeformation_data_lake_settings.main` (`admins`, `trusted_resource_owners`).

- [ ] Admins in console match Terraform
- [ ] Trusted resource owners in console match Terraform
- [ ] Document any discrepancies for remediation

---

### Step 2: Review Permissions by Role

For **Glue ETL** and **Athena** roles, verify DB/table/location permissions in the console vs Terraform `aws_lakeformation_permissions` resources.

**Glue ETL role:**

- Databases: `beauty_products`, `metadata` — CREATE_TABLE, ALTER, DROP
- Tables: raw, curated, error, quarantine, quality_metrics, lineage — SELECT, INSERT, DELETE, ALTER, DROP as defined
- Data locations: raw, curated, metadata buckets — DATA_LOCATION_ACCESS

**Athena role:**

- Databases: DESCRIBE only
- Tables: curated, quality_metrics, lineage — SELECT only (no raw/error/quarantine)

- [ ] Glue ETL permissions match Terraform and follow least privilege
- [ ] Athena permissions match Terraform and follow least privilege (SELECT only on curated/metrics/lineage)
- [ ] No extra principals or permissions granted manually in console

---

### Step 3: Check Drift

Run `terraform plan` from the `terraform/` directory.

```bash
cd terraform/
terraform plan
```

If there are changes to `aws_lakeformation_*` resources:

- Investigate cause (e.g. manual console changes)
- **Option A:** Update Terraform to reflect intended state, then `terraform apply`
- **Option B:** Revert manual changes in console to match Terraform

- [ ] `terraform plan` reviewed
- [ ] Any drift identified and remediated (Terraform updated or console reverted)

---

### Step 4: Record the Review

Log the following:

- **Date** of review
- **Responsible person**
- **Findings** (including any drift or remediation taken)
- **Next review date** (e.g. +3 months for quarterly)

Store in a team-defined location (e.g. wiki, shared doc, changelog, or compliance log).

- [ ] Review recorded with date, owner, and findings
- [ ] Next review date scheduled

---

## References

- [Data Governance Charter — §4. Iterate Lake Formation Security](../governance/data-governance-charter.md#4-iterate-lake-formation-security)
- [terraform/lake-formation.tf](../terraform/lake-formation.tf) — Lake Formation Terraform resources
- [CLIENT-DEPLOYMENT-GUIDE — Deploy Lake Formation](../docs/CLIENT-DEPLOYMENT-GUIDE.md) — Initial deploy/validate procedure
