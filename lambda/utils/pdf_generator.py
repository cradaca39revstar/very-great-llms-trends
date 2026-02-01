"""
PDF Report Generator Module
Creates professional PDF reports using FPDF (fpdf2).
All body text uses effective page width (epw) and set_x(l_margin) so content
wraps within margins and does not overflow.
"""

import os
from datetime import datetime, timezone
from typing import Dict, List
import boto3
from fpdf import FPDF

# -----------------------------------------------------------------------------
# Layout constants (tweak here for global layout changes)
# -----------------------------------------------------------------------------
# Page margins in mm (FPDF default unit). Left/right/top/bottom.
PAGE_MARGIN_MM = 15
# Bottom margin reserved for footer (used by set_auto_page_break)
PAGE_BOTTOM_MARGIN_MM = 15
# Font sizes (pt): title, heading, body, small
FONT_SIZE_TITLE = 24
FONT_SIZE_HEADING = 16
FONT_SIZE_SUBHEADING = 12
FONT_SIZE_BODY = 11
FONT_SIZE_SMALL = 10
# Line height multiplier for multi_cell (pt per line)
LINE_HEIGHT_BODY = 5
LINE_HEIGHT_TITLE = 6
# Max URL length before truncation with ellipsis (avoids overflow)
MAX_URL_DISPLAY_LEN = 80

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
        self.cell(0, 5, _sanitize_pdf_text(f"Category: {self.report_data.get('category', '')}"), 0, 1, 'C')
        self.ln(5)
    
    def footer(self):
        """Page footer"""
        self.set_y(-15)
        self.set_x(self.l_margin)
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
    pdf.set_margins(PAGE_MARGIN_MM, PAGE_MARGIN_MM, PAGE_MARGIN_MM)
    pdf.set_auto_page_break(auto=True, margin=PAGE_BOTTOM_MARGIN_MM)
    pdf.set_x(pdf.l_margin)
    pdf.set_y(pdf.t_margin)
    products = report.get('products', [])
    
    # Add title page
    add_title_page(pdf, report)
    
    # Add each product
    for product in products:
        add_product_page(pdf, product)
    
    # Get PDF as bytes (fpdf2 2.8+ output() returns bytearray; no .encode())
    pdf_bytes = bytes(pdf.output())

    return pdf_bytes


def add_title_page(pdf: FPDF, report: Dict):
    """Add title/cover page to PDF. All text uses content width and respects margins."""
    pdf.add_page()
    pdf.set_x(pdf.l_margin)
    
    # Title
    pdf.set_font('Arial', 'B', FONT_SIZE_TITLE)
    pdf.ln(30)
    pdf.cell(0, 10, 'Trending Products Report', 0, 1, 'C')
    
    # Category
    pdf.set_font('Arial', 'B', 18)
    pdf.ln(10)
    pdf.cell(0, 10, _sanitize_pdf_text(f"Category: {report.get('category', '')}"), 0, 1, 'C')
    
    # Metadata
    pdf.set_font('Arial', '', FONT_SIZE_SUBHEADING)
    pdf.ln(20)
    pdf.cell(0, 8, f"Generated: {format_timestamp(report.get('generated_at', ''))}", 0, 1, 'C')
    pdf.cell(0, 8, f"Data Period: {report.get('data_period', 'Last 30 Days')}", 0, 1, 'C')
    pdf.cell(0, 8, f"Number of Products: {len(report.get('products', []))}", 0, 1, 'C')
    
    # Summary paragraph (full content width, word-wrapped)
    pdf.ln(20)
    pdf.set_font('Arial', '', FONT_SIZE_BODY)
    pdf.set_x(pdf.l_margin)
    summary = _sanitize_pdf_text(
        f"This report presents the top {len(report.get('products', []))} trending products "
        f"in the {report.get('category', '')} category based on revenue performance and "
        f"month-over-month growth over the last 30 days. Each product includes AI-generated "
        f"market trend analysis."
    )
    pdf.multi_cell(_content_width(pdf), LINE_HEIGHT_TITLE, summary)


def _sanitize_pdf_text(s: str) -> str:
    """Replace Unicode chars not in Latin-1 (helvetica) with ASCII equivalents."""
    if not s or not isinstance(s, str):
        return s
    replacements = (
        ('\u2019', "'"),   # RIGHT SINGLE QUOTATION MARK
        ('\u2018', "'"),   # LEFT SINGLE QUOTATION MARK
        ('\u201c', '"'),   # LEFT DOUBLE QUOTATION MARK
        ('\u201d', '"'),   # RIGHT DOUBLE QUOTATION MARK
        ('\u2014', "-"),   # EM DASH
        ('\u2013', "-"),   # EN DASH
        ('\u2026', "..."), # HORIZONTAL ELLIPSIS
    )
    out = s
    for u, a in replacements:
        out = out.replace(u, a)
    return out


def _content_width(pdf: FPDF) -> float:
    """Full content width (epw) for body text. Use after set_x(l_margin) for consistent wrapping."""
    return pdf.epw


def _safe_width(pdf: FPDF, min_w: float = 10.0) -> float:
    """Width from current x to right margin; for two-column rows (e.g. metrics label + value)."""
    w = pdf.w - pdf.r_margin - pdf.get_x()
    return max(float(w), min_w)


def _truncate_url(url: str, max_len: int = MAX_URL_DISPLAY_LEN) -> str:
    """Truncate long URLs with ellipsis to avoid overflow; keeps one line readable."""
    if not url or len(url) <= max_len:
        return url or ""
    return url[: max_len - 3].rstrip("/") + "..."


