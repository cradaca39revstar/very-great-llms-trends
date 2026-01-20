-- ============================================================================
-- Athena Views and Queries for Beauty Products Data Lake
-- Database: beauty_products_db
-- ============================================================================

-- View 1: High Quality Products
-- Filter for production-ready data with quality score >= 0.95
-- ============================================================================

CREATE OR REPLACE VIEW beauty_products_db.vw_high_quality_products AS
SELECT 
    month,
    product_id,
    product_name,
    shop_name,
    l1_category,
    l2_category,
    l3_category,
    item_sold,
    revenue_usd,
    avg_unit_price_usd,
    mom_growth_pct,
    data_quality_score,
    processed_timestamp
FROM 
    beauty_products_db.curated_beauty_products
WHERE 
    data_quality_score >= 0.95
ORDER BY 
    month DESC, revenue_usd DESC;

-- Usage: SELECT * FROM vw_high_quality_products WHERE month >= DATE '2024-01-01';


-- View 2: Sales by Category and Month
-- Aggregated sales metrics by category hierarchy
-- ============================================================================

CREATE OR REPLACE VIEW beauty_products_db.vw_sales_by_category_month AS
SELECT 
    year,
    month_num,
    month,
    l1_category,
    l2_category,
    l3_category,
    COUNT(DISTINCT product_id) as unique_products,
    COUNT(DISTINCT shop_name) as unique_shops,
    SUM(item_sold) as total_items_sold,
    SUM(revenue_usd) as total_revenue_usd,
    AVG(avg_unit_price_usd) as avg_product_price,
    AVG(data_quality_score) as avg_quality_score
FROM 
    beauty_products_db.curated_beauty_products
WHERE 
    data_quality_score >= 0.70  -- Include warned records
GROUP BY 
    year,
    month_num,
    month,
    l1_category,
    l2_category,
    l3_category
ORDER BY 
    year DESC,
    month_num DESC,
    total_revenue_usd DESC;

-- Usage: SELECT * FROM vw_sales_by_category_month WHERE year = 2024 AND l1_category = 'Beauty & Personal Care';


-- View 3: Data Quality Trends
-- Track data quality over time
-- ============================================================================

CREATE OR REPLACE VIEW beauty_products_db.vw_quality_trends AS
SELECT 
    year,
    month_num,
    month,
    COUNT(*) as total_records,
    SUM(CASE WHEN data_quality_score >= 0.95 THEN 1 ELSE 0 END) as high_quality_count,
    SUM(CASE WHEN data_quality_score >= 0.70 AND data_quality_score < 0.95 THEN 1 ELSE 0 END) as medium_quality_count,
    SUM(CASE WHEN data_quality_score < 0.70 THEN 1 ELSE 0 END) as low_quality_count,
    AVG(data_quality_score) as avg_quality_score,
    MIN(data_quality_score) as min_quality_score,
    MAX(data_quality_score) as max_quality_score,
    COUNT(DISTINCT transformation_version) as transformation_versions
FROM 
    beauty_products_db.curated_beauty_products
GROUP BY 
    year,
    month_num,
    month
ORDER BY 
    year DESC,
    month_num DESC;

-- Usage: SELECT * FROM vw_quality_trends WHERE avg_quality_score < 0.90;


-- View 4: Product Performance Summary
-- Top performing products with growth metrics
-- ============================================================================

CREATE OR REPLACE VIEW beauty_products_db.vw_product_performance AS
SELECT 
    product_id,
    product_name,
    shop_name,
    l1_category,
    l2_category,
    COUNT(DISTINCT month) as months_on_market,
    SUM(item_sold) as lifetime_items_sold,
    SUM(revenue_usd) as lifetime_revenue_usd,
    AVG(avg_unit_price_usd) as avg_price,
    AVG(mom_growth_pct) as avg_mom_growth,
    MAX(revenue_usd) as peak_monthly_revenue,
    AVG(data_quality_score) as avg_quality_score
FROM 
    beauty_products_db.curated_beauty_products
WHERE 
    data_quality_score >= 0.70
GROUP BY 
    product_id,
    product_name,
    shop_name,
    l1_category,
    l2_category
