"""
PDF Report Generator Module (V2).
Creates Product Innovation Report PDF: market context, brand proposal, product ideas with AI images.
"""

import os
from datetime import datetime, timezone
from io import BytesIO
from typing import Dict, List, Optional
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
# Market Intelligence: compact section (max 1 page)
MI_SNIPPET_MAX_CHARS = 90
MI_ITEMS_PER_SECTION = 3
MI_LINE_HEIGHT = 4
MI_SECTION_FILL_RGB = (240, 240, 240)

# AWS S3 client
s3_client = boto3.client('s3', region_name=os.environ.get('AWS_REGION_NAME', 'us-east-1'))


class TrendingProductsPDF(FPDF):
    """Custom PDF class for trending products reports"""
    
    def __init__(self, report_data: Dict):
        super().__init__()
        self.report_data = report_data
        
    def header(self):
        """Page header – left empty so title appears only once on the title page."""
        pass
    
    def footer(self):
        """Page footer"""
        self.set_y(-15)
        self.set_x(self.l_margin)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f"Page {self.page_no()}", 0, 0, 'C')


def generate_pdf_report(
    report: Dict,
    product_ideas_with_images: Optional[List[Dict]] = None,
    brand_logo_bytes: Optional[bytes] = None,
) -> bytes:
    """
    Generate Product Innovation Report PDF (V2): title, market context, brand proposal, 5 product idea pages.
    product_ideas_with_images: list of product dicts that may contain _image_bytes for embedding.
    brand_logo_bytes: optional AI-generated brand logo image (PNG) for brand proposal page.
    """
    pdf = TrendingProductsPDF(report)
    pdf.set_margins(PAGE_MARGIN_MM, PAGE_MARGIN_MM, PAGE_MARGIN_MM)
    pdf.set_auto_page_break(auto=True, margin=PAGE_BOTTOM_MARGIN_MM)
    pdf.set_x(pdf.l_margin)
    pdf.set_y(pdf.t_margin)

    add_title_page(pdf, report)
    add_market_research_page(pdf, report)
    add_brand_proposal_page(pdf, report.get("brand_proposal", {}), logo_bytes=brand_logo_bytes)
    product_ideas = report.get("product_ideas", [])
    ideas_with_images = product_ideas_with_images or []
    for i, product in enumerate(product_ideas):
        img_bytes = None
        if i < len(ideas_with_images) and isinstance(ideas_with_images[i], dict):
            img_bytes = ideas_with_images[i].get("_image_bytes")
        add_product_idea_page(pdf, product, img_bytes)

    return bytes(pdf.output())


def add_title_page(pdf: FPDF, report: Dict):
    """V2: Product Innovation Report title page – title and category once; Proposed Brand (name + tagline); Generated; Data Period."""
    pdf.add_page()
    pdf.set_x(pdf.l_margin)
    category = report.get("category", "")
    brand_proposal = report.get("brand_proposal", {})
    brand_name = brand_proposal.get("brand_name", "")
    brand_tagline = brand_proposal.get("brand_tagline", "")

    # Title and category (only once)
    pdf.set_font("Arial", "B", FONT_SIZE_TITLE)
    pdf.ln(20)
    pdf.cell(0, 10, "Product Innovation Report", 0, 1, "C")
    pdf.set_font("Arial", "", 18)
    w_label = pdf.get_string_width("Category: ")
    pdf.set_font("Arial", "B", 18)
    w_cat = pdf.get_string_width(_sanitize_pdf_text(category))
    pdf.set_x((pdf.w - w_label - w_cat) / 2)
    pdf.set_font("Arial", "", 18)
    pdf.cell(w_label, 10, "Category: ", 0, 0, "L")
    pdf.set_font("Arial", "B", 18)
    pdf.cell(w_cat, 10, _sanitize_pdf_text(category), 0, 1, "L")

    # Proposed Brand: Name (bold+italic) and Tagline (italic)
    pdf.set_font("Arial", "B", FONT_SIZE_SUBHEADING)
    pdf.ln(10)
    pdf.cell(0, 8, "Proposed Brand:", 0, 1, "C")
    if brand_name:
        pdf.set_font("Arial", "BI", FONT_SIZE_HEADING)
        pdf.ln(4)
        pdf.cell(0, 8, _sanitize_pdf_text(f"Brand: {brand_name}"), 0, 1, "C")
        if brand_tagline:
            pdf.set_font("Arial", "I", FONT_SIZE_HEADING)
            pdf.cell(0, 8, _sanitize_pdf_text(brand_tagline), 0, 1, "C")

    # Generated and Data Period
    pdf.set_font("Arial", "", FONT_SIZE_SUBHEADING)
    pdf.ln(12)
    pdf.cell(0, 8, f"Generated: {format_timestamp(report.get('generated_at', ''))}", 0, 1, "C")
    pdf.cell(0, 8, f"Data Period: {report.get('data_period', 'Last 30 Days')}", 0, 1, "C")

    # Intro paragraph
    pdf.ln(15)
    pdf.set_font("Arial", "", FONT_SIZE_BODY)
    pdf.set_x(pdf.l_margin)
    summary = _sanitize_pdf_text(
        f"Based on market analysis of top-performing products in {category}, this report "
        f"presents an AI-generated brand concept and 5 product ideas (4 based on top performers, 1 brand new) with supporting trends."
    )
    pdf.multi_cell(_content_width(pdf), LINE_HEIGHT_TITLE, summary)


