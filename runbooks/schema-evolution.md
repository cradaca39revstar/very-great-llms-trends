# Runbook: Schema Evolution
## Beauty Products Data Lake

**Version:** 1.0.0  
**Last Updated:** January 17, 2026  
**Owner:** Data Architecture Team  

---

## Overview

This runbook defines the process for safely evolving the schema of the Beauty Products Data Lake when source data structure changes or new fields are required.

**Principle:** Maintain backward compatibility and minimize downtime

---

## Schema Change Types

### Type 1: Additive Changes (Low Risk)
**Examples:**
- Adding new optional columns
- Adding new category taxonomy levels
- Adding new governance metadata fields

**Impact:** Low - Existing queries continue to work

---

### Type 2: Modification Changes (Medium Risk)
**Examples:**
- Changing column data type (e.g., STRING → INT)
- Renaming columns
- Changing transformation logic

**Impact:** Medium - May break existing queries

---

### Type 3: Breaking Changes (High Risk)
**Examples:**
- Removing columns
- Changing partition keys
- Major data model restructuring

**Impact:** High - Will break existing queries and downstream applications

---

## Change Approval Matrix

| Change Type | Approval Required | Testing Required | Rollback Plan Required |
|-------------|------------------|------------------|----------------------|
| Additive | Data Steward | Unit + Integration | No |
| Modification | Data Steward + Data Architect | Full Regression | Yes |
| Breaking | Governance Council | Full Regression + UAT | Yes |

---

## Pre-Change Checklist

Before making any schema change:

- [ ] Document business justification for change
- [ ] Identify all affected downstream systems and queries
- [ ] Review existing Athena views and queries
- [ ] Check BI dashboard dependencies
- [ ] Assess impact on data quality rules
- [ ] Plan communication to stakeholders
- [ ] Schedule change window (if needed)
- [ ] Prepare rollback plan

---

## Procedure: Adding New Columns (Additive)

### Example: Adding "Brand" Column

**Scenario:** Source CSV now includes a "Brand" column that we want to capture.

---

#### Step 1: Update Raw Table Schema

**Glue Catalog (via Terraform):**

Edit `terraform/glue-catalog.tf`:

```hcl
# Add new column to raw_beauty_products table
columns {
  name = "brand"
  type = "string"
}
```

**Apply Change:**
```bash
cd terraform/
terraform plan -target=aws_glue_catalog_table.raw_beauty_products
terraform apply -target=aws_glue_catalog_table.raw_beauty_products
```

**Verify:**
```sql
-- Run in Athena
DESCRIBE beauty_products_db.raw_beauty_products;
```

---

#### Step 2: Update ETL Script

Edit `scripts/beauty_products_etl.py`:

```python
# Add transformation for new column
df = df.withColumn("brand", normalize_text_udf(col("Brand")))

# Add to final select for curated output
df_curated_final = df_curated.select(
    # ... existing columns ...
    "brand",  # <-- Add here
    # ... remaining columns ...
)
```

**Test Locally:**
```bash
pytest tests/test_transformations.py
```

**Update Schema Definition:**

Edit `schemas/curated_beauty_products_v1.json`:

```json
{
  "name": "brand",
  "type": "STRING",
  "nullable": true,
  "description": "Product brand name",
  "source_column": "Brand",
  "transformation": "Trim whitespace, normalize encoding"
}
```

**Increment Schema Version:** Update to `v1.1.0` (minor version bump for additive change)

---

#### Step 3: Update Curated Table Schema

**Glue Catalog (via Terraform):**

Edit `terraform/glue-catalog.tf`:

```hcl
# Add to curated_beauty_products table columns
columns {
  name    = "brand"
  type    = "string"
  comment = "Product brand name"
}
```

**Apply:**
```bash
terraform apply -target=aws_glue_catalog_table.curated_beauty_products
```

---

#### Step 4: Deploy ETL Script

```bash
# Upload updated script to S3 (replace {environment} with your environment)
aws s3 cp scripts/beauty_products_etl.py \
  s3://very-great-products-glue-scripts-us-east-1-{environment}/scripts/beauty_products_etl.py

# Update transformation version parameter
aws glue update-job \
  --job-name beauty-products-etl-job \
  --job-update '{"DefaultArguments": {"--TRANSFORMATION_VERSION": "v1.1.0"}}'
```

