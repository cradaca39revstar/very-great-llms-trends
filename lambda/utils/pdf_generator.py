"""
PDF Report Generator Module
Creates professional PDF reports using FPDF
"""

import os
from datetime import datetime, timezone
from typing import Dict, List
import boto3
from fpdf import FPDF

# AWS S3 client
s3_client = boto3.client('s3', region_name=os.environ.get('AWS_REGION_NAME', 'us-east-1'))


class TrendingProductsPDF(FPDF):
    """Custom PDF class for trending products reports"""
    
    def __init__(self, report_data: Dict):
        super().__init__()
        self.report_data = report_data
        
    def header(self):
        """Page header"""
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'Trending Products Report', 0, 1, 'C')
        self.set_font('Arial', '', 10)
        self.cell(0, 5, f"Category: {self.report_data.get('category', '')}", 0, 1, 'C')
        self.ln(5)
    
    def footer(self):
        """Page footer"""
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f"Page {self.page_no()}", 0, 0, 'C')


def generate_pdf_report(report: Dict) -> bytes:
    """
    Generate PDF report from formatted report data
    
    Args:
        report: Formatted report dict with products
        
    Returns:
        PDF file as bytes
    """
    pdf = TrendingProductsPDF(report)
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Add title page
    add_title_page(pdf, report)
    
    # Add each product
    products = report.get('products', [])
    for product in products:
        add_product_page(pdf, product)
    
    # Get PDF as bytes (fpdf2 2.8+ output() returns bytearray; no .encode())
    pdf_bytes = bytes(pdf.output())

    return pdf_bytes


def add_title_page(pdf: FPDF, report: Dict):
    """Add title/cover page to PDF"""
    pdf.add_page()
    
    # Title
    pdf.set_font('Arial', 'B', 24)
    pdf.ln(30)
    pdf.cell(0, 10, 'Trending Products Report', 0, 1, 'C')
    
    # Category
    pdf.set_font('Arial', 'B', 18)
    pdf.ln(10)
    pdf.cell(0, 10, f"Category: {report.get('category', '')}", 0, 1, 'C')
    
    # Metadata
    pdf.set_font('Arial', '', 12)
    pdf.ln(20)
    pdf.cell(0, 8, f"Generated: {format_timestamp(report.get('generated_at', ''))}", 0, 1, 'C')
    pdf.cell(0, 8, f"Data Period: {report.get('data_period', 'Last 30 Days')}", 0, 1, 'C')
    pdf.cell(0, 8, f"Number of Products: {len(report.get('products', []))}", 0, 1, 'C')
    
    # Summary
    pdf.ln(20)
    pdf.set_font('Arial', '', 11)
    pdf.multi_cell(0, 6, 
        f"This report presents the top {len(report.get('products', []))} trending products "
        f"in the {report.get('category', '')} category based on revenue performance and "
        f"month-over-month growth over the last 30 days. Each product includes AI-generated "
        f"market trend analysis."
    )