def add_market_research_page(pdf: FPDF, report: Dict):
    """Page 2: Market Research – title, intro sentence, Top 5 Products list with short descriptions."""
    pdf.add_page()
    pdf.set_x(pdf.l_margin)
    cw = _content_width(pdf)
    market_context = report.get("market_context") or []

    # Main title: Market Research
    pdf.set_font("Arial", "B", FONT_SIZE_TITLE)
    pdf.ln(10)
    pdf.cell(0, 10, "Market Research", 0, 1, "L")

    # Introductory sentence
    pdf.set_font("Arial", "", FONT_SIZE_BODY)
    pdf.ln(6)
    intro = _sanitize_pdf_text("Here are your top 5 products recommended based on your prompt.")
    pdf.multi_cell(cw, LINE_HEIGHT_BODY, intro)

    # Subtitle: Top 5 Products
    pdf.set_font("Arial", "B", FONT_SIZE_HEADING)
    pdf.ln(12)
    pdf.cell(0, 10, "Top 5 Products", 0, 1, "L")

    # Numbered list with product name and short description
    pdf.set_font("Arial", "", FONT_SIZE_BODY)
    pdf.ln(4)
    for i, p in enumerate(market_context[:5], 1):
        name = _sanitize_pdf_text(p.get("product_name") or "—")
        desc = _sanitize_pdf_text(p.get("short_description") or "")
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Arial", "B", FONT_SIZE_BODY)
        pdf.cell(8, LINE_HEIGHT_BODY, f"{i}.", 0, 0, "L")
        pdf.multi_cell(cw - 8, LINE_HEIGHT_BODY, name, 0, "L")
        if desc:
            pdf.set_x(pdf.l_margin + 10)
            pdf.set_font("Arial", "", FONT_SIZE_SMALL)
            pdf.multi_cell(cw - 10, LINE_HEIGHT_BODY - 1, desc)
        pdf.ln(4)


def add_market_context_page(pdf: FPDF, market_context: List[Dict]):
    """V2: Market Analysis - top 5 real products."""
    pdf.add_page()
    pdf.set_x(pdf.l_margin)
    cw = _content_width(pdf)
    pdf.set_font("Arial", "B", FONT_SIZE_HEADING)
    pdf.cell(0, 10, "Market Analysis - Current Top Performers", 0, 1, "L")
    pdf.ln(3)
    pdf.set_font("Arial", "", FONT_SIZE_BODY)
    pdf.multi_cell(cw, LINE_HEIGHT_BODY, _sanitize_pdf_text(
        "The following market data was analyzed to identify opportunities for the brand concept."
    ))
    pdf.set_x(pdf.l_margin)
    pdf.ln(5)
    pdf.set_font("Arial", "B", FONT_SIZE_SMALL)
    pdf.cell(12, LINE_HEIGHT_BODY, "Rank", 1, 0, "L")
    pdf.cell(50, LINE_HEIGHT_BODY, "Product", 1, 0, "L")
    pdf.cell(35, LINE_HEIGHT_BODY, "Shop", 1, 0, "L")
    pdf.cell(25, LINE_HEIGHT_BODY, "Revenue", 1, 0, "R")
    pdf.cell(20, LINE_HEIGHT_BODY, "Growth%", 1, 0, "R")
    pdf.cell(20, LINE_HEIGHT_BODY, "Sold", 1, 1, "R")
    pdf.set_font("Arial", "", FONT_SIZE_SMALL)
    for p in market_context[:5]:
        pdf.set_x(pdf.l_margin)
        pdf.cell(12, LINE_HEIGHT_BODY, str(p.get("revenue_rank", "")), 1, 0, "L")
        pdf.cell(50, LINE_HEIGHT_BODY, _sanitize_pdf_text((p.get("product_name") or "")[:28]), 1, 0, "L")
        pdf.cell(35, LINE_HEIGHT_BODY, _sanitize_pdf_text((p.get("shop_name") or "")[:18]), 1, 0, "L")
        pdf.cell(25, LINE_HEIGHT_BODY, f"${float(p.get('revenue_usd') or 0):,.0f}", 1, 0, "R")
        pdf.cell(20, LINE_HEIGHT_BODY, f"{float(p.get('mom_growth_pct') or 0):.1f}%", 1, 0, "R")
        pdf.cell(20, LINE_HEIGHT_BODY, str(int(p.get("item_sold") or 0)), 1, 1, "R")


