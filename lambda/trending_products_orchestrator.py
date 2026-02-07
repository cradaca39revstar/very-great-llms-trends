"""
LLM Product Innovation Engine - Lambda Orchestrator (V2).
Athena top 5 (market context) -> Brand proposal -> 5 product ideas -> Titan images -> PDF.
Target latency: 17-26s. All documentation and comments in English.
"""

import base64
import json
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from decimal import Decimal
from http import HTTPStatus
from typing import List, Dict, Any, Optional

import boto3
from botocore.exceptions import ClientError

from utils.athena_helper import query_athena_top_products
from utils.bedrock_helper import generate_brand_proposal, generate_product_ideas
from utils.image_generator import generate_brand_logo, generate_images_parallel
from utils.pdf_generator import generate_pdf_report, upload_pdf_to_s3

# Environment variables
ATHENA_WORKGROUP = os.environ.get("ATHENA_WORKGROUP")
ATHENA_DATABASE = os.environ.get("ATHENA_DATABASE")
BEDROCK_PRIMARY_MODEL = os.environ.get("BEDROCK_PRIMARY_MODEL")
BEDROCK_FALLBACK_MODEL = os.environ.get("BEDROCK_FALLBACK_MODEL")
DYNAMODB_LOGS_TABLE = os.environ.get("DYNAMODB_LOGS_TABLE")
PDF_BUCKET = os.environ.get("PDF_BUCKET")
ENVIRONMENT = os.environ.get("ENVIRONMENT", "poc")
AWS_REGION = os.environ.get("AWS_REGION_NAME", "us-east-1")

dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
cloudwatch = boto3.client("cloudwatch", region_name=AWS_REGION)
bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)

SUPPORTED_L2_CATEGORIES = [
    "Skincare",
    "Haircare & Styling",
    "Makeup",
    "Bath & Body Care",
    "Fragrance",
    "Tools & Accessories",
]

# Error codes per rulescore.mdc: [MODULE][NUMBER] (TRD = Trending)
TRD001 = "TRD001"  # Missing query
TRD002 = "TRD002"  # Category not found
TRD003 = "TRD003"  # No products in category
TRD004 = "TRD004"  # Athena query failed
TRD005 = "TRD005"  # Brand generation failed
TRD006 = "TRD006"  # Product ideas generation failed
TRD007 = "TRD007"  # Internal server error


