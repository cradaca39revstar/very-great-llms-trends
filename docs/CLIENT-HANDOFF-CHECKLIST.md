# Client Handoff Checklist
## Beauty Products Data Lake + LLM Product Innovation Engine

**Version:** 2.0.0  
**Handoff Date:** February 26, 2026  
**Environment:** dev (POC)

Use this checklist during the knowledge transfer session. Mark each item as the session progresses.

---

## Section 1 — System Access

| # | Item | Status | Notes |
|---|------|--------|-------|
| 1.1 | Client has AWS Console access to the deployment account | ☐ | |
| 1.2 | Client can access the Amplify frontend URL | ☐ | https://amplify-versio.d32yhcl4pif1yr.amplifyapp.com/ |
| 1.3 | Client has received demo account credentials | ☐ | verygreat@test.com |
| 1.4 | Client can sign in to the frontend and generate a report | ☐ | |
| 1.5 | Client has been shown how to download the PDF report | ☐ | |
| 1.6 | Client has received Terraform outputs (API URL, Cognito IDs, etc.) | ☐ | |

---

## Section 2 — Architecture Walkthrough

| # | Topic | Status | Notes |
|---|-------|--------|-------|
| 2.1 | Data Lake architecture explained (S3 zones, Glue, Athena) | ☐ | See `docs/ARCHITECTURE.md` |
| 2.2 | LLM system architecture explained (Lambda, Bedrock, API GW, Cognito) | ☐ | See `docs/LLM-TRENDING-PRODUCTS-ARCHITECTURE.md` |
| 2.3 | Async flow explained: POST → 202 → polling GET → completed | ☐ | |
| 2.4 | AI image generation explained (Stability SD 3.5, us-west-2) | ☐ | |
| 2.5 | Data quality framework explained (scoring, tiers, flags) | ☐ | See `README.md#data-quality` |
| 2.6 | Web insights cache explained (Brave Search + DynamoDB 6h TTL) | ☐ | |

---

## Section 3 — Data Operations

| # | Item | Status | Notes |
|---|------|--------|-------|
| 3.1 | Client knows how to upload CSV files to S3 raw zone | ☐ | See Operations Guide §1.2 |
| 3.2 | Client understands the required CSV column format (11 columns) | ☐ | |
| 3.3 | Client knows ETL runs automatically at 2 AM UTC | ☐ | |
| 3.4 | Client knows how to trigger ETL job manually | ☐ | `aws glue start-job-run` |
| 3.5 | Client can view ETL job status and logs in CloudWatch | ☐ | |
| 3.6 | Client has been shown data quality report structure | ☐ | |
| 3.7 | Client understands quality tiers (PASS/WARN/FAIL) and routing | ☐ | |

---

## Section 4 — Athena Analytics

| # | Item | Status | Notes |
|---|------|--------|-------|
| 4.1 | Client can open Athena Query Editor | ☐ | |
| 4.2 | Client knows which workgroup to use | ☐ | `beauty-products-athena-dev` |
| 4.3 | Client has been shown the 5 pre-built views | ☐ | `vw_high_quality_products`, etc. |
| 4.4 | Client understands the top-5 query that feeds the LLM | ☐ | |
| 4.5 | Client knows how to add partition filters for performance | ☐ | |

---

## Section 5 — LLM Product Innovation Engine

| # | Item | Status | Notes |
|---|------|--------|-------|
| 5.1 | Client can use the frontend to generate a report | ☐ | |
| 5.2 | Client understands what a "brand proposal" includes | ☐ | Name, tagline, story, values, positioning |
| 5.3 | Client understands what "product ideas" include | ☐ | 5 concepts with images, price, ingredients |
| 5.4 | Client knows what L2 categories are available | ☐ | From Athena `DISTINCT l2_category` query |
| 5.5 | Client understands the ~15–25 second generation time | ☐ | |
| 5.6 | Client knows PDF links expire after 1 hour | ☐ | |
| 5.7 | Client knows the API error codes (TRD001–TRD007) | ☐ | See Operations Guide §5.2 |

---

## Section 6 — Monitoring