def add_brand_proposal_page(pdf: FPDF, brand_proposal: Dict, logo_bytes: Optional[bytes] = None):
    """V2: Proposed Brand section with optional AI-generated logo (PNG, no background box)."""
    pdf.add_page()
    pdf.set_x(pdf.l_margin)
    cw = _content_width(pdf)
    name = brand_proposal.get("brand_name", "")
    pdf.set_font("Arial", "B", FONT_SIZE_HEADING)
    pdf.cell(0, 10, f"Proposed Brand: {_sanitize_pdf_text(name)}", 0, 1, "L")
    pdf.ln(3)
    if logo_bytes:
        try:
            img_io = BytesIO(logo_bytes)
            pdf.image(img_io, x=pdf.l_margin, y=pdf.get_y(), w=50, type="PNG")
            pdf.set_y(pdf.get_y() + 50)
            pdf.ln(5)
        except Exception as e:
            print(f"PDF: failed to embed brand logo: {e}")
    pdf.set_x(pdf.l_margin)
    pdf.ln(3)
    for label, key in [
        ("Tagline", "brand_tagline"),
        ("Brand Story", "brand_story"),
        ("Target Demographic", "target_demographic"),
        ("Price Positioning", "price_positioning"),
        ("Distribution Strategy", "distribution_strategy"),
        ("Brand Personality", "brand_personality"),
    ]:
        val = brand_proposal.get(key) or ""
        if isinstance(val, list):
            val = ", ".join(str(x) for x in val)
        val_str = str(val)
        if key == "brand_personality":
            val_str = _title_case_comma_list(val_str)
        pdf.set_font("Arial", "B", FONT_SIZE_SUBHEADING)
        pdf.cell(0, 8, label, 0, 1, "L")
        pdf.set_font("Arial", "", FONT_SIZE_BODY)
        pdf.multi_cell(cw, LINE_HEIGHT_BODY, _sanitize_pdf_text(val_str) or "-")
        pdf.set_x(pdf.l_margin)
        pdf.ln(3)
    values = brand_proposal.get("brand_values") or []
    if values:
        values_str = _title_case_comma_list(", ".join(str(v) for v in values))
        pdf.set_font("Arial", "B", FONT_SIZE_SUBHEADING)
        pdf.cell(0, 8, "Core Values", 0, 1, "L")
        pdf.set_font("Arial", "", FONT_SIZE_BODY)
        pdf.multi_cell(cw, LINE_HEIGHT_BODY, _sanitize_pdf_text(values_str))
        pdf.ln(3)