---

#### Step 5: Test with Sample Data

**Create test file with new column:**
```csv
Month,Product Id,Product Name,Shop Name,L1 category,L2 category,L3 category,Item Sold,Revenue,Avg. Unit Price,MoM Growth %,Brand
4/01/2024,123456,Test Product,Test Shop,Beauty,Hair,Brushes,100,$1000.00,$10.00,5%,TestBrand
```

**Upload to dev/test environment (replace {environment} with your environment):**
```bash
aws s3 cp test-data-with-brand.csv \
  s3://very-great-products-raw-us-east-1-{environment}/landing/beauty-products/test/
```

**Run job manually in test mode:**
```bash
aws glue start-job-run \
  --job-name beauty-products-etl-job \
  --arguments='{"--SOURCE_BUCKET":"very-great-products-raw-us-east-1-{environment}/landing/beauty-products/test/"}'
```

**Verify new column in output:**
```sql
SELECT brand, COUNT(*) 
FROM beauty_products_db.curated_beauty_products 
WHERE processed_timestamp > CURRENT_TIMESTAMP - INTERVAL '1' HOUR
GROUP BY brand;
```

---

#### Step 6: Update Documentation

- [ ] Update business glossary with "Brand" definition
- [ ] Update source-to-target mapping spreadsheet
- [ ] Update Athena view examples if needed
- [ ] Add release notes to CHANGELOG.md

---

#### Step 7: Communicate Change

**Notification Template:**

```
Subject: Beauty Products Data Lake - New "Brand" Column Available

Hi Team,

The Beauty Products Data Lake has been updated with a new column:

**Column:** brand (STRING)
**Description:** Product brand name
**Availability:** Starting [date], all new data will include this field
**Backward Compatibility:** Existing queries will continue to work
**Historical Data:** Previous records will have NULL for this field

Example Query:
SELECT product_name, brand, SUM(revenue_usd) as total_revenue
FROM beauty_products_db.curated_beauty_products
WHERE brand IS NOT NULL
GROUP BY product_name, brand
ORDER BY total_revenue DESC;

Questions? Contact #data-engineering on Slack

Thanks,
Data Engineering Team
```

---

## Procedure: Changing Column Data Type (Modification)

### Example: Converting "Product ID" from STRING to BIGINT

**Risk:** Medium - Existing queries casting as STRING will break

---

#### Step 1: Impact Analysis

**Identify affected queries:**
```sql
-- Search Athena query history for references to product_id
-- Check saved queries, views, dashboards
```

**Check downstream applications:**
- BI dashboards using product_id
- Reporting queries
- Data exports

---

#### Step 2: Create Transition Plan

**Option A: Dual Column Approach (Recommended)**
1. Add new column: `product_id_bigint`
2. Keep old column: `product_id` (STRING) - deprecated
3. Populate both for transition period
4. Migrate consumers to new column
5. Remove old column after transition (3-6 months)

**Option B: In-Place Change (Risky)**
1. Change data type directly
2. Requires all consumers to update simultaneously
3. High coordination overhead

**Recommended:** Option A (Dual Column)

---

#### Step 3: Implement Dual Column

**Update ETL Script:**
```python
# Keep old transformation for backward compatibility
df = df.withColumn("product_id_string", normalize_text_udf(col("Product Id")))

# Add new BIGINT column
df = df.withColumn("product_id", normalize_product_id_udf(col("Product Id")))
```

**Update Curated Table Schema:**
```hcl
# In terraform/glue-catalog.tf

# New column
columns {
  name    = "product_id"
  type    = "bigint"
  comment = "Unique product identifier (numeric)"
}

# Deprecated column
columns {
  name    = "product_id_string"
  type    = "string"
  comment = "DEPRECATED: Use product_id (bigint) instead"
}
```

---

#### Step 4: Create Migration Views

