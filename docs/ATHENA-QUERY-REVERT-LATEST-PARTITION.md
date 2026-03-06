# Revert Athena Query to Latest-Partition-Only (Previous Behavior)

This document explains how to switch the LLM report’s Athena queries back to **latest-partition-only** behavior (single most recent month) instead of **all historical data**.

---

## Current vs previous behavior

| Aspect | Current (all history) | Previous (latest partition) |
|--------|------------------------|-----------------------------|
| **Top products** | Aggregated across all partitions (SUM revenue, SUM item_sold, AVG mom_growth_pct). Data accumulates when new months are loaded. | Only the most recent `(year, month_num)` partition. One month of data; replaced when a newer partition exists. |
| **Categories list** | All categories that have ever had data (any partition). | Only categories present in the latest partition. |
| **When new data is added** | Old data stays; new data adds to totals. | Report switches to the new month; previous month no longer used. |

---

## How to revert to latest-partition-only

Edit **`lambda/utils/athena_helper.py`** and replace the two functions as follows.

### 1. Replace `build_top_products_query`

Replace the entire `build_top_products_query` function (from the docstring through `return query.strip()`) with:

```python
def build_top_products_query(l2_category: str, database: str, limit: int = 5) -> str:
    """
    Build SQL query for top products by L2 category.
    Uses only the latest partition (year, month_num) so data is from the most recent
    period (e.g. last 30 days when table is loaded monthly). One row per product, no duplicates.
    Results ordered by revenue (desc) then growth (desc).
    """
    # Escape single quotes in category name
    safe_category = l2_category.replace("'", "''")
    table = f"{database}.curated_beauty_products"
    query = f"""
    WITH distinct_partitions AS (
      SELECT DISTINCT year, month_num FROM {table}
    ),
    ranked_partitions AS (
      SELECT year, month_num,
             ROW_NUMBER() OVER (ORDER BY year DESC, month_num DESC) AS rn
      FROM distinct_partitions
    ),
    latest_partition AS (
      SELECT year, month_num FROM ranked_partitions WHERE rn = 1
    ),
    latest_data AS (
      SELECT p.product_id, p.product_name, p.shop_name, p.l2_category,
             p.revenue_usd, p.mom_growth_pct, p.item_sold
      FROM {table} p
      INNER JOIN latest_partition lp ON p.year = lp.year AND p.month_num = lp.month_num
      WHERE LOWER(TRIM(p.l2_category)) = LOWER(TRIM('{safe_category}'))
        AND p.data_quality_score >= 0.95
    ),
    deduped AS (
      SELECT product_id, product_name, shop_name, l2_category,
             revenue_usd, mom_growth_pct, item_sold,
             ROW_NUMBER() OVER (
               PARTITION BY product_id, product_name, shop_name
               ORDER BY revenue_usd DESC, mom_growth_pct DESC
             ) AS rn
      FROM latest_data
    ),
    ranked_products AS (
      SELECT product_id, product_name, shop_name, l2_category,
             revenue_usd, mom_growth_pct, item_sold,
             ROW_NUMBER() OVER (
               ORDER BY revenue_usd DESC, mom_growth_pct DESC
             ) AS revenue_rank
      FROM deduped
      WHERE rn = 1
    )
    SELECT 
      product_id,
      product_name,
      shop_name,
      l2_category,
      revenue_usd,
      mom_growth_pct,
      item_sold,
      revenue_rank
    FROM ranked_products
    WHERE revenue_rank <= {limit}
    ORDER BY revenue_usd DESC, mom_growth_pct DESC
    """
    return query.strip()
```

### 2. Replace `build_distinct_categories_query`

Replace the entire `build_distinct_categories_query` function with:

```python
def build_distinct_categories_query(database: str) -> str:
    """
    Build SQL to get distinct l2_category from the latest partition only (last 30 days).
    Used for dynamic category list in the frontend — only categories with data in the most recent period.
    """
    table = f"{database}.curated_beauty_products"
    return f"""
    WITH distinct_partitions AS (
      SELECT DISTINCT year, month_num FROM {table}
    ),
    ranked_partitions AS (
      SELECT year, month_num,
             ROW_NUMBER() OVER (ORDER BY year DESC, month_num DESC) AS rn
      FROM distinct_partitions
    ),
    latest_partition AS (
      SELECT year, month_num FROM ranked_partitions WHERE rn = 1
    ),
    latest_data AS (
      SELECT p.l2_category
      FROM {table} p
      INNER JOIN latest_partition lp ON p.year = lp.year AND p.month_num = lp.month_num
      WHERE p.data_quality_score >= 0.95
        AND p.l2_category IS NOT NULL
        AND TRIM(p.l2_category) != ''
    )
    SELECT MIN(TRIM(l2_category)) AS l2_category
    FROM latest_data
    GROUP BY LOWER(TRIM(l2_category))
    ORDER BY l2_category
    """.strip()
```

### 3. Update `query_athena_l2_categories` docstring

In `query_athena_l2_categories`, change the docstring to:

```python
"""
Return sorted list of L2 category names that have data in the latest partition (last 30 days).
Empty list on failure or no data.
"""
```

---

## After reverting

1. Save `lambda/utils/athena_helper.py`.
2. Redeploy the Lambda (e.g. run `.\scripts\deploy-lambda-llm.ps1`).
3. New report requests will again use only the latest partition; the report will show a single month and will switch to the newest month when new partitions are loaded.
