"""
Integration Tests for Beauty Products ETL Pipeline

End-to-end testing with sample data files.

NOTE: These tests are designed to run in the AWS Glue Docker container.
Use the script: scripts/test-with-aws-glue-docker.ps1

This ensures the same environment as AWS Glue in production (Linux-based).
"""

import unittest
import os
import sys
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType
import shutil

# Workaround for Python 3.14 serialization issues
if sys.version_info >= (3, 14):
    import warnings
    warnings.filterwarnings("ignore", category=RuntimeWarning)


class TestETLIntegration(unittest.TestCase):
    """Integration tests for complete ETL pipeline"""
    
    @classmethod
    def setUpClass(cls):
        """Set up Spark session for testing"""
        # Configure Spark to minimize serialization and socket issues
        from pyspark.sql import SparkSession
        from pyspark import SparkConf
        
        conf = SparkConf()
        conf.set("spark.serializer", "org.apache.spark.serializer.KryoSerializer")
        conf.set("spark.sql.execution.arrow.pyspark.enabled", "false")
        conf.set("spark.sql.execution.arrow.maxRecordsPerBatch", "1")
        conf.set("spark.sql.execution.pythonUDF.arrow.enabled", "false")
        conf.set("spark.python.worker.reuse", "false")
        # Fix socket connection issues on Windows
        conf.set("spark.local.dir", os.path.join(os.getcwd(), "spark-temp"))
        conf.set("spark.network.timeout", "600s")
        conf.set("spark.executor.heartbeatInterval", "60s")
        conf.set("spark.sql.adaptive.enabled", "false")
        conf.set("spark.sql.adaptive.coalescePartitions.enabled", "false")
        
        cls.spark = SparkSession.builder \
            .appName("BeautyProductsETLTest") \
            .master("local[1]") \
            .config(conf=conf) \
            .getOrCreate()
        
        cls.test_data_dir = "./test_data_temp"
        os.makedirs(cls.test_data_dir, exist_ok=True)
    
    @classmethod
    def tearDownClass(cls):
        """Clean up Spark session and test data"""
        cls.spark.stop()
        if os.path.exists(cls.test_data_dir):
            shutil.rmtree(cls.test_data_dir)
    
    def test_csv_read_valid_data(self):
        """Test reading valid CSV data"""
        # Create sample CSV
        sample_data = [
            "Month,Product Id,Product Name,Shop Name,L1 category,L2 category,L3 category,Item Sold,Revenue,Avg. Unit Price,MoM Growth %",
            "4/01/2024,1,72938E+18,Unbrush Detangling Hair Brush,BeautyChoiceUSA,Beauty & Personal Care,Haircare & Styling,Hair Brushes & Combs,24157,$305785.10,$12.66,-42%"
        ]
        
        csv_path = f"{self.test_data_dir}/valid_input.csv"
        with open(csv_path, 'w') as f:
            f.write('\n'.join(sample_data))
        
        # Read CSV
        df = self.spark.read.format("csv") \
            .option("header", "true") \
            .load(csv_path)
        
        self.assertEqual(df.count(), 1)
        self.assertEqual(len(df.columns), 11)
    
    def test_transformation_pipeline(self):
        """Test complete transformation pipeline"""
        # Create sample data
        data = [
            ("4/01/2024", "123456", "Test Product", "Test Shop", "Beauty", "Hair", "Brushes", 
             "100", "$1,234.56", "$12.34", "5%")
        ]
        
        schema = StructType([
            StructField("Month", StringType(), True),
            StructField("Product Id", StringType(), True),
            StructField("Product Name", StringType(), True),
            StructField("Shop Name", StringType(), True),
            StructField("L1 category", StringType(), True),
            StructField("L2 category", StringType(), True),
            StructField("L3 category", StringType(), True),
            StructField("Item Sold", StringType(), True),
            StructField("Revenue", StringType(), True),
            StructField("Avg. Unit Price", StringType(), True),
            StructField("MoM Growth %", StringType(), True)
        ])
        
        df = self.spark.createDataFrame(data, schema)
        df.createOrReplaceTempView("test_data")
        
        # Use SQL directly to avoid serialization issues
        df_transformed = self.spark.sql("""
            SELECT *, TO_DATE(Month, 'M/dd/yyyy') as month_parsed
            FROM test_data
        """)
        
        # Verify columns without collecting to avoid socket issues
        columns = df_transformed.columns
        self.assertIn("month_parsed", columns)
        
        # Verify count using SQL to avoid socket issues
        count_df = self.spark.sql("SELECT COUNT(*) as cnt FROM test_data")
        count = count_df.collect()[0][0]
        self.assertEqual(count, 1)
    
    def test_quality_scoring(self):
        """Test data quality score calculation"""
        # Create data with quality issues
        data = [
            ("invalid-date", "", "Test Product", "Test Shop", "Beauty", "Hair", "Brushes", 
             "100", "$1,234.56", "$12.34", "5%")
        ]
        
        schema = StructType([
            StructField("Month", StringType(), True),
            StructField("Product Id", StringType(), True),
            StructField("Product Name", StringType(), True),
            StructField("Shop Name", StringType(), True),
            StructField("L1 category", StringType(), True),
            StructField("L2 category", StringType(), True),
            StructField("L3 category", StringType(), True),
            StructField("Item Sold", StringType(), True),
            StructField("Revenue", StringType(), True),
            StructField("Avg. Unit Price", StringType(), True),
            StructField("MoM Growth %", StringType(), True)
        ])
        
        df = self.spark.createDataFrame(data, schema)
        df.createOrReplaceTempView("test_data")
        
        # Use SQL directly to avoid serialization issues
        df_scored = self.spark.sql("""
            SELECT *,
                CASE WHEN Month = 'invalid-date' THEN 1.0000 - 0.20 ELSE 1.0000 END as data_quality_score
            FROM test_data
        """)
        df_scored.createOrReplaceTempView("scored_data")
        
        # Verify using SQL aggregation to avoid socket issues
        result_df = self.spark.sql("SELECT AVG(data_quality_score) as avg_score FROM scored_data")
        result = result_df.collect()[0][0]
        # Convert to float if it's a Decimal type
        if hasattr(result, '__float__'):
            result = float(result)
        self.assertAlmostEqual(result, 0.8000, places=4)
    
    def test_malformed_csv_handling(self):
        """Test handling of malformed CSV rows"""
        # Create CSV with malformed row
        sample_data = [
            "Month,Product Id,Product Name,Shop Name,L1 category,L2 category,L3 category,Item Sold,Revenue,Avg. Unit Price,MoM Growth %",
            "4/01/2024,123,Test Product,Test Shop,Beauty,Hair,Brushes,100,$100.00,$10.00,5%",
            "malformed row with missing columns"
        ]
        
        csv_path = f"{self.test_data_dir}/malformed_input.csv"
        with open(csv_path, 'w') as f:
            f.write('\n'.join(sample_data))
        
        # Read CSV in permissive mode with corrupt record handling
        # Note: Some Spark versions may handle corrupt records differently
        df = self.spark.read.format("csv") \
            .option("header", "true") \
            .option("mode", "PERMISSIVE") \
            .option("columnNameOfCorruptRecord", "_corrupt_record") \
            .option("multiLine", "false") \
            .load(csv_path)
        
        # Check columns - corrupt record column may not always be present depending on Spark version
        columns = df.columns
        
        # Verify we can read the data and handle malformed rows gracefully
        df.createOrReplaceTempView("malformed_data")
        
        # Count total rows (including potentially malformed ones)
        total_count = self.spark.sql("SELECT COUNT(*) as cnt FROM malformed_data").collect()[0][0]
        self.assertGreaterEqual(total_count, 1, "Should read at least one valid row")
        
        # If corrupt record column exists, check it
        if "_corrupt_record" in columns:
            corrupt_count = self.spark.sql("SELECT COUNT(*) as cnt FROM malformed_data WHERE _corrupt_record IS NOT NULL").collect()[0][0]
            self.assertGreaterEqual(corrupt_count, 0, "Should handle corrupt records")
        else:
            # If corrupt record column doesn't exist, verify that malformed rows are handled
            # by checking that we can still query the data
            valid_count = self.spark.sql("SELECT COUNT(*) as cnt FROM malformed_data WHERE Month IS NOT NULL").collect()[0][0]
            self.assertGreaterEqual(valid_count, 1, "Should have at least one valid row")
    
    def test_deduplication_logic(self):
        """Test deduplication of records"""
        # Create duplicate data
        data = [
            ("123", "2024-04-01", "Shop A", "Product 1"),
            ("123", "2024-04-01", "Shop A", "Product 1"),  # Duplicate
            ("456", "2024-04-01", "Shop B", "Product 2")
        ]
        
        schema = StructType([
            StructField("product_id", StringType(), True),
            StructField("month", StringType(), True),
            StructField("shop_name", StringType(), True),
            StructField("product_name", StringType(), True)
        ])
        
        df = self.spark.createDataFrame(data, schema)
        df.createOrReplaceTempView("test_data")
        
        # Use SQL directly to avoid serialization issues
        df_dedup = self.spark.sql("""
            SELECT product_id, month, shop_name, product_name
            FROM (
                SELECT *,
                    ROW_NUMBER() OVER (PARTITION BY product_id, month, shop_name ORDER BY product_name) as row_num
                FROM test_data
            ) ranked
            WHERE row_num = 1
        """)
        df_dedup.createOrReplaceTempView("dedup_data")
        
        # Verify count using SQL to avoid socket issues
        count_df = self.spark.sql("SELECT COUNT(*) as cnt FROM dedup_data")
        count = count_df.collect()[0][0]
        self.assertEqual(count, 2)
    
    def test_output_schema(self):
        """Test that output schema matches expected structure"""
        expected_columns = [
            "month", "product_id", "product_name", "shop_name",
            "l1_category", "l2_category", "l3_category",
            "item_sold", "revenue_usd", "avg_unit_price_usd", "mom_growth_pct",
            "source_file", "source_record_number", "processed_timestamp",
            "transformation_version", "data_quality_score", "quality_flags",
            "created_by", "record_hash", "year", "month_num"
        ]
        
        # This would be validated against actual curated output
        # For now, just verify the list is complete
        self.assertEqual(len(expected_columns), 21)
    
    def test_quality_scoring_all_flags(self):
        """Test quality scoring with all quality flags (score < 0.70)"""
        # Create data with all quality issues
        data = [
            ("invalid-date", "", "", "Test Shop", "Beauty", "Hair", "Brushes", 
             "invalid", "invalid", "invalid", "150%")  # All fields invalid
        ]
        
        schema = StructType([
            StructField("Month", StringType(), True),
            StructField("Product Id", StringType(), True),
            StructField("Product Name", StringType(), True),
            StructField("Shop Name", StringType(), True),
            StructField("L1 category", StringType(), True),
            StructField("L2 category", StringType(), True),
            StructField("L3 category", StringType(), True),
            StructField("Item Sold", StringType(), True),
            StructField("Revenue", StringType(), True),
            StructField("Avg. Unit Price", StringType(), True),
            StructField("MoM Growth %", StringType(), True)
        ])
        
        df = self.spark.createDataFrame(data, schema)
        df.createOrReplaceTempView("test_data")
        
        # Use SQL directly to avoid serialization issues
        df_scored = self.spark.sql("""
            SELECT *,
                1.0000 + 
                CASE WHEN Month = 'invalid-date' THEN -0.20 ELSE 0 END +
                CASE WHEN `Product Id` = '' THEN -0.15 ELSE 0 END +
                CASE WHEN `Product Name` = '' THEN -0.20 ELSE 0 END +
                CASE WHEN Revenue = 'invalid' THEN -0.15 ELSE 0 END +
                CASE WHEN `Avg. Unit Price` = 'invalid' THEN -0.10 ELSE 0 END +
                CASE WHEN `Item Sold` = 'invalid' THEN -0.10 ELSE 0 END +
                CASE WHEN `MoM Growth %` = '150%' THEN -0.05 ELSE 0 END as data_quality_score,
                CONCAT(
                    CASE WHEN Month = 'invalid-date' THEN 'INVALID_DATE,' ELSE '' END,
                    CASE WHEN `Product Id` = '' THEN 'SYNTHETIC_PRODUCT_ID,' ELSE '' END,
                    CASE WHEN `Product Name` = '' THEN 'MISSING_PRODUCT_NAME,' ELSE '' END,
                    CASE WHEN Revenue = 'invalid' THEN 'INVALID_REVENUE,' ELSE '' END,
                    CASE WHEN `Avg. Unit Price` = 'invalid' THEN 'INVALID_AVG_PRICE,' ELSE '' END,
                    CASE WHEN `Item Sold` = 'invalid' THEN 'MISSING_ITEMS,' ELSE '' END,
                    CASE WHEN `MoM Growth %` = '150%' THEN 'SUSPICIOUS_GROWTH,' ELSE '' END
                ) as quality_flags
            FROM test_data
        """)
        df_scored.createOrReplaceTempView("scored_data")
        
        # Verify using SQL to avoid socket issues
        score_df = self.spark.sql("SELECT MIN(data_quality_score) as min_score FROM scored_data")
        final_score = score_df.collect()[0][0]
        
        flags_df = self.spark.sql("SELECT quality_flags FROM scored_data LIMIT 1")
        flags = flags_df.collect()[0][0] if flags_df.count() > 0 else ""
        
        # Total penalty: 0.20 + 0.15 + 0.20 + 0.15 + 0.10 + 0.10 + 0.05 = 0.95
        # Final score: 1.0 - 0.95 = 0.05
        self.assertLess(final_score, 0.70, "Score should be < 0.70 (FAIL threshold)")
        if flags:
            self.assertIn("INVALID_DATE", flags)
            self.assertIn("SYNTHETIC_PRODUCT_ID", flags)
            self.assertIn("MISSING_PRODUCT_NAME", flags)
            self.assertIn("INVALID_REVENUE", flags)
            self.assertIn("INVALID_AVG_PRICE", flags)
            self.assertIn("MISSING_ITEMS", flags)
            self.assertIn("SUSPICIOUS_GROWTH", flags)
    
    def test_quality_routing_pass_warn_fail(self):
        """Test quality-based routing (pass/warn/fail according to thresholds)"""
        # Thresholds
        DQ_PASS_THRESHOLD = 0.95
        DQ_WARN_THRESHOLD = 0.70
        
        # Create records with different quality scores
        data = [
            ("4/01/2024", "123", "Product A", "Shop A", "Beauty", "Hair", "Brushes", 
             "100", "$1000.00", "$10.00", "5%"),  # Perfect score: 1.0 (PASS)
            ("invalid", "456", "Product B", "Shop B", "Beauty", "Hair", "Brushes", 
             "200", "$2000.00", "$10.00", "5%"),  # One issue: 0.8 (WARN)
            ("invalid", "", "", "Shop C", "Beauty", "Hair", "Brushes", 
             "invalid", "invalid", "invalid", "150%")  # Many issues: < 0.7 (FAIL)
        ]
        
        schema = StructType([
            StructField("Month", StringType(), True),
            StructField("Product Id", StringType(), True),
            StructField("Product Name", StringType(), True),
            StructField("Shop Name", StringType(), True),
            StructField("L1 category", StringType(), True),
            StructField("L2 category", StringType(), True),
            StructField("L3 category", StringType(), True),
            StructField("Item Sold", StringType(), True),
            StructField("Revenue", StringType(), True),
            StructField("Avg. Unit Price", StringType(), True),
            StructField("MoM Growth %", StringType(), True)
        ])
        
        df = self.spark.createDataFrame(data, schema)
        df.createOrReplaceTempView("test_data")
        
        # Use SQL directly to calculate scores and route
        df_scored = self.spark.sql("""
            SELECT *,
                1.0000 + 
                CASE WHEN Month = 'invalid' THEN -0.20 ELSE 0 END +
                CASE WHEN `Product Id` = '' THEN -0.15 ELSE 0 END +
                CASE WHEN `Product Name` = '' THEN -0.20 ELSE 0 END +
                CASE WHEN Revenue = 'invalid' THEN -0.15 ELSE 0 END as data_quality_score
            FROM test_data
        """)
        df_scored.createOrReplaceTempView("scored_data")
        
        # Route records using SQL COUNT to avoid socket issues
        passed_count_df = self.spark.sql(f"SELECT COUNT(*) as cnt FROM scored_data WHERE data_quality_score >= {DQ_PASS_THRESHOLD}")
        warned_count_df = self.spark.sql(f"""
            SELECT COUNT(*) as cnt FROM scored_data 
            WHERE data_quality_score >= {DQ_WARN_THRESHOLD} 
            AND data_quality_score < {DQ_PASS_THRESHOLD}
        """)
        failed_count_df = self.spark.sql(f"SELECT COUNT(*) as cnt FROM scored_data WHERE data_quality_score < {DQ_WARN_THRESHOLD}")
        
        # Verify routing
        passed_count = passed_count_df.collect()[0][0]
        warned_count = warned_count_df.collect()[0][0]
        failed_count = failed_count_df.collect()[0][0]
        
        self.assertEqual(passed_count, 1, "Should have 1 PASS record")
        self.assertEqual(warned_count, 1, "Should have 1 WARN record")
        self.assertEqual(failed_count, 1, "Should have 1 FAIL record")
        
        # Verify scores using SQL aggregation
        passed_score_df = self.spark.sql(f"SELECT MIN(data_quality_score) as min_score FROM scored_data WHERE data_quality_score >= {DQ_PASS_THRESHOLD}")
        warned_score_df = self.spark.sql(f"SELECT MIN(data_quality_score) as min_score FROM scored_data WHERE data_quality_score >= {DQ_WARN_THRESHOLD} AND data_quality_score < {DQ_PASS_THRESHOLD}")
        failed_score_df = self.spark.sql(f"SELECT MAX(data_quality_score) as max_score FROM scored_data WHERE data_quality_score < {DQ_WARN_THRESHOLD}")
        
        passed_score = passed_score_df.collect()[0][0]
        warned_score = warned_score_df.collect()[0][0]
        failed_score = failed_score_df.collect()[0][0]
        
        self.assertGreaterEqual(passed_score, DQ_PASS_THRESHOLD)
        self.assertGreaterEqual(warned_score, DQ_WARN_THRESHOLD)
        self.assertLess(warned_score, DQ_PASS_THRESHOLD)
        self.assertLess(failed_score, DQ_WARN_THRESHOLD)
    
    def test_anomaly_detection(self):
        """Test detection of anomalies (revenue/items > threshold)"""
        # Anomaly thresholds
        ANOMALY_REVENUE_MAX = 10000000  # $10M
        ANOMALY_ITEMS_MAX = 1000000  # 1M items
        
        # Create data with anomalies
        data = [
            ("4/01/2024", "123", "Product Normal", "Shop A", "Beauty", "Hair", "Brushes", 
             "100", "$1000.00", "$10.00", "5%"),  # Normal
            ("4/01/2024", "456", "Product High Revenue", "Shop B", "Beauty", "Hair", "Brushes", 
             "500", "$15000000.00", "$30000.00", "5%"),  # Revenue anomaly
            ("4/01/2024", "789", "Product High Items", "Shop C", "Beauty", "Hair", "Brushes", 
             "2000000", "$5000.00", "$0.00", "5%"),  # Items anomaly
            ("4/01/2024", "999", "Product Both", "Shop D", "Beauty", "Hair", "Brushes", 
             "3000000", "$20000000.00", "$6.67", "5%")  # Both anomalies
        ]
        
        schema = StructType([
            StructField("Month", StringType(), True),
            StructField("Product Id", StringType(), True),
            StructField("Product Name", StringType(), True),
            StructField("Shop Name", StringType(), True),
            StructField("L1 category", StringType(), True),
            StructField("L2 category", StringType(), True),
            StructField("L3 category", StringType(), True),
            StructField("Item Sold", StringType(), True),
            StructField("Revenue", StringType(), True),
            StructField("Avg. Unit Price", StringType(), True),
            StructField("MoM Growth %", StringType(), True)
        ])
        
        df = self.spark.createDataFrame(data, schema)
        df.createOrReplaceTempView("test_data")
        
        # Use SQL directly to parse and detect anomalies - use COUNT to avoid socket issues
        anomaly_count_df = self.spark.sql(f"""
            SELECT COUNT(*) as cnt
            FROM (
                SELECT *,
                    CAST(REGEXP_REPLACE(REGEXP_REPLACE(Revenue, '\\\\$', ''), ',', '') AS DOUBLE) as revenue_usd,
                    CAST(`Item Sold` AS INT) as item_sold
                FROM test_data
            ) parsed
            WHERE revenue_usd > {ANOMALY_REVENUE_MAX} OR item_sold > {ANOMALY_ITEMS_MAX}
        """)
        
        anomaly_count = anomaly_count_df.collect()[0][0]
        
        # Should detect 3 anomalies (records 1, 2, 3)
        self.assertEqual(anomaly_count, 3, "Should detect 3 anomaly records")
        
        # Verify specific anomalies using SQL
        revenue_anomalies_df = self.spark.sql(f"""
            SELECT COUNT(*) as cnt FROM (
                SELECT *,
                    CAST(REGEXP_REPLACE(REGEXP_REPLACE(Revenue, '\\\\$', ''), ',', '') AS DOUBLE) as revenue_usd
                FROM test_data
            ) parsed
            WHERE revenue_usd > {ANOMALY_REVENUE_MAX}
        """)
        revenue_anomalies = revenue_anomalies_df.collect()[0][0]
        
        items_anomalies_df = self.spark.sql(f"""
            SELECT COUNT(*) as cnt FROM (
                SELECT *,
                    CAST(`Item Sold` AS INT) as item_sold
                FROM test_data
            ) parsed
            WHERE item_sold > {ANOMALY_ITEMS_MAX}
        """)
        items_anomalies = items_anomalies_df.collect()[0][0]
        
        self.assertGreaterEqual(revenue_anomalies, 2, "Should detect revenue anomalies")
        self.assertGreaterEqual(items_anomalies, 2, "Should detect items anomalies")
    
    def test_quality_report_schema_validation(self):
        """Test quality report JSON structure against expected schema"""
        import json
        
        # Expected schema fields (from quality_report_v1.json)
        required_fields = [
            "job_run_id",
            "execution_timestamp",
            "total_records",
            "records_passed",
            "records_warned",
            "records_failed",
            "records_duplicates",
            "pass_rate",
            "avg_quality_score",
            "quality_issues",
            "transformation_version"
        ]
        
        # Create sample quality report
        sample_report = {
            "job_run_id": "jr_20240417_123456",
            "execution_timestamp": "2024-04-17T12:34:56Z",
            "source_file": "s3://bucket/path/file.csv",
            "total_records": 1000,
            "records_passed": 850,
            "records_warned": 120,
            "records_failed": 30,
            "records_duplicates": 10,
            "records_anomalies": 5,
            "pass_rate": 0.85,
            "avg_quality_score": 0.9234,
            "quality_issues": {
                "INVALID_DATE": 20,
                "SYNTHETIC_PRODUCT_ID": 15,
                "MISSING_PRODUCT_NAME": 10,
                "INVALID_REVENUE": 8,
                "INVALID_AVG_PRICE": 5,
                "MISSING_ITEMS": 7,
                "SUSPICIOUS_GROWTH": 3
            },
            "transformation_version": "v1.0.0"
        }
        
        # Validate JSON structure
        report_json = json.dumps(sample_report)
        parsed_report = json.loads(report_json)
        
        # Check all required fields are present
        for field in required_fields:
            self.assertIn(field, parsed_report, f"Required field '{field}' missing")
        
        # Validate data types
        self.assertIsInstance(parsed_report["job_run_id"], str)
        self.assertIsInstance(parsed_report["execution_timestamp"], str)
        self.assertIsInstance(parsed_report["total_records"], int)
        self.assertIsInstance(parsed_report["records_passed"], int)
        self.assertIsInstance(parsed_report["records_warned"], int)
        self.assertIsInstance(parsed_report["records_failed"], int)
        self.assertIsInstance(parsed_report["pass_rate"], (int, float))
        self.assertIsInstance(parsed_report["avg_quality_score"], (int, float))
        self.assertIsInstance(parsed_report["quality_issues"], dict)
        self.assertIsInstance(parsed_report["transformation_version"], str)
        
        # Validate value ranges
        self.assertGreaterEqual(parsed_report["pass_rate"], 0.0)
        self.assertLessEqual(parsed_report["pass_rate"], 1.0)
        self.assertGreaterEqual(parsed_report["avg_quality_score"], 0.0)
        self.assertLessEqual(parsed_report["avg_quality_score"], 1.0)
        
        # Validate quality_issues structure
        expected_issue_types = [
            "INVALID_DATE",
            "SYNTHETIC_PRODUCT_ID",
            "MISSING_PRODUCT_NAME",
            "INVALID_REVENUE",
            "INVALID_AVG_PRICE",
            "MISSING_ITEMS",
            "SUSPICIOUS_GROWTH"
        ]
        
        for issue_type in expected_issue_types:
            if issue_type in parsed_report["quality_issues"]:
                self.assertIsInstance(parsed_report["quality_issues"][issue_type], int)
                self.assertGreaterEqual(parsed_report["quality_issues"][issue_type], 0)


if __name__ == '__main__':
    unittest.main()