HAVING 
    SUM(revenue_usd) > 0
ORDER BY 
    lifetime_revenue_usd DESC;

-- Usage: SELECT * FROM vw_product_performance LIMIT 100;


-- View 5: Shop Performance Leaderboard
-- Rank shops by sales performance
-- ============================================================================

CREATE OR REPLACE VIEW beauty_products_db.vw_shop_leaderboard AS
SELECT 
    shop_name,
    COUNT(DISTINCT product_id) as product_count,
    COUNT(DISTINCT l2_category) as category_diversity,
    SUM(item_sold) as total_items_sold,
    SUM(revenue_usd) as total_revenue_usd,
    AVG(revenue_usd) as avg_monthly_revenue,
    AVG(data_quality_score) as avg_data_quality
FROM 
    beauty_products_db.curated_beauty_products
WHERE 
    data_quality_score >= 0.70
GROUP BY 
    shop_name
ORDER BY 
    total_revenue_usd DESC;

-- Usage: SELECT * FROM vw_shop_leaderboard LIMIT 50;


-- ============================================================================
-- Example Queries
-- ============================================================================

-- Query 1: Top 10 Products by Revenue (Last 6 Months)
-- ============================================================================
SELECT 
    product_name,
    shop_name,
    l2_category,
    SUM(revenue_usd) as total_revenue,
    SUM(item_sold) as total_units_sold,
    AVG(avg_unit_price_usd) as avg_price
FROM 
    beauty_products_db.curated_beauty_products
WHERE 
    month >= DATE_ADD('month', -6, CURRENT_DATE)
    AND data_quality_score >= 0.95
GROUP BY 
    product_name,
    shop_name,
    l2_category
ORDER BY 
    total_revenue DESC
LIMIT 10;


-- Query 2: Month-over-Month Growth Analysis
-- ============================================================================
WITH monthly_sales AS (
    SELECT 
        year,
        month_num,
        month,
        SUM(revenue_usd) as total_revenue,
        SUM(item_sold) as total_items
    FROM 
        beauty_products_db.curated_beauty_products
    WHERE 
        data_quality_score >= 0.70
    GROUP BY 
        year, month_num, month
),
growth_calc AS (
    SELECT 
        month,
        total_revenue,
        total_items,
        LAG(total_revenue) OVER (ORDER BY year, month_num) as prev_month_revenue,
        LAG(total_items) OVER (ORDER BY year, month_num) as prev_month_items
    FROM 
        monthly_sales
)
SELECT 
    month,
    total_revenue,
    total_items,
    prev_month_revenue,
    ROUND((total_revenue - prev_month_revenue) / prev_month_revenue * 100, 2) as revenue_growth_pct,
    ROUND((total_items - prev_month_items) / CAST(prev_month_items AS DOUBLE) * 100, 2) as volume_growth_pct
FROM 
    growth_calc
WHERE 
    prev_month_revenue IS NOT NULL
ORDER BY 
    month DESC;


-- Query 3: Category Performance Comparison
-- ============================================================================
SELECT 
    l1_category,
    l2_category,
    COUNT(DISTINCT product_id) as product_count,
    SUM(revenue_usd) as total_revenue,
    AVG(avg_unit_price_usd) as avg_price_point,
    SUM(item_sold) as total_units_sold,
    ROUND(SUM(revenue_usd) * 100.0 / SUM(SUM(revenue_usd)) OVER (), 2) as revenue_share_pct
FROM 
    beauty_products_db.curated_beauty_products
WHERE 
    year = YEAR(CURRENT_DATE)
    AND data_quality_score >= 0.70
GROUP BY 
    l1_category,
    l2_category
ORDER BY 
    total_revenue DESC;


-- Query 4: Quality Issues Deep Dive
-- ============================================================================
SELECT 
    quality_flags,
    COUNT(*) as record_count,
    AVG(data_quality_score) as avg_score,
    AVG(revenue_usd) as avg_revenue,
    SUM(revenue_usd) as total_revenue_affected
FROM 
    beauty_products_db.curated_beauty_products
WHERE 
    quality_flags IS NOT NULL
    AND quality_flags != ''