def lambda_handler(event: Dict, context: Any) -> Dict:
    """
    V2 flow: Athena top 5 -> market context -> brand proposal -> product ideas -> Titan images -> report -> PDF.
    """
    start_time = time.time()
    request_id = str(uuid.uuid4())
    print(f"[{request_id}] Starting Product Innovation request (V2)")

    try:
        body = json.loads(event.get("body", "{}"))
        user_query = (body.get("query") or "").strip()
        if not user_query:
            return error_response(
                HTTPStatus.BAD_REQUEST,
                [{"code": TRD001, "description": "Missing required field: query"}],
                request_id,
            )

        user_id = extract_user_id(event)
        user_email = extract_user_email(event)
        print(f"[{request_id}] User: {user_email}, Query: {user_query}")

        try:
            l2_category = extract_l2_category(user_query)
            print(f"[{request_id}] Extracted L2 category: {l2_category}")
        except ValueError as e:
            return error_response(
                HTTPStatus.BAD_REQUEST,
                [{"code": TRD002, "description": str(e)}],
                request_id,
            )

        # Step 2: Athena top 5
        query_start = time.time()
        try:
            products = query_athena_top_products(
                l2_category=l2_category,
                workgroup=ATHENA_WORKGROUP,
                database=ATHENA_DATABASE,
            )
            athena_duration = (time.time() - query_start) * 1000
            print(f"[{request_id}] Athena: {len(products)} products, {athena_duration:.0f}ms")
            if not products:
                return error_response(
                    HTTPStatus.NOT_FOUND,
                    [{"code": TRD003, "description": f"No trending products found in category '{l2_category}' for the last 30 days"}],
                    request_id,
                )
        except Exception as e:
            print(f"[{request_id}] Athena failed: {e}")
            return error_response(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                [{"code": TRD004, "description": f"Athena query failed: {str(e)}"}],
                request_id,
            )

        # Step 3: Market context
        market_context = [
            {
                "product_name": p.get("product_name") or p.get("product_name_curated") or "",
                "shop_name": p.get("shop_name") or "",
                "revenue_usd": float(p.get("revenue_usd") or 0),
                "mom_growth_pct": float(p.get("mom_growth_pct") or 0),
                "item_sold": int(p.get("item_sold") or 0),
                "revenue_rank": int(p.get("revenue_rank") or i + 1),
            }
            for i, p in enumerate(products)
        ]

        # Step 4: Brand proposal
        try:
            brand_proposal = generate_brand_proposal(
                market_context=market_context,
                l2_category=l2_category,
                bedrock_client=bedrock,
                model_id=BEDROCK_PRIMARY_MODEL,
            )
            print(f"[{request_id}] Brand proposal: {brand_proposal.get('brand_name', '')}")
        except Exception as e:
            print(f"[{request_id}] Brand generation failed: {e}")
            return error_response(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                [{"code": TRD005, "description": f"Brand generation failed: {str(e)}"}],
                request_id,
            )

        brand_name = brand_proposal.get("brand_name") or ""
        brand_tagline = brand_proposal.get("brand_tagline") or ""

        # Step 5: Product ideas (needed before we can generate product images)
        try:
            product_ideas_raw = generate_product_ideas(
                market_context=market_context,
                brand_proposal=brand_proposal,
                l2_category=l2_category,
                bedrock_client=bedrock,
                model_id=BEDROCK_PRIMARY_MODEL,
            )
            print(f"[{request_id}] Product ideas: {len(product_ideas_raw)}")
        except Exception as e:
            print(f"[{request_id}] Product ideas failed: {e}")
            return error_response(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                [{"code": TRD006, "description": f"Product ideas generation failed: {str(e)}"}],
                request_id,
            )

        # Step 6: Brand logo + product images in parallel (saves ~5–15s vs sequential; keeps under API Gateway 29s limit)
        brand_logo_bytes = None
        image_bytes_list: List[Optional[bytes]] = []
        try:
            with ThreadPoolExecutor(max_workers=2) as executor:
                future_logo = executor.submit(generate_brand_logo, brand_name, brand_tagline, bedrock)
                future_images = executor.submit(
                    generate_images_parallel,
                    product_ideas_raw,
                    brand_name,
                    bedrock,
                    5,
                )
                for future in as_completed([future_logo, future_images]):
                    if future == future_logo:
                        try:
                            brand_logo_bytes = future.result()
                            print(f"[{request_id}] Brand logo: ok={brand_logo_bytes is not None}")
                        except Exception as e:
                            print(f"[{request_id}] Brand logo failed: {e}")
                    else:
                        try:
                            image_bytes_list = future.result()
                        except Exception as e:
                            print(f"[{request_id}] Product images failed: {e}")
                            return error_response(
                                HTTPStatus.INTERNAL_SERVER_ERROR,
                                [{"code": TRD007, "description": f"Image generation failed: {str(e)}"}],
                                request_id,
                            )
        except Exception as e:
            print(f"[{request_id}] Image step failed: {e}")
            return error_response(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                [{"code": TRD007, "description": f"Image generation failed: {str(e)}"}],
                request_id,
            )

        # Attach image bytes and build product_ideas for report
        product_ideas = []
        for i, idea in enumerate(product_ideas_raw):
            img_bytes = image_bytes_list[i] if i < len(image_bytes_list) else None
            st = idea.get("supporting_trends")
            if not isinstance(st, list):
                st = []
            product_ideas.append({
                "rank": i + 1,
                "product_name": idea.get("product_name") or "",
                "description": idea.get("description") or "",
                "estimated_price_usd": float(idea.get("estimated_price_usd") or 0),
                "why_it_would_sell": idea.get("why_it_would_sell") or "",
                "key_ingredients": idea.get("key_ingredients") if isinstance(idea.get("key_ingredients"), list) else [],
                "supporting_trends_intro": idea.get("supporting_trends_intro") or "",
                "supporting_trends": st,
                "competitive_advantage": idea.get("competitive_advantage") or "",
                "has_image": img_bytes is not None,
                "_image_bytes": img_bytes,
            })

        # Step 7: Format report (V2 structure; include image_base64 for frontend, logo for brand)
        report = format_report_v2(
            user_query=user_query,
            l2_category=l2_category,
            market_context=market_context,
            brand_proposal=brand_proposal,
            product_ideas=product_ideas,
            brand_logo_bytes=brand_logo_bytes,
        )

        # Step 8: PDF and upload (pass product_ideas with _image_bytes and brand logo for embedding)
        pdf_start = time.time()
        try:
            pdf_url = generate_and_upload_pdf(
                report, request_id, l2_category,
                product_ideas_with_images=product_ideas,
                brand_logo_bytes=brand_logo_bytes,
            )
            pdf_duration = (time.time() - pdf_start) * 1000
            print(f"[{request_id}] PDF: {pdf_duration:.0f}ms, URL: {pdf_url}")
        except Exception as e:
            print(f"[{request_id}] PDF failed: {e}")
            pdf_url = None
            pdf_duration = 0

        total_duration = (time.time() - start_time) * 1000
        bedrock_duration = total_duration - athena_duration - pdf_duration
        if bedrock_duration < 0:
            bedrock_duration = 0

        # Step 9: DynamoDB log (strip image_base64 / logo_image_base64 to stay under 400KB item limit)
        try:
            report_for_log = _report_for_dynamodb(report)
            log_to_dynamodb({
                "request_id": request_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "user_id": user_id,
                "user_email": user_email,
                "user_query": user_query,
                "l2_category": l2_category,
                "market_context_products": [p.get("product_id") for p in products],
                "brand_proposal_name": brand_proposal.get("brand_name", ""),
                "final_report": report_for_log,
                "pdf_url": pdf_url,
                "execution_time_ms": int(total_duration),
                "athena_duration_ms": int(athena_duration),
                "bedrock_duration_ms": int(bedrock_duration),
                "pdf_duration_ms": int(pdf_duration),
                "status": "success",
            })
        except Exception as e:
            print(f"[{request_id}] DynamoDB log warning: {e}")

        publish_metrics({
            "TrendingReportRequests": 1,
            "TotalReportDuration": total_duration,
            "AthenaQueryDuration": athena_duration,
            "BedrockCallDuration": bedrock_duration,
            "PDFGenerationDuration": pdf_duration,
        })

        print(f"[{request_id}] Completed in {total_duration:.0f}ms")

        # Return report without image_base64/logo_image_base64 so response fits under API Gateway 29s limit
        response_report = _report_for_dynamodb(report)
        return {
            "statusCode": HTTPStatus.OK.value,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key",
                "Access-Control-Allow-Methods": "POST,OPTIONS",
            },
            "body": json.dumps({
                "status": "success",
                "request_id": request_id,
                "query": user_query,
                "category": l2_category,
                "brand_name": brand_proposal.get("brand_name", ""),
                "report": response_report,
                "pdf_url": pdf_url,
                "execution_time_ms": int(total_duration),
                "product_count": len(product_ideas),
            }),
        }

    except Exception as e:
        print(f"[{request_id}] Unexpected error: {e}")
        return error_response(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            [{"code": TRD007, "description": f"Internal server error: {str(e)}"}],
            request_id,
        )