| # | Item | Status | Notes |
|---|------|--------|-------|
| 6.1 | Client can access the Data Lake CloudWatch dashboard | ☐ | `beauty-products-pipeline-metrics` |
| 6.2 | Client can access the LLM CloudWatch dashboard | ☐ | `beauty-products-llm-dashboard` |
| 6.3 | Client knows which alarms are configured and what they do | ☐ | 3 ETL alarms + LLM error alarms |
| 6.4 | Client knows how to check alert email configuration | ☐ | SNS topic, `alert_email` in tfvars |
| 6.5 | Client can view Lambda logs in CloudWatch | ☐ | `/aws/lambda/beauty-products-llm-orchestrator-dev` |
| 6.6 | Client can query DynamoDB audit logs | ☐ | `beauty-products-prompt-logs-dev` |

---

## Section 7 — User Management

| # | Item | Status | Notes |
|---|------|--------|-------|
| 7.1 | Client knows how to create users in Cognito | ☐ | Via Console or CLI (Operations Guide §4) |
| 7.2 | Client knows how to disable/delete users | ☐ | |
| 7.3 | Client understands Cognito password requirements | ☐ | 8+ chars, uppercase, lowercase, number |
| 7.4 | Client has changed or plans to change demo account password | ☐ | `VeryGreat123!` |

---

## Section 8 — Deployment and Infrastructure

| # | Item | Status | Notes |
|---|------|--------|-------|
| 8.1 | Client has a copy of the project repository | ☐ | |
| 8.2 | Client has a copy of `terraform.tfvars` (securely) | ☐ | Do not commit to git |
| 8.3 | Client has `terraform.tfvars.example` as a reference | ☐ | `terraform/terraform.tfvars.example` |
| 8.4 | Client understands the 2-step deployment: Terraform + Lambda deploy script | ☐ | |
| 8.5 | Client knows how to re-deploy Lambda code updates | ☐ | `.\scripts\deploy-lambda-llm.ps1` |
| 8.6 | Client knows how to run `terraform plan/apply` for infra changes | ☐ | |
| 8.7 | Client knows how to destroy infrastructure if needed | ☐ | `terraform destroy` (see Deployment Guide §decommission) |

---

## Section 9 — Runbooks and Troubleshooting

| # | Runbook | Status | Notes |
|---|---------|--------|-------|
| 9.1 | ETL Job Failure | ☐ | `runbooks/etl-job-failure.md` |
| 9.2 | Data Quality Investigation | ☐ | `runbooks/data-quality-investigation.md` |
| 9.3 | Schema Evolution | ☐ | `runbooks/schema-evolution.md` |
| 9.4 | Validation and Testing | ☐ | `runbooks/validation-and-testing.md` |
| 9.5 | Lake Formation Security Review | ☐ | `runbooks/lake-formation-security-review.md` |
| 9.6 | End-to-End Test (DL → LLM) | ☐ | `runbooks/e2e-dl-to-llm-test.md` |

---

## Section 10 — Security and Compliance

| # | Item | Status | Notes |
|---|------|--------|-------|
| 10.1 | Client understands that `terraform.tfvars` must NOT be committed to git | ☐ | Already in `.gitignore` |
| 10.2 | Client will rotate Brave Search API key after handoff | ☐ | |
| 10.3 | Client understands S3 buckets are private (public access blocked) | ☐ | |
| 10.4 | Client understands data retention policies | ☐ | Operations Guide §8 |
| 10.5 | Client has reviewed the Data Governance Charter | ☐ | `governance/data-governance-charter.md` |
| 10.6 | Production hardening checklist reviewed | ☐ | See `terraform/README-LLM.md` Security section |

---

## Post-Handoff Action Items

Items the client should complete after the session:

| # | Action | Owner | Target Date |
|---|--------|-------|-------------|
| 1 | Change demo account password | Client | After handoff |
| 2 | Create individual user accounts for the team | Client | Week 1 |
| 3 | Rotate Brave Search API key | Client | Week 1 |
| 4 | Configure `alert_email` to production ops team | Client | Week 1 |
| 5 | Upload production data and run ETL | Client | Week 1 |
| 6 | Enable MFA on Cognito User Pool (for production) | Client | Week 2 |
| 7 | Review and accept Data Governance Charter | Client | Week 2 |
| 8 | Set up cost monitoring in AWS Cost Explorer | Client | Week 2 |

---

## Handoff Sign-Off

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Delivered by (Revstar) | | | |
| Received by (Client) | | | |
| Technical lead (Client) | | | |

---

**Session Date:** _______________  
**Duration:** _______________  
**Participants:** _______________  
**Follow-up session needed:** ☐ Yes / ☐ No  
**Follow-up date:** _______________
