"""
Unit Tests for Beauty Products ETL Transformations

Tests all transformation functions and quality scoring logic.
"""

import unittest
from datetime import datetime
from decimal import Decimal
import sys
sys.path.append('../scripts')


class TestDateParsing(unittest.TestCase):
    """Test date parsing transformations"""
    
    def test_parse_standard_date(self):
        """Test parsing standard M/DD/YYYY format"""
        from beauty_products_etl import parse_date_field
        result = parse_date_field("4/01/2024")
        self.assertEqual(result, "2024-04-01")
    
    def test_parse_double_digit_month(self):
        """Test parsing MM/DD/YYYY format"""
        from beauty_products_etl import parse_date_field
        result = parse_date_field("12/25/2024")
        self.assertEqual(result, "2024-12-25")
    
    def test_parse_null_date(self):
        """Test parsing null/empty date"""
        from beauty_products_etl import parse_date_field
        self.assertIsNone(parse_date_field(""))
        self.assertIsNone(parse_date_field(None))
    
    def test_parse_invalid_date(self):
        """Test parsing invalid date format"""
        from beauty_products_etl import parse_date_field
        result = parse_date_field("invalid-date")
        self.assertIsNone(result)


class TestProductIdNormalization(unittest.TestCase):
    """Test product ID normalization"""
    
    def test_normalize_scientific_notation(self):
        """Test normalization of scientific notation with commas"""
        from beauty_products_etl import normalize_product_id
        result = normalize_product_id("1,72938E+18")
        self.assertIsNotNone(result)
        self.assertIsInstance(result, int)
    
    def test_normalize_regular_number(self):
        """Test normalization of regular number"""
        from beauty_products_etl import normalize_product_id
        result = normalize_product_id("123456789")
        self.assertEqual(result, 123456789)
    
    def test_normalize_null_product_id(self):
        """Test handling of null product ID"""
        from beauty_products_etl import normalize_product_id
        self.assertIsNone(normalize_product_id(""))
        self.assertIsNone(normalize_product_id(None))
    
    def test_normalize_negative_product_id(self):
        """Test handling of negative product ID"""
        from beauty_products_etl import normalize_product_id
        result = normalize_product_id("-12345")
        self.assertIsNone(result)


class TestTextNormalization(unittest.TestCase):
    """Test text field normalization"""
    
    def test_trim_whitespace(self):
        """Test trimming leading/trailing whitespace"""
        from beauty_products_etl import normalize_text_field
        result = normalize_text_field("  Product Name  ")
        self.assertEqual(result, "Product Name")
    
    def test_collapse_multiple_spaces(self):
        """Test collapsing multiple spaces"""
        from beauty_products_etl import normalize_text_field
        result = normalize_text_field("Product    Name")
        self.assertEqual(result, "Product Name")
    
    def test_max_length_truncation(self):
        """Test maximum length truncation"""
        from beauty_products_etl import normalize_text_field
        long_text = "A" * 1000
        result = normalize_text_field(long_text, max_length=100)
        self.assertEqual(len(result), 100)
    
    def test_null_text(self):
        """Test handling of null text"""
        from beauty_products_etl import normalize_text_field
        self.assertIsNone(normalize_text_field(""))
        self.assertIsNone(normalize_text_field(None))


class TestCurrencyParsing(unittest.TestCase):
    """Test currency parsing"""
    
    def test_parse_currency_with_symbol(self):
        """Test parsing currency with $ symbol"""
        from beauty_products_etl import parse_currency_field
        result = parse_currency_field("$305,785.10")
        self.assertEqual(result, 305785.10)
    
    def test_parse_currency_without_symbol(self):
        """Test parsing currency without symbol"""
        from beauty_products_etl import parse_currency_field
        result = parse_currency_field("12.66")
        self.assertEqual(result, 12.66)
    
    def test_parse_currency_with_thousands(self):
        """Test parsing currency with thousands separator"""
        from beauty_products_etl import parse_currency_field
        result = parse_currency_field("1,234,567.89")
        self.assertEqual(result, 1234567.89)
    
    def test_parse_negative_currency(self):
        """Test handling of negative currency"""
        from beauty_products_etl import parse_currency_field
        result = parse_currency_field("-100.00")
        self.assertIsNone(result)
    
    def test_parse_null_currency(self):
        """Test handling of null currency"""
        from beauty_products_etl import parse_currency_field
        self.assertIsNone(parse_currency_field(""))
        self.assertIsNone(parse_currency_field(None))


class TestPercentageParsing(unittest.TestCase):
    """Test percentage parsing"""
    
    def test_parse_negative_percentage(self):
        """Test parsing negative percentage"""
        from beauty_products_etl import parse_percentage_field
        result = parse_percentage_field("-42%")
        self.assertEqual(result, -0.42)
    
    def test_parse_positive_percentage(self):
        """Test parsing positive percentage"""
        from beauty_products_etl import parse_percentage_field
        result = parse_percentage_field("15%")
        self.assertEqual(result, 0.15)
    
    def test_parse_percentage_without_symbol(self):
        """Test parsing percentage without % symbol"""
        from beauty_products_etl import parse_percentage_field
        result = parse_percentage_field("25")
        self.assertEqual(result, 0.25)
    
    def test_parse_null_percentage(self):
        """Test handling of null percentage"""
        from beauty_products_etl import parse_percentage_field
        self.assertIsNone(parse_percentage_field(""))
        self.assertIsNone(parse_percentage_field(None))


class TestIntegerParsing(unittest.TestCase):
    """Test integer parsing"""
    
    def test_parse_integer_with_commas(self):
        """Test parsing integer with thousands separators"""
        from beauty_products_etl import parse_integer_field
        result = parse_integer_field("24,157")
        self.assertEqual(result, 24157)
    
    def test_parse_integer_without_commas(self):
        """Test parsing integer without separators"""
        from beauty_products_etl import parse_integer_field
        result = parse_integer_field("12345")
        self.assertEqual(result, 12345)
    
    def test_parse_negative_integer(self):
        """Test handling of negative integer"""
        from beauty_products_etl import parse_integer_field
        result = parse_integer_field("-100")
        self.assertIsNone(result)
    
    def test_parse_null_integer(self):
        """Test handling of null integer"""
        from beauty_products_etl import parse_integer_field
        self.assertIsNone(parse_integer_field(""))
        self.assertIsNone(parse_integer_field(None))


class TestDataQualityScoring(unittest.TestCase):
    """Test data quality score calculations"""
    
    def test_perfect_score(self):
        """Test calculation for perfect quality score"""
        # All fields valid, should start at 1.0000
        score = 1.0000
        self.assertEqual(score, 1.0000)
    
    def test_invalid_date_penalty(self):
        """Test penalty for invalid date"""
        score = 1.0000 - 0.20
        self.assertEqual(score, 0.8000)
    
    def test_multiple_penalties(self):
        """Test cumulative penalties"""
        score = 1.0000
        score -= 0.20  # Invalid date
        score -= 0.15  # Synthetic product_id
        score -= 0.10  # Invalid revenue
        self.assertEqual(score, 0.5500)
    
    def test_minimum_score(self):
        """Test that score doesn't go below 0"""
        score = max(0.0000, 1.0000 - 2.0000)
        self.assertEqual(score, 0.0000)


if __name__ == '__main__':
    unittest.main()