def add_product_page(pdf: FPDF, product: Dict):
    """Add product details page"""
    pdf.add_page()
    
    rank = product.get('rank', 0)
    
    # Product header
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 10, f"Trending Product #{rank}", 0, 1, 'L')
    pdf.ln(5)
    
    # Brand name
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 8, f"Brand Name: {product.get('brand_name', 'Unknown')}", 0, 1, 'L')
    
    # Product name
    pdf.set_font('Arial', '', 12)
    pdf.multi_cell(0, 6, f"Product: {product.get('product_name', '')}")
    pdf.ln(2)
    
    # URL (if available)
    if product.get('brand_url'):
        pdf.set_font('Arial', 'U', 10)
        pdf.set_text_color(0, 0, 255)
        pdf.cell(0, 6, f"URL: {product.get('brand_url', '')}", 0, 1, 'L')
        pdf.set_text_color(0, 0, 0)
    pdf.ln(2)
    
    # Description
    pdf.set_font('Arial', '', 11)
    pdf.multi_cell(0, 5, f"Description: {product.get('description', '')}")
    pdf.ln(5)
    
    # Revenue metrics box
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 8, 'Revenue Metrics', 0, 1, 'L')
    pdf.set_font('Arial', '', 11)
    
    # Metrics table
    metrics = [
        ('Revenue Trend:', product.get('revenue_trend', '')),
        ('Revenue Scale:', product.get('revenue_scale', '')),
        ('Product Rank in Category:', product.get('category_rank', ''))
    ]
    
    for label, value in metrics:
        pdf.set_font('Arial', 'B', 11)
        pdf.cell(60, 6, label, 0, 0, 'L')
        pdf.set_font('Arial', '', 11)
        pdf.cell(0, 6, value, 0, 1, 'L')
    
    pdf.ln(5)
    
    # Supporting trends
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 8, 'Supporting Trends:', 0, 1, 'L')
    pdf.ln(2)
    
    pdf.set_font('Arial', '', 11)
    intro_text = (
        f"Here are 5 macro trends that are driving the success of "
        f"{product.get('brand_name', '')} {product.get('product_name', '')}, "
        f"and which have helped make it one of the most dominant products in the market:"
    )
    pdf.multi_cell(0, 5, intro_text)
    pdf.ln(3)
    
    # List trends
    trends = product.get('supporting_trends', [])
    for i, trend in enumerate(trends, 1):
        # Parse trend title and explanation
        trend_parts = parse_trend_text(trend)
        
        # Trend number and title
        pdf.set_font('Arial', 'B', 11)
        pdf.multi_cell(0, 5, f"{i}. {trend_parts['title']}")
        
        # Trend explanation
        pdf.set_font('Arial', '', 10)
        pdf.multi_cell(0, 5, trend_parts['explanation'])
        pdf.ln(2)


def parse_trend_text(trend: str) -> Dict:
    """
    Parse trend text into title and explanation
    
    Args:
        trend: Trend text (may include title on first line)
        
    Returns:
        Dict with 'title' and 'explanation'
    """
    lines = trend.split('\n', 1)
    
    if len(lines) == 2:
        return {
            'title': lines[0].strip(),
            'explanation': lines[1].strip()
        }
    else:
        # Single paragraph - use first sentence as title
        sentences = trend.split('. ', 1)
        if len(sentences) == 2:
            return {
                'title': sentences[0],
                'explanation': sentences[1]
            }
        else:
            return {
                'title': 'Market Trend',
                'explanation': trend
            }


def upload_pdf_to_s3(pdf_bytes: bytes, bucket: str, key: str, expiration: int = 3600) -> str:
    """
    Upload PDF to S3 and generate pre-signed URL
    
    Args:
        pdf_bytes: PDF file as bytes
        bucket: S3 bucket name
        key: S3 object key
        expiration: URL expiration in seconds (default 1 hour)
        
    Returns:
        Pre-signed URL for PDF download
    """
    # Upload PDF to S3
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=pdf_bytes,
        ContentType='application/pdf',
        ContentDisposition='inline; filename="trending-products-report.pdf"'
    )
    
    print(f"PDF uploaded to s3://{bucket}/{key}")
    
    # Generate pre-signed URL
    url = s3_client.generate_presigned_url(
        'get_object',
        Params={
            'Bucket': bucket,
            'Key': key
        },
        ExpiresIn=expiration
    )
    
    return url


def format_timestamp(iso_timestamp: str) -> str:
    """
    Format ISO timestamp for display
    
    Args:
        iso_timestamp: ISO 8601 timestamp
        
    Returns:
        Formatted string (e.g., "January 26, 2026 at 10:05 AM")
    """
    try:
        dt = datetime.fromisoformat(iso_timestamp.replace('Z', '+00:00'))
        return dt.strftime('%B %d, %Y at %I:%M %p')
    except:
        return iso_timestamp