def add_product_page(pdf: FPDF, product: Dict):
    """Add product details page. All body text uses content width (epw) and stays within margins."""
    pdf.add_page()
    pdf.set_x(pdf.l_margin)
    
    rank = product.get('rank', 0)
    cw = _content_width(pdf)
    
    # Product header
    pdf.set_font('Arial', 'B', FONT_SIZE_HEADING)
    pdf.cell(0, 10, f"Trending Product #{rank}", 0, 1, 'L')
    pdf.ln(5)
    
    # Brand name
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 8, _sanitize_pdf_text(f"Brand Name: {product.get('brand_name', 'Unknown')}"), 0, 1, 'L')
    
    # Product name (full width paragraph)
    pdf.set_x(pdf.l_margin)
    pdf.set_font('Arial', '', FONT_SIZE_SUBHEADING)
    pdf.multi_cell(cw, LINE_HEIGHT_TITLE, _sanitize_pdf_text(f"Product: {product.get('product_name', '') or '-'}"))
    pdf.set_x(pdf.l_margin)
    pdf.ln(2)
    
    # URL (wrapped or truncated to stay within margins)
    if product.get('brand_url'):
        pdf.set_font('Arial', 'U', FONT_SIZE_SMALL)
        pdf.set_text_color(0, 0, 255)
        url_display = _truncate_url(_sanitize_pdf_text(product.get('brand_url', '') or ""))
        pdf.multi_cell(cw, LINE_HEIGHT_BODY, f"URL: {url_display}")
        pdf.set_text_color(0, 0, 0)
        pdf.set_x(pdf.l_margin)
    pdf.ln(2)
    
    # Description (full width paragraph)
    pdf.set_x(pdf.l_margin)
    pdf.set_font('Arial', '', FONT_SIZE_BODY)
    desc = _sanitize_pdf_text((product.get('description') or '').strip() or "-")
    pdf.multi_cell(cw, LINE_HEIGHT_BODY, desc)
    pdf.set_x(pdf.l_margin)
    pdf.ln(5)
    
    # Revenue metrics (two-column: label 60pt, value uses rest of line)
    pdf.set_font('Arial', 'B', FONT_SIZE_SUBHEADING)
    pdf.cell(0, 8, 'Revenue Metrics', 0, 1, 'L')
    pdf.set_font('Arial', '', FONT_SIZE_BODY)
    metrics = [
        ('Revenue Trend:', product.get('revenue_trend', '')),
        ('Revenue Scale:', product.get('revenue_scale', '')),
        ('Product Rank in Category:', product.get('category_rank', ''))
    ]
    for label, value in metrics:
        pdf.set_x(pdf.l_margin)
        pdf.set_font('Arial', 'B', FONT_SIZE_BODY)
        pdf.cell(60, LINE_HEIGHT_BODY, label, 0, 0, 'L')
        pdf.set_font('Arial', '', FONT_SIZE_BODY)
        w_val = _safe_width(pdf)
        pdf.multi_cell(w_val, LINE_HEIGHT_BODY, _sanitize_pdf_text((str(value).strip() if value is not None else '') or '-'), 0, 'L')
        pdf.set_x(pdf.l_margin)
    
    pdf.ln(5)
    
    # Supporting trends heading
    pdf.set_font('Arial', 'B', FONT_SIZE_SUBHEADING)
    pdf.cell(0, 8, 'Supporting Trends:', 0, 1, 'L')
    pdf.ln(2)
    
    # Intro paragraph (full width)
    pdf.set_x(pdf.l_margin)
    pdf.set_font('Arial', '', FONT_SIZE_BODY)
    intro_text = _sanitize_pdf_text(
        f"Here are 5 macro trends that are driving the success of "
        f"{product.get('brand_name', '')} {product.get('product_name', '')}, "
        f"and which have helped make it one of the most dominant products in the market:"
    )
    pdf.multi_cell(cw, LINE_HEIGHT_BODY, intro_text)
    pdf.set_x(pdf.l_margin)
    pdf.ln(3)
    
    # List of trends (each title + explanation as full-width paragraphs)
    trends = product.get('supporting_trends', [])
    for i, trend in enumerate(trends, 1):
        pdf.set_x(pdf.l_margin)
        trend_parts = parse_trend_text(trend)
        title = _sanitize_pdf_text((trend_parts['title'] or '').strip() or "-")
        explanation = _sanitize_pdf_text((trend_parts['explanation'] or '').strip() or "-")
        pdf.set_font('Arial', 'B', FONT_SIZE_BODY)
        pdf.multi_cell(cw, LINE_HEIGHT_BODY, f"{i}. {title}")
        pdf.set_x(pdf.l_margin)
        pdf.set_font('Arial', '', FONT_SIZE_SMALL)
        pdf.multi_cell(cw, LINE_HEIGHT_BODY, explanation)
        pdf.set_x(pdf.l_margin)
        pdf.ln(2)


def parse_trend_text(trend: str) -> Dict:
    """
    Parse trend text into title and explanation
    
    Args:
        trend: Trend text (may include title on first line)
        
    Returns:
        Dict with 'title' and 'explanation'
    """
    if trend is None or not isinstance(trend, str):
        return {'title': '-', 'explanation': '-'}
    trend = trend.strip()
    if not trend:
        return {'title': '-', 'explanation': '-'}
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