**Athena View for Backward Compatibility:**
```sql
-- Create view that exposes both columns
CREATE OR REPLACE VIEW beauty_products_db.vw_products_legacy AS
SELECT 
    CAST(product_id AS VARCHAR) as product_id_old,
    product_id,
    product_name,
    shop_name,
    -- ... other columns ...
FROM beauty_products_db.curated_beauty_products;
```

---

#### Step 5: Phased Rollout

**Phase 1: Dual Column (Weeks 1-4)**
- Both columns available
- Notify consumers of upcoming change
- Provide migration guide

**Phase 2: Transition (Weeks 5-12)**
- Update downstream applications
- Monitor usage of old column
- Deprecation warnings in documentation

**Phase 3: Cleanup (Week 13+)**
- Remove old column if usage = 0
- Archive deprecated views
- Update all documentation

---

## Procedure: Renaming Columns (Modification)

### Example: Rename "l1_category" to "category_level_1"

**Challenge:** SQL is case-sensitive; breaks existing queries

**Recommended Approach:**

1. **Create Athena View with New Names:**
   ```sql
   CREATE OR REPLACE VIEW beauty_products_db.vw_products_new_schema AS
   SELECT 
       month,
       product_id,
       product_name,
       l1_category as category_level_1,  -- Rename
       l2_category as category_level_2,  -- Rename
       l3_category as category_level_3,  -- Rename
       -- ... other columns ...
   FROM beauty_products_db.curated_beauty_products;
   ```

2. **Keep Physical Table Unchanged:**
   - Underlying Parquet files use old names
   - View provides new names for queries
   - No data rewrite needed

3. **Migrate Consumers Gradually:**
   - Update to use view instead of table
   - Once all migrated, consider physical rename (requires rewrite)

---

## Procedure: Removing Columns (Breaking Change)

### Example: Remove deprecated "product_id_string" column

---

#### Step 1: Verify Zero Usage

```sql
-- Check Athena query history for column usage
-- Review all saved queries and views
-- Confirm with all downstream teams
```

---

#### Step 2: Governance Council Approval

Present to council:
- Business justification for removal
- Impact analysis (should be zero if truly unused)
- Migration completed successfully
- Rollback plan if issues arise

---

#### Step 3: Announce Deprecation

**Timeline:** 30 days advance notice

```
Subject: BREAKING CHANGE - Removal of Deprecated Column

Column to be removed: product_id_string
Removal Date: [Date + 30 days]
Replacement: product_id (BIGINT)

Action Required:
1. Update all queries to use product_id (BIGINT)
2. Test queries before removal date
3. Contact data-engineering if issues

Questions? Reply to this email or Slack #data-engineering
```

---

#### Step 4: Remove from Schema

**Update ETL Script:**
```python
# Remove from final select
df_curated_final = df_curated.select(
    # "product_id_string",  # <-- Remove this line
    "product_id",
    # ... other columns ...
)
```

**Update Glue Catalog:**
```hcl
# Remove column definition from terraform/glue-catalog.tf
# columns {
#   name = "product_id_string"
#   type = "string"
# }
```

**Apply Changes:**
```bash
terraform apply
```

---

#### Step 5: Archive Old Data

**Optional:** If historical data needs column removed:

```sql
-- Create new table without deprecated column
CREATE TABLE beauty_products_db.curated_beauty_products_v2
WITH (
  format = 'PARQUET',
  parquet_compression = 'SNAPPY',
  partitioned_by = ARRAY['year', 'month_num']
) AS
SELECT 
    month,
    product_id,  -- Only new column
    product_name,
    -- ... (excluding product_id_string) ...
FROM beauty_products_db.curated_beauty_products;

-- Swap tables (requires downtime)
ALTER TABLE beauty_products_db.curated_beauty_products RENAME TO curated_beauty_products_old;
ALTER TABLE beauty_products_db.curated_beauty_products_v2 RENAME TO curated_beauty_products;
```

**WARNING:** This rewrites all historical data - only if necessary

---

## Rollback Procedures

### Scenario: New Column Causes ETL Failure

**Rollback Steps:**