def format_report_v2(
    user_query: str,
    l2_category: str,
    market_context: List[Dict],
    brand_proposal: Dict,
    product_ideas: List[Dict],
    brand_logo_bytes: Optional[bytes] = None,
) -> Dict:
    """Build report dict for V2. Adds image_base64 for frontend/PDF; brand_proposal gets logo_image_base64."""
    ideas_out = []
    for p in product_ideas:
        img_b64 = None
        raw = p.get("_image_bytes")
        if raw:
            try:
                img_b64 = base64.b64encode(raw).decode("ascii")
            except Exception:
                pass
        ideas_out.append({
            "rank": p.get("rank", 0),
            "product_name": p.get("product_name", ""),
            "description": p.get("description", ""),
            "estimated_price_usd": p.get("estimated_price_usd", 0),
            "why_it_would_sell": p.get("why_it_would_sell", ""),
            "key_ingredients": p.get("key_ingredients", []),
            "supporting_trends_intro": p.get("supporting_trends_intro") or "",
            "supporting_trends": p.get("supporting_trends", []),
            "competitive_advantage": p.get("competitive_advantage", ""),
            "has_image": p.get("has_image", False),
            "image_base64": img_b64,
        })
    brand_out = dict(brand_proposal)
    if brand_logo_bytes:
        try:
            brand_out["logo_image_base64"] = base64.b64encode(brand_logo_bytes).decode("ascii")
        except Exception:
            pass
    return {
        "query": user_query,
        "category": l2_category,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_period": "Last 30 Days",
        "market_context": market_context,
        "brand_proposal": brand_out,
        "product_ideas": ideas_out,
    }