GROUP BY 
    quality_flags
ORDER BY 
    record_count DESC;


-- Query 5: Products with Declining Sales
-- Identify products with negative MoM growth
-- ============================================================================
SELECT 
    product_id,
    product_name,
    shop_name,
    month,
    revenue_usd,
    mom_growth_pct,
    data_quality_score
FROM 
    beauty_products_db.curated_beauty_products
WHERE 
    mom_growth_pct < -0.20  -- 20% decline
    AND data_quality_score >= 0.90
    AND month >= DATE_ADD('month', -3, CURRENT_DATE)
ORDER BY 
    mom_growth_pct ASC,
    revenue_usd DESC
LIMIT 50;


-- Query 6: Revenue by Shop and Category Matrix
-- ============================================================================
SELECT 
    shop_name,
    l2_category,
    COUNT(DISTINCT product_id) as products,
    SUM(item_sold) as units_sold,
    SUM(revenue_usd) as total_revenue,
    AVG(data_quality_score) as avg_quality
FROM 
    beauty_products_db.curated_beauty_products
WHERE 
    year = 2024
    AND data_quality_score >= 0.70
GROUP BY 
    shop_name,
    l2_category
HAVING 
    SUM(revenue_usd) > 10000
ORDER BY 
    shop_name,
    total_revenue DESC;


-- Query 7: Data Freshness Check
-- ============================================================================
SELECT 
    MAX(processed_timestamp) as last_load_time,
    MAX(month) as latest_data_month,
    COUNT(*) as total_records_loaded,
    transformation_version,
    AVG(data_quality_score) as avg_quality_score
FROM 
    beauty_products_db.curated_beauty_products
GROUP BY 
    transformation_version
ORDER BY 
    last_load_time DESC;


-- Query 8: Anomaly Detection Summary
-- Check quarantine table for anomalies
-- ============================================================================
SELECT 
    quarantine_reason,
    COUNT(*) as record_count,
    AVG(data_quality_score) as avg_quality_score
FROM 
    beauty_products_db.quarantine_beauty_products
GROUP BY 
    quarantine_reason
ORDER BY 
    record_count DESC;


-- Query 9: Price Elasticity Analysis
-- Correlation between price changes and volume
-- ============================================================================
SELECT 
    l2_category,
    CASE 
        WHEN avg_unit_price_usd < 10 THEN 'Budget (<$10)'
        WHEN avg_unit_price_usd < 25 THEN 'Mid-Range ($10-$25)'
        WHEN avg_unit_price_usd < 50 THEN 'Premium ($25-$50)'
        ELSE 'Luxury (>$50)'
    END as price_tier,
    COUNT(DISTINCT product_id) as product_count,
    SUM(item_sold) as total_units,
    SUM(revenue_usd) as total_revenue,
    AVG(avg_unit_price_usd) as avg_price
FROM 
    beauty_products_db.curated_beauty_products
WHERE 
    data_quality_score >= 0.90
    AND year = 2024
GROUP BY 
    l2_category,
    CASE 
        WHEN avg_unit_price_usd < 10 THEN 'Budget (<$10)'
        WHEN avg_unit_price_usd < 25 THEN 'Mid-Range ($10-$25)'
        WHEN avg_unit_price_usd < 50 THEN 'Premium ($25-$50)'
        ELSE 'Luxury (>$50)'
    END
ORDER BY 
    l2_category,
    avg_price;


-- Query 10: Metadata Quality Report
-- Query the quality metrics table
-- ============================================================================
SELECT 
    json_extract_scalar(quality_issues, '$.INVALID_DATE') as invalid_dates,
    json_extract_scalar(quality_issues, '$.SYNTHETIC_PRODUCT_ID') as synthetic_ids,
    json_extract_scalar(quality_issues, '$.MISSING_PRODUCT_NAME') as missing_names,
    total_records,
    records_passed,
    records_warned,
    records_failed,
    pass_rate,
    avg_quality_score,
    execution_timestamp,
    transformation_version
FROM 
    beauty_products_metadata_db.data_quality_metrics
ORDER BY 
    execution_timestamp DESC
LIMIT 10;