1. **Revert ETL Script (replace {environment} with your environment):**
   ```bash
   git revert <commit-hash>
   aws s3 cp scripts/beauty_products_etl.py \
     s3://very-great-products-glue-scripts-us-east-1-{environment}/scripts/
   ```

2. **Revert Glue Catalog:**
   ```bash
   git checkout HEAD~1 terraform/glue-catalog.tf
   terraform apply -target=aws_glue_catalog_table.curated_beauty_products
   ```

3. **Rerun Job:**
   ```bash
   aws glue start-job-run --job-name beauty-products-etl-job
   ```

4. **Verify:**
   ```sql
   SELECT COUNT(*) FROM beauty_products_db.curated_beauty_products
   WHERE processed_timestamp > CURRENT_TIMESTAMP - INTERVAL '1' HOUR;
   ```

---

### Scenario: Data Type Change Breaks Queries

**Rollback Steps:**

1. **Restore Dual Column Approach:**
   - Re-add old column to schema
   - Update ETL to populate both

2. **Recreate Compatibility View:**
   ```sql
   CREATE OR REPLACE VIEW beauty_products_db.vw_products_legacy AS
   SELECT CAST(product_id AS VARCHAR) as product_id, ...
   ```

3. **Notify Stakeholders:**
   - Inform of rollback
   - Provide updated timeline
   - Offer migration assistance

---

## Testing Checklist

Before deploying schema change to production:

### Unit Tests
- [ ] Update `test_transformations.py` with new column tests
- [ ] Run: `pytest tests/test_transformations.py`
- [ ] All tests pass

### Integration Tests
- [ ] Create test CSV with new schema
- [ ] Run ETL in dev environment
- [ ] Verify output Parquet has correct schema
- [ ] Query results with Athena

### Regression Tests
- [ ] Run existing Athena queries against new schema
- [ ] Verify BI dashboards still work
- [ ] Check data quality metrics unchanged
- [ ] Validate row counts match expectations

### Performance Tests
- [ ] Measure query performance with new column
- [ ] Check ETL job duration hasn't increased significantly
- [ ] Verify Parquet file sizes reasonable

---

## Post-Change Validation

After deployment:

### Data Validation
```sql
-- Check new column population rate
SELECT 
    COUNT(*) as total_records,
    COUNT(brand) as brand_populated,
    ROUND(COUNT(brand) * 100.0 / COUNT(*), 2) as population_pct
FROM beauty_products_db.curated_beauty_products
WHERE processed_timestamp > CURRENT_TIMESTAMP - INTERVAL '7' DAY;
```

### Schema Validation
```sql
-- Verify schema matches expectation
DESCRIBE beauty_products_db.curated_beauty_products;
```

### Query Performance
```sql
-- Test query performance with new column
EXPLAIN SELECT brand, SUM(revenue_usd) 
FROM beauty_products_db.curated_beauty_products 
GROUP BY brand;
```

---

## Communication Templates

### Advance Notice (30 days)
```
Subject: Upcoming Schema Change - Beauty Products Data Lake

Change: [Description]
Type: [Additive/Modification/Breaking]
Scheduled Date: [Date]
Impact: [High/Medium/Low]

Details:
[Explain what's changing and why]

Action Required:
[List any actions consumers need to take]

Testing:
[Provide test environment details]

Questions: Contact #data-engineering
```

### Change Notification (Day of)
```
Subject: Schema Change Complete - Beauty Products Data Lake

Status: Successfully deployed
Change: [Description]
Deployed: [Timestamp]

Verification:
[Provide example queries to test]

Issues? Contact #data-engineering immediately
```

---

## Version Control

**Schema Versioning Strategy:**
- **Major** (v2.0.0): Breaking changes, partition key changes
- **Minor** (v1.1.0): Additive changes, new columns
- **Patch** (v1.0.1): Bug fixes, data type corrections

**Track in:**
- `transformation_version` column in curated data
- Git tags: `git tag v1.1.0`
- `schemas/curated_beauty_products_v1.1.0.json`

---

## Related Runbooks

- [ETL Job Failure](etl-job-failure.md)
- [Data Quality Investigation](data-quality-investigation.md)

---

**Questions:** Contact #data-architecture on Slack
