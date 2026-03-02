# AWS Cost Breakdown
## Beauty Products Data Lake + LLM Product Innovation Engine

**Version:** 2.1.0  
**Last Updated:** February 26, 2026  
**Region:** us-east-1 (primary) + **us-east-2 (Ohio)** for image generation (Stability SD 3.5 only)  
**Environment:** dev / poc

> All prices are in USD and based on AWS public pricing as of early 2026.  
> Costs are estimates — actual charges depend on data volume, query patterns, and usage frequency.

**Current pipeline (v2.1):** One report = Athena top 5 market products + Brave Search (web insights) + brand proposal + **1 product concept** with **1 product image** (product + logo overlay) + **1 logo** (symbol only, composed with Pillow). **Only Stability SD 3.5 Large** is used for images (region: **Ohio / us-east-2**). No Nova Pro or other Bedrock LLM in this cost breakdown.

---

## Summary by Scenario

| Scenario | Reports/month | Estimated Monthly Cost |
|----------|--------------|----------------------|
| POC / Demo | 50 | **~$25–40** |
| Low (small team) | 100 | **~$35–55** |
| Medium (active use) | 1,000 | **~$280–420** |
| High (enterprise) | 10,000 | **~$2,600–4,000** |

---

## Current cost vs. budget (VeryGreat documents)

Comparison of this project's estimated cost with the budget defined in the AWS Pricing Calculator documents (VeryGreat-aws-cost-calc-llmops.pdf and VeryGreat-aws-cost-calc-datalake.pdf).

---

## Part 1 — Fixed Monthly Costs (Data Lake Infrastructure)

These costs apply regardless of how many LLM reports are generated. They cover the always-on data lake infrastructure.

### 1.1 Amazon S3 Storage

| Bucket | Retention | Est. Size (small dataset) | Monthly Cost |
|--------|-----------|--------------------------|-------------|
| Raw zone (CSVs) | 1 year | ~500 MB | ~$0.012 |
| Curated zone (Parquet) | 7 years | ~100 MB (Parquet is ~80% smaller than CSV) | ~$0.002 |
| Metadata / quality reports | 7 years | ~50 MB | ~$0.001 |
| Glue scripts + Spark logs | Lifecycle managed | ~10 MB | ~$0.000 |
| Athena query results | 30-day lifecycle | ~50 MB | ~$0.001 |
| **S3 Storage Subtotal** | | | **~$0.02–$2/month** |

> S3 Standard: $0.023/GB-month. Costs scale with data volume — above estimate is for a small POC dataset (~1GB total).

### 1.2 AWS Glue ETL

| Item | Config | Cost Basis | Monthly Cost |
|------|--------|-----------|-------------|
| ETL job (daily run) | G.1X, 2 workers, ~7 min/run | $0.44/DPU-hour × 3 DPU × 0.12 hrs × 30 days | **~$4.75** |
| Glue Data Catalog | 5 databases, ~10 tables | First 1M objects free | **$0.00** |
| Glue Crawlers | 2 crawlers (on-demand + scheduled) | $0.44/DPU-hour, ~5 min/run | **~$1.50** |
| **Glue Subtotal** | | | **~$6.25/month** |

### 1.3 Amazon Athena

| Item | Config | Cost Basis | Monthly Cost |
|------|--------|-----------|-------------|
| Ad-hoc queries (analytics) | ~50 queries/month, ~10MB/query | $5.00/TB scanned | **~$0.003** |
| LLM system queries | Included in per-report cost (see Part 2) | — | — |
| **Athena Subtotal** | | | **~$0.01/month** |

> Parquet format + partition pruning (year/month) dramatically reduces data scanned per query.

### 1.4 Amazon CloudWatch

| Item | Config | Monthly Cost |
|------|--------|-------------|
| Dashboard (Data Lake) | 1 dashboard | **$3.00** |
| Dashboard (LLM system) | 1 dashboard | **$3.00** |
| CloudWatch Alarms | ~8 alarms total | **$0.80** |
| Custom metrics (ETL quality) | ~8 metrics, published per job run | **$2.40** |
| Custom metrics (LLM) | ~6 metrics per report | Included in request-based cost |
| Log ingestion (Glue + Lambda) | ~500 MB/month | **$0.25** |
| **CloudWatch Subtotal** | | **~$9.45/month** |

### 1.5 Other Always-On Services

| Service | Config | Monthly Cost |
|---------|--------|-------------|
| Amazon EventBridge | 1 scheduled rule (daily ETL trigger) | **~$0.00** |
| Amazon SNS | ~30 notifications/month (alarms) | **~$0.00** |
| Amazon Cognito | Up to 50,000 MAUs free | **$0.00** (free tier) |
| IAM + Lake Formation | Always free | **$0.00** |
| AWS X-Ray | Lambda tracing (100K traces free/month) | **$0.00** (free tier for POC) |
| **Other Subtotal** | | **~$0.00/month** |

### Fixed Infrastructure Total

| Component | Monthly Cost |
|-----------|-------------|
| Amazon S3 | ~$0.02–$2.00 |
| AWS Glue ETL | ~$6.25 |
| Amazon Athena | ~$0.01 |
| Amazon CloudWatch | ~$9.45 |
| Other (EventBridge, SNS, Cognito, IAM) | ~$0.00 |
| **FIXED TOTAL** | **~$16–$18/month** |

---

## Part 2 — Variable Costs per LLM Report

Every time a user generates a report through the frontend or API, the following services are invoked.

### Per-Report Cost Breakdown (current: 1 product concept, 1 product image + 1 logo)