def generate_and_upload_pdf(
    report: Dict,
    request_id: str,
    category: str,
    product_ideas_with_images: List[Dict] | None = None,
    brand_logo_bytes: Optional[bytes] = None,
) -> str:
    """Generate PDF from report; product_ideas_with_images may contain _image_bytes; brand_logo_bytes for brand page."""
    pdf_bytes = generate_pdf_report(
        report,
        product_ideas_with_images=product_ideas_with_images or [],
        brand_logo_bytes=brand_logo_bytes,
    )
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    category_slug = category.lower().replace(" & ", "-").replace(" ", "-")
    filename = f"trending-products-{category_slug}-{timestamp}.pdf"
    date_path = datetime.now(timezone.utc).strftime("%Y/%m/%d")
    s3_key = f"reports/{date_path}/{filename}"
    pdf_url = upload_pdf_to_s3(pdf_bytes=pdf_bytes, bucket=PDF_BUCKET, key=s3_key, expiration=3600)
    return pdf_url


def extract_l2_category(user_query: str) -> str:
    """Extract L2 category from natural language query. Raises ValueError if not found."""
    query_lower = user_query.lower()
    for category in SUPPORTED_L2_CATEGORIES:
        if category.lower() in query_lower:
            return category
        if category == "Haircare & Styling" and ("haircare" in query_lower or "hair care" in query_lower):
            return category
        if category == "Bath & Body Care" and ("bath" in query_lower or "body care" in query_lower):
            return category
        if category == "Tools & Accessories" and ("tools" in query_lower or "accessories" in query_lower):
            return category
    raise ValueError(
        f"Category not found in query: '{user_query}'. Supported categories: {', '.join(SUPPORTED_L2_CATEGORIES)}"
    )


def extract_user_id(event: Dict) -> str:
    try:
        return event.get("requestContext", {}).get("authorizer", {}).get("claims", {}).get("sub", "unknown")
    except Exception:
        return "unknown"


def extract_user_email(event: Dict) -> str:
    try:
        return event.get("requestContext", {}).get("authorizer", {}).get("claims", {}).get("email", "unknown")
    except Exception:
        return "unknown"


def _report_for_dynamodb(report: Dict) -> Dict:
    """Return a copy of the report without image_base64/logo_image_base64 to stay under DynamoDB 400KB item limit."""
    out = dict(report)
    bp = out.get("brand_proposal") or {}
    out["brand_proposal"] = {k: v for k, v in bp.items() if k != "logo_image_base64"}
    ideas = []
    for p in out.get("product_ideas") or []:
        ideas.append({k: v for k, v in (p if isinstance(p, dict) else {}).items() if k != "image_base64"})
    out["product_ideas"] = ideas
    return out


def _float_to_decimal(obj: Any) -> Any:
    """Recursively convert floats to Decimal for DynamoDB (does not support float)."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: _float_to_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_float_to_decimal(v) for v in obj]
    return obj


def log_to_dynamodb(log_data: Dict) -> None:
    try:
        table = dynamodb.Table(DYNAMODB_LOGS_TABLE)
        log_data["ttl_expiry"] = int(time.time()) + (90 * 24 * 60 * 60)
        item = _float_to_decimal(log_data)
        table.put_item(Item=item)
        print(f"[{log_data['request_id']}] Logged to DynamoDB")
    except Exception as e:
        print(f"Warning: DynamoDB logging failed: {e}")


def publish_metrics(metrics: Dict) -> None:
    try:
        metric_data = [
            {
                "MetricName": name,
                "Value": value,
                "Unit": "Milliseconds" if "Duration" in name else "Count",
                "Timestamp": datetime.now(timezone.utc),
            }
            for name, value in metrics.items()
        ]
        cloudwatch.put_metric_data(Namespace="BeautyProducts/LLM", MetricData=metric_data)
    except Exception as e:
        print(f"Warning: CloudWatch metrics failed: {e}")


def error_response(
    status: HTTPStatus,
    msg_code: List[Dict[str, str]],
    request_id: str,
) -> Dict:
    """Standardized error response. status_code from HTTPStatus; msg_code list with code and description."""
    try:
        cloudwatch.put_metric_data(
            Namespace="BeautyProducts/LLM",
            MetricData=[{"MetricName": "ErrorCount", "Value": 1, "Unit": "Count", "Timestamp": datetime.now(timezone.utc)}],
        )
    except Exception:
        pass
    return {
        "statusCode": status.value,
        "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
        "body": json.dumps({
            "error": True,
            "status_code": status.value,
            "msg_code": msg_code,
            "request_id": request_id,
            "message": msg_code[0].get("description", "") if msg_code else "",
            "supported_categories": SUPPORTED_L2_CATEGORIES if status == HTTPStatus.BAD_REQUEST else None,
        }),
    }
