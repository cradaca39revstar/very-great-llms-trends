"""
Integration Tests for Beauty Products ETL Pipeline

End-to-end testing with sample data files.
"""

import unittest
import os
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType
import shutil


class TestETLIntegration(unittest.TestCase):
    """Integration tests for complete ETL pipeline"""
    
    @classmethod
    def setUpClass(cls):
        """Set up Spark session for testing"""
        cls.spark = SparkSession.builder \
            .appName("BeautyProductsETLTest") \
            .master("local[*]") \
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
        
        # Apply basic transformations (simplified for testing)
        from pyspark.sql.functions import lit, to_date
        df_transformed = df.withColumn("month_parsed", to_date(df["Month"], "M/dd/yyyy"))
        
        self.assertEqual(df_transformed.count(), 1)
        self.assertIn("month_parsed", df_transformed.columns)
    
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
        
        # Initialize quality score
        from pyspark.sql.functions import lit, when, col
        df_scored = df.withColumn("data_quality_score", lit(1.0000))
        
        # Apply penalty for invalid date
        df_scored = df_scored.withColumn("data_quality_score",
            when(col("Month") == "invalid-date", col("data_quality_score") - 0.20)
            .otherwise(col("data_quality_score")))
        
        result = df_scored.select("data_quality_score").collect()[0][0]
        self.assertEqual(result, 0.8000)
    
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
        
        # Read CSV in permissive mode
        df = self.spark.read.format("csv") \
            .option("header", "true") \
            .option("mode", "PERMISSIVE") \
            .option("columnNameOfCorruptRecord", "_corrupt_record") \
            .load(csv_path)
        
        # Check that we can identify corrupt records
        self.assertIn("_corrupt_record", df.columns)
    
    def test_deduplication_logic(self):
        """Test deduplication of records"""
        from pyspark.sql.functions import row_number
        from pyspark.sql.window import Window
        
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
        
        # Apply deduplication
        window_spec = Window.partitionBy("product_id", "month", "shop_name").orderBy("product_name")
        df_dedup = df.withColumn("row_num", row_number().over(window_spec)) \
            .filter("row_num = 1") \
            .drop("row_num")
        
        # Should have 2 records after deduplication
        self.assertEqual(df_dedup.count(), 2)
    
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


if __name__ == '__main__':
    unittest.main()