| Step | Service | What Happens | Cost per Report |
|------|---------|-------------|----------------|
| 1 | **API Gateway** | 2 API calls (POST + GET poll) | ~$0.000007 |
| 2 | **Athena** | Top-5 product query for market context (~5–10 MB scan, Parquet partitioned) | ~$0.00005 |
| 3 | **Brave Search API** | Web market insights / 5-trend context (cached 6h — shared per category) | ~$0.00–$0.0002 |
| 4 | **AWS Lambda** | 2 invocations × 1,024 MB × ~20–30 seconds | ~$0.00083 |
| 5 | **Bedrock — Stability SD 3.5 Large** | **2 images** (1 logo symbol + 1 product with logo overlay), **us-east-2 (Ohio)** | **~$0.08–$0.16** |
| 6 | **Amazon S3** | PDF upload (~2–4 MB) + 2 image references | ~$0.00002 |
| 7 | **DynamoDB** | ~10 writes + ~20 reads (logs + status polling) | ~$0.00003 |
| 8 | **CloudWatch** | Metrics + log ingestion | ~$0.001 |

**Estimated cost per report: ~$0.09–$0.17**

> **Bedrock is used only for images:** model **Stability SD 3.5 Large** in region **Ohio (us-east-2)**. Nova Pro or any other LLM cost is not included in this breakdown.  
> 2 images per report (1 logo + 1 product with logo). If images are disabled, cost per report drops to **~$0.002–$0.003** (Lambda, Athena, etc. only).

---

## Part 3 — Total Monthly Cost by Scenario

### Scenario A: POC / Demo (50 reports/month)

| Component | Cost |
|-----------|------|
| Fixed infrastructure | ~$17 |
| 50 reports × ~$0.14 avg | ~$7 |
| **Total** | **~$24–$35/month** |

### Scenario B: Low Usage (100 reports/month)

| Component | Cost |
|-----------|------|
| Fixed infrastructure | ~$17 |
| 100 reports × ~$0.14 avg | ~$14 |
| **Total** | **~$31–$45/month** |

### Scenario C: Medium Usage (1,000 reports/month)

| Component | Cost |
|-----------|------|
| Fixed infrastructure | ~$17 |
| 1,000 reports × ~$0.14 avg | ~$140 |
| Brave Search (Pro plan if >2,000 calls) | ~$3 |
| **Total** | **~$160–$250/month** |

### Scenario D: High Usage (10,000 reports/month)

| Component | Cost |
|-----------|------|
| Fixed infrastructure | ~$17 |
| 10,000 reports × ~$0.14 avg | ~$1,400 |
| Brave Search (Pro plan) | ~$15 |
| Cognito (>50K MAU threshold) | ~$0–$275 |
| **Total** | **~$1,400–$2,200/month** |

---

## Part 4 — External API Costs (Brave Search)

The system uses Brave Search for web market insights. Results are cached in DynamoDB for 6 hours per L2 category, reducing actual API calls.

| Plan | Price | Queries/month | Notes |
|------|-------|--------------|-------|
| Free | $0 | 2,000 | Sufficient for POC (<100 reports/month with caching) |
| Pro | $3/month | 20,000 | Recommended for 100–1,000 reports/month |
| Enterprise | Custom | Unlimited | For high-volume usage |

> With the 6-hour cache, if 10 users generate reports for "Skincare" in the same 6-hour window, only 1 Brave Search call is made instead of 10.

---


## Part 5 — Cost Monitoring

### AWS Cost Explorer

Monitor costs by service and tag in AWS Console:

```
AWS Console → Cost Explorer → Group by: Service
Filter by tag: Project = BeautyProductsDataLake
```

### Cost Alerts

Set up a billing alarm to get notified when costs exceed a threshold:

```sh
aws cloudwatch put-metric-alarm \
  --alarm-name "monthly-cost-alert" \
  --alarm-description "Alert when monthly spend exceeds $100" \
  --metric-name EstimatedCharges \
  --namespace AWS/Billing \
  --statistic Maximum \
  --period 86400 \
  --evaluation-periods 1 \
  --threshold 100 \
  --comparison-operator GreaterThanThreshold \
  --alarm-actions arn:aws:sns:us-east-1:{account}:{sns-topic}
```

### Key Metrics to Monitor

| Metric | CloudWatch Dashboard | Target |
|--------|---------------------|--------|
| Reports generated per day | LLM dashboard | Track growth |
| Average report latency | LLM dashboard | < 30 seconds |
| Lambda error rate | LLM dashboard | < 2% |
| Glue job duration | Data Lake dashboard | < 10 minutes |
| Athena data scanned | Athena console | < 100 MB/query |

---

## Part 6 — Pricing References

| Service | Pricing Page |
|---------|-------------|
| Stability AI (SD 3.5 Large) — us-east-2 (Ohio) | https://aws.amazon.com/bedrock/pricing/ (Marketplace models) |
| AWS Lambda | https://aws.amazon.com/lambda/pricing/ |
| AWS Glue | https://aws.amazon.com/glue/pricing/ |
| Amazon Athena | https://aws.amazon.com/athena/pricing/ |
| Amazon S3 | https://aws.amazon.com/s3/pricing/ |
| Amazon DynamoDB | https://aws.amazon.com/dynamodb/pricing/ |
| API Gateway | https://aws.amazon.com/api-gateway/pricing/ |
| Amazon Cognito | https://aws.amazon.com/cognito/pricing/ |
| Brave Search API | https://api.search.brave.com/app/subscriptions |

---

**Prepared by:** Revstar DATA AI Team  
**Date:** February 26, 2026  

> This document provides cost estimates for planning purposes. Actual AWS charges may vary. Use [AWS Pricing Calculator](https://calculator.aws/) for a customized estimate.