def add_market_intelligence_page(pdf: FPDF, web_insights: Dict, show_disclaimer: bool = False) -> None:
    """Market Intelligence: compact 1-page section with clear hierarchy, domain-only URLs, short snippets.
    Uses gray section bars, bullets, and max MI_ITEMS_PER_SECTION items per block to fit in ~1 page."""
    pdf.add_page()
    pdf.set_x(pdf.l_margin)
    cw = _content_width(pdf)
    title_w = cw - 35
    domain_w = 32
    trends = web_insights.get("trends") or []
    pain_points = web_insights.get("pain_points") or []
    competitors = web_insights.get("competitors") or []
    has_any = bool(trends or pain_points or competitors)
    if show_disclaimer and not has_any:
        pdf.set_font("Arial", "B", FONT_SIZE_SUBHEADING)
        pdf.cell(0, 8, "Market Intelligence", 0, 1, "L")
        pdf.ln(2)
        pdf.set_font("Arial", "", FONT_SIZE_SMALL)
        pdf.multi_cell(
            cw, MI_LINE_HEIGHT,
            _sanitize_pdf_text(
                "Web search insights could not be loaded for this report. "
                "The following analysis is based on internal market data only."
            )
        )
        return
    if not has_any:
        pdf.set_font("Arial", "B", FONT_SIZE_SUBHEADING)
        pdf.cell(0, 8, "Market Intelligence", 0, 1, "L")
        pdf.ln(2)
        pdf.set_font("Arial", "", FONT_SIZE_SMALL)
        pdf.multi_cell(cw, MI_LINE_HEIGHT, _sanitize_pdf_text("No web search data available for this category."))
        return
    pdf.set_font("Arial", "B", FONT_SIZE_SUBHEADING)
    pdf.cell(0, 7, "Market Intelligence", 0, 1, "L")
    pdf.ln(2)
    sections = [
        (">> Trends", trends),
        (">> Pain points", pain_points),
        (">> Competitors", competitors),
    ]
    for label, items in sections:
        if not items:
            continue
        pdf.set_fill_color(*MI_SECTION_FILL_RGB)
        pdf.set_font("Arial", "B", FONT_SIZE_SMALL)
        pdf.cell(0, 7, f"  {label}", 0, 1, "L", fill=1)
        pdf.set_font("Arial", "", FONT_SIZE_SMALL)
        pdf.ln(1)
        for entry in items[:MI_ITEMS_PER_SECTION]:
            if not isinstance(entry, dict):
                continue
            title = _sanitize_pdf_text((entry.get("title") or "").strip())
            if len(title) > 52:
                title = title[:49] + "..."
            url = (entry.get("url") or "").strip()
            domain = _url_to_domain(url)
            snippet_raw = (entry.get("snippet") or "").strip()
            snippet = _sanitize_pdf_text(snippet_raw[:MI_SNIPPET_MAX_CHARS] + ("..." if len(snippet_raw) > MI_SNIPPET_MAX_CHARS else ""))
            y0 = pdf.get_y()
            pdf.set_font("Arial", "", FONT_SIZE_SMALL)
            pdf.multi_cell(title_w, MI_LINE_HEIGHT, "  - " + (title or "-"), 0, "L")
            y1 = pdf.get_y()
            if domain:
                pdf.set_font("Arial", "I", 8)
                pdf.set_xy(pdf.l_margin + title_w, y0)
                pdf.cell(domain_w, MI_LINE_HEIGHT, domain[:28], 0, 0, "R")
                pdf.set_font("Arial", "", FONT_SIZE_SMALL)
            pdf.set_xy(pdf.l_margin, y1)
            if snippet:
                pdf.set_x(pdf.l_margin)
                pdf.set_font("Arial", "", 8)
                pdf.multi_cell(cw, MI_LINE_HEIGHT - 0.5, "     " + snippet, 0, "L")
                pdf.set_font("Arial", "", FONT_SIZE_SMALL)
            pdf.ln(2)
        pdf.ln(2)


def add_product_idea_page(pdf: FPDF, product: Dict, image_bytes: Optional[bytes] = None):
    """V2: One page per product idea with optional AI-generated image."""
    pdf.add_page()
    pdf.set_x(pdf.l_margin)
    cw = _content_width(pdf)
    rank = product.get("rank", 0)
    pdf.set_font("Arial", "B", FONT_SIZE_HEADING)
    pdf.cell(0, 10, f"Product Concept #{rank}", 0, 1, "L")
    pdf.ln(3)
    if image_bytes:
        try:
            img_io = BytesIO(image_bytes)
            pdf.image(img_io, x=pdf.l_margin, y=pdf.get_y(), w=60, type="PNG")
            pdf.set_y(pdf.get_y() + 60)
            pdf.ln(5)
        except Exception as e:
            print(f"PDF: failed to embed product image: {e}")
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Arial", "B", FONT_SIZE_SUBHEADING)
    pdf.cell(0, 8, _sanitize_pdf_text(product.get("product_name", "") or "-"), 0, 1, "L")
    pdf.set_font("Arial", "", FONT_SIZE_BODY)
    pdf.multi_cell(cw, LINE_HEIGHT_BODY, _sanitize_pdf_text(product.get("description", "") or "-"))
    pdf.set_x(pdf.l_margin)
    pdf.ln(3)
    pdf.set_font("Arial", "B", FONT_SIZE_BODY)
    pdf.cell(0, 8, f"Estimated Price: ${float(product.get('estimated_price_usd') or 0):.2f}", 0, 1, "L")
    ingredients = product.get("key_ingredients") or []
    if ingredients:
        pdf.set_font("Arial", "B", FONT_SIZE_SMALL)
        pdf.cell(0, 8, "Key Ingredients:", 0, 1, "L")
        pdf.set_font("Arial", "", FONT_SIZE_SMALL)
        pdf.multi_cell(cw, LINE_HEIGHT_BODY, _sanitize_pdf_text(", ".join(str(x) for x in ingredients)))
        pdf.set_x(pdf.l_margin)
        pdf.ln(2)
    pdf.set_font("Arial", "B", FONT_SIZE_SMALL)
    pdf.cell(0, 8, "Why It Would Sell:", 0, 1, "L")
    pdf.set_font("Arial", "", FONT_SIZE_SMALL)
    pdf.multi_cell(cw, LINE_HEIGHT_BODY, _sanitize_pdf_text(product.get("why_it_would_sell", "") or "-"))
    pdf.set_x(pdf.l_margin)
    pdf.ln(2)
    pdf.set_font("Arial", "B", FONT_SIZE_SMALL)
    pdf.cell(0, 8, "Competitive Advantage:", 0, 1, "L")
    pdf.set_font("Arial", "", FONT_SIZE_SMALL)
    pdf.multi_cell(cw, LINE_HEIGHT_BODY, _sanitize_pdf_text(product.get("competitive_advantage", "") or "-"))
    pdf.set_x(pdf.l_margin)
    pdf.ln(5)
    pdf.set_font("Arial", "B", FONT_SIZE_SMALL)
    pdf.cell(0, 8, "Supporting Trends:", 0, 1, "L")
    pdf.set_font("Arial", "", FONT_SIZE_SMALL)
    intro = product.get("supporting_trends_intro") or ""
    if intro:
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(cw, LINE_HEIGHT_BODY, _sanitize_pdf_text(intro))
        pdf.set_x(pdf.l_margin)
        pdf.ln(3)
    trends = product.get("supporting_trends") or []
    for i, trend in enumerate(trends, 1):
        pdf.set_x(pdf.l_margin)
        if isinstance(trend, dict):
            title = _sanitize_pdf_text((trend.get("title") or "").strip())
            desc = _sanitize_pdf_text((trend.get("description") or "").strip())
            if title:
                pdf.set_font("Arial", "B", FONT_SIZE_SMALL)
                pdf.multi_cell(cw, LINE_HEIGHT_BODY, f"{i}. {title}")
                pdf.set_x(pdf.l_margin)
            if desc:
                pdf.set_font("Arial", "", FONT_SIZE_SMALL)
                pdf.multi_cell(cw, LINE_HEIGHT_BODY, desc)
            pdf.set_x(pdf.l_margin)
            pdf.ln(2)
        else:
            pdf.multi_cell(cw, LINE_HEIGHT_BODY, _sanitize_pdf_text(f"{i}. {trend}"))
        pdf.set_x(pdf.l_margin)
    pdf.ln(5)
    pdf.set_font("Arial", "I", FONT_SIZE_SMALL)
    pdf.cell(0, 8, "AI-Generated Product Concept", 0, 1, "L")


def _title_case_comma_list(s: str) -> str:
    """Make capital letters consistent: title-case each comma-separated item (e.g. Brand Personality, Core Values)."""
    if not s or not isinstance(s, str):
        return s
    parts = [p.strip().title() for p in s.split(",") if p.strip()]
    return ", ".join(parts)


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


def _url_to_domain(url: str) -> str:
    """Extract display domain from URL (e.g. https://www.reddit.com/r/... -> reddit.com)."""
    if not url or not isinstance(url, str):
        return ""
    s = url.strip()
    for prefix in ("https://", "http://"):
        if s.lower().startswith(prefix):
            s = s[len(prefix) :].lstrip("/")
            break
    if s.lower().startswith("www."):
        s = s[4:]
    # Take first path segment (domain only)
    domain = s.split("/")[0].split("?")[0]
    return domain if domain else ""


def _truncate_url(url: str, max_len: int = MAX_URL_DISPLAY_LEN) -> str:
    """Truncate long URLs with ellipsis to avoid overflow; keeps one line readable."""
    if not url or len(url) <= max_len:
        return url or ""
    return url[: max_len - 3].rstrip("/") + "..."


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
