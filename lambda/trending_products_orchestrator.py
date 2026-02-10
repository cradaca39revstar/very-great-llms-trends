"""
LLM Product Innovation Engine - Lambda Orchestrator (V2).
Async flow: POST returns 202 and invokes self; GET /report/{request_id} polls status.
Worker: Athena top 5 -> Brand proposal -> 5 product ideas -> Titan images -> PDF -> write to report_status.
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
from utils.market_research_agent import search_all as market_research_search_all
from utils.image_utils import image_bytes_to_thumbnail_base64, logo_remove_background, logo_to_thumbnail_base64
from utils.pdf_generator import generate_pdf_report, upload_pdf_to_s3

# Environment variables
ATHENA_WORKGROUP = os.environ.get("ATHENA_WORKGROUP")
ATHENA_DATABASE = os.environ.get("ATHENA_DATABASE")
BEDROCK_PRIMARY_MODEL = os.environ.get("BEDROCK_PRIMARY_MODEL")
BEDROCK_FALLBACK_MODEL = os.environ.get("BEDROCK_FALLBACK_MODEL")
DYNAMODB_LOGS_TABLE = os.environ.get("DYNAMODB_LOGS_TABLE")
REPORT_STATUS_TABLE = os.environ.get("REPORT_STATUS_TABLE")
WEB_INSIGHTS_CACHE_TABLE = os.environ.get("WEB_INSIGHTS_CACHE_TABLE")  # optional; 6h TTL
PDF_BUCKET = os.environ.get("PDF_BUCKET")
ENVIRONMENT = os.environ.get("ENVIRONMENT", "poc")
AWS_REGION = os.environ.get("AWS_REGION_NAME", "us-east-1")

dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
cloudwatch = boto3.client("cloudwatch", region_name=AWS_REGION)
bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)
lambda_client = boto3.client("lambda", region_name=AWS_REGION)

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

# CORS headers for all Lambda responses
CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
}


def lambda_handler(event: Dict, context: Any) -> Dict:
    """
    Router: GET /report/{request_id} -> status; async_report -> worker; else POST -> 202 + async invoke.
    """
    # GET /report/{request_id} (from API Gateway)
    if event.get("httpMethod") == "GET" and event.get("pathParameters", {}).get("request_id"):
        return handle_get_report_status(event)

    # Background worker invocation (async self-invoke)
    if event.get("async_report") is True:
        run_report_worker(event)
        return {"statusCode": HTTPStatus.OK.value, "headers": CORS_HEADERS, "body": "{}"}

    # POST /trending-products/query from API Gateway -> return 202 and invoke self async
    return handle_post_query_async(event, context)


def handle_get_report_status(event: Dict) -> Dict:
    """Return 200 with status (processing|completed|failed) and payload, or 404."""
    request_id = (event.get("pathParameters") or {}).get("request_id")
    if not request_id:
        return {
            "statusCode": HTTPStatus.BAD_REQUEST.value,
            "headers": CORS_HEADERS,
            "body": json.dumps({"error": True, "message": "Missing request_id"}),
        }
    if not REPORT_STATUS_TABLE:
        return {
            "statusCode": HTTPStatus.INTERNAL_SERVER_ERROR.value,
            "headers": CORS_HEADERS,
            "body": json.dumps({"error": True, "message": "Report status not configured"}),
        }
    try:
        table = dynamodb.Table(REPORT_STATUS_TABLE)
        row = table.get_item(Key={"request_id": request_id})
        item = row.get("Item")
        if not item:
            return {
                "statusCode": HTTPStatus.NOT_FOUND.value,
                "headers": CORS_HEADERS,
                "body": json.dumps({"error": True, "message": "Report not found", "request_id": request_id}),
            }
        status = item.get("status", "processing")
        payload = {"request_id": request_id}
        if status == "completed":
            payload["status"] = "success"
            if item.get("pdf_url") is not None:
                payload["pdf_url"] = item["pdf_url"]
            if item.get("report") is not None:
                payload["report"] = _from_dynamodb(item["report"])
            if item.get("brand_name") is not None:
                payload["brand_name"] = item["brand_name"]
            if item.get("query") is not None:
                payload["query"] = item["query"]
            if item.get("category") is not None:
                payload["category"] = item["category"]
            if item.get("execution_time_ms") is not None:
                payload["execution_time_ms"] = int(item["execution_time_ms"])
            if item.get("product_count") is not None:
                payload["product_count"] = int(item["product_count"])
        elif status == "failed":
            payload["status"] = "failed"
            payload["error"] = True
            payload["message"] = item.get("error", "Unknown error")
        else:
            payload["status"] = "processing"
        return {
            "statusCode": HTTPStatus.OK.value,
            "headers": CORS_HEADERS,
            "body": json.dumps(payload),
        }
    except Exception as e:
        print(f"[{request_id}] GET report status failed: {e}")
        return {
            "statusCode": HTTPStatus.INTERNAL_SERVER_ERROR.value,
            "headers": CORS_HEADERS,
            "body": json.dumps({"error": True, "message": str(e), "request_id": request_id}),
        }


def handle_post_query_async(event: Dict, context: Any) -> Dict:
    """Validate POST body, write processing, invoke self async, return 202."""
    request_id = str(uuid.uuid4())
    try:
        body = json.loads(event.get("body", "{}"))
        user_query = (body.get("query") or "").strip()
        if not user_query:
            return error_response(
                HTTPStatus.BAD_REQUEST,
                [{"code": TRD001, "description": "Missing required field: query"}],
                request_id,
            )
        try:
            l2_category = extract_l2_category(user_query)
        except ValueError as e:
            return error_response(
                HTTPStatus.BAD_REQUEST,
                [{"code": TRD002, "description": str(e)}],
                request_id,
            )
    except json.JSONDecodeError as e:
        return error_response(
            HTTPStatus.BAD_REQUEST,
            [{"code": TRD001, "description": f"Invalid JSON body: {e}"}],
            request_id,
        )

    user_id = extract_user_id(event)
    user_email = extract_user_email(event)
    print(f"[{request_id}] Accepted async request; User: {user_email}, Query: {user_query}")

    if REPORT_STATUS_TABLE:
        try:
            now = datetime.now(timezone.utc).isoformat()
            table = dynamodb.Table(REPORT_STATUS_TABLE)
            table.put_item(
                Item={
                    "request_id": request_id,
                    "status": "processing",
                    "created_at": now,
                    "updated_at": now,
                    "user_id": user_id,
                    "user_email": user_email,
                    "user_query": user_query,
                    "l2_category": l2_category,
                    "ttl_expiry": int(time.time()) + 90 * 24 * 3600,
                }
            )
        except Exception as e:
            print(f"[{request_id}] Failed to write processing status: {e}")
            return error_response(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                [{"code": TRD007, "description": "Could not start report generation"}],
                request_id,
            )

    # Invoke self asynchronously (Event)
    try:
        function_name = context.function_name
        payload = {
            "async_report": True,
            "request_id": request_id,
            "body": event.get("body"),
            "requestContext": event.get("requestContext", {}),
        }
        lambda_client.invoke(
            FunctionName=function_name,
            InvocationType="Event",
            Payload=json.dumps(payload),
        )
    except Exception as e:
        print(f"[{request_id}] Async invoke failed: {e}")
        if REPORT_STATUS_TABLE:
            try:
                table = dynamodb.Table(REPORT_STATUS_TABLE)
                table.update_item(
                    Key={"request_id": request_id},
                    UpdateExpression="SET #s = :failed, #e = :err, updated_at = :now",
                    ExpressionAttributeNames={"#s": "status", "#e": "error"},
                    ExpressionAttributeValues={
                        ":failed": "failed",
                        ":err": str(e),
                        ":now": datetime.now(timezone.utc).isoformat(),
                    },
                )
            except Exception:
                pass
        return error_response(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            [{"code": TRD007, "description": "Could not start background job"}],
            request_id,
        )

    return {
        "statusCode": HTTPStatus.ACCEPTED.value,
        "headers": CORS_HEADERS,
        "body": json.dumps({
            "status": "processing",
            "request_id": request_id,
            "message": "Report is being generated. Poll GET /report/{request_id} for status and result.",
        }),
    }


def run_report_worker(event: Dict) -> None:
    """Run full report generation and write result to report_status (no return to client)."""
    request_id = event.get("request_id", "")
    body_str = event.get("body") or "{}"
    request_context = event.get("requestContext") or {}
    try:
        body = json.loads(body_str) if isinstance(body_str, str) else body_str
    except json.JSONDecodeError:
        _write_report_status_failed(request_id, "Invalid request body")
        return
    # Build event shape expected by execute_report_generation
    inner_event = {"body": json.dumps(body), "requestContext": request_context}
    try:
        result = execute_report_generation(inner_event, request_id)
        _write_report_status_completed(request_id, result)
    except Exception as e:
        print(f"[{request_id}] Worker failed: {e}")
        _write_report_status_failed(request_id, str(e))


def _write_report_status_completed(request_id: str, result: Dict) -> None:
    if not REPORT_STATUS_TABLE:
        return
    try:
        table = dynamodb.Table(REPORT_STATUS_TABLE)
        now = datetime.now(timezone.utc).isoformat()
        item = {
            "request_id": request_id,
            "status": "completed",
            "updated_at": now,
            "pdf_url": result.get("pdf_url"),
            "brand_name": result.get("brand_name"),
            "query": result.get("query"),
            "category": result.get("category"),
            "execution_time_ms": result.get("execution_time_ms"),
            "product_count": result.get("product_count"),
            "ttl_expiry": int(time.time()) + 90 * 24 * 3600,
        }
        report = result.get("report")
        if report is not None:
            item["report"] = _float_to_decimal(report)
        table.put_item(Item=item)
        print(f"[{request_id}] Report status updated to completed")
    except Exception as e:
        print(f"[{request_id}] Failed to write completed status: {e}")


def _write_report_status_failed(request_id: str, error_message: str) -> None:
    if not REPORT_STATUS_TABLE:
        return
    try:
        table = dynamodb.Table(REPORT_STATUS_TABLE)
        table.update_item(
            Key={"request_id": request_id},
            UpdateExpression="SET #s = :failed, #e = :err, updated_at = :now",
            ExpressionAttributeNames={"#s": "status", "#e": "error"},
            ExpressionAttributeValues={
                ":failed": "failed",
                ":err": error_message,
                ":now": datetime.now(timezone.utc).isoformat(),
            },
        )
        print(f"[{request_id}] Report status updated to failed")
    except Exception as e:
        print(f"[{request_id}] Failed to write failed status: {e}")


def execute_report_generation(event: Dict, request_id: str) -> Dict:
    """
    Full V2 flow: Athena top 5 -> market context -> brand proposal -> product ideas -> Titan images -> report -> PDF.
    Returns dict with report (for DynamoDB/storage), pdf_url, brand_name, query, category, execution_time_ms, product_count.
    """
    start_time = time.time()

    body = json.loads(event.get("body", "{}"))
    user_query = (body.get("query") or "").strip()
    if not user_query:
        raise ValueError("Missing query")

    user_id = extract_user_id(event)
    user_email = extract_user_email(event)
    print(f"[{request_id}] Worker started; User: {user_email}, Query: {user_query}")

    try:
        l2_category = extract_l2_category(user_query)
    except ValueError as e:
        raise ValueError(str(e))
    print(f"[{request_id}] Extracted L2 category: {l2_category}")

    # Step 2 + 3.5: Athena and Web insights in parallel
    products: List[Dict] = []
    athena_duration = 0.0
    web_insights: Dict[str, Any] = {}
    web_search_disclaimer = False

    def _run_athena() -> tuple:
        start = time.time()
        try:
            prods = query_athena_top_products(
                l2_category=l2_category,
                workgroup=ATHENA_WORKGROUP,
                database=ATHENA_DATABASE,
            )
            return (prods, None, (time.time() - start) * 1000)
        except Exception as e:
            return ([], e, (time.time() - start) * 1000)

    def _run_web_insights() -> tuple:
        insights: Dict[str, Any] = {}
        disclaimer = False
        cache_key = f"web_insights#{l2_category}"
        try:
            if WEB_INSIGHTS_CACHE_TABLE:
                try:
                    table = dynamodb.Table(WEB_INSIGHTS_CACHE_TABLE)
                    row = table.get_item(Key={"cache_key": cache_key})
                    item = row.get("Item")
                    if item and item.get("ttl_expiry", 0) > int(time.time()):
                        payload = item.get("payload")
                        if isinstance(payload, dict):
                            insights = payload
                            print(f"[{request_id}] Web insights from cache")
                except Exception as e:
                    print(f"[{request_id}] Cache read failed: {e}")
            if not insights:
                insights = market_research_search_all(l2_category=l2_category, user_query=user_query)
                has_any = bool(
                    (insights.get("trends") or [])
                    or (insights.get("pain_points") or [])
                    or (insights.get("competitors") or [])
                )
                if has_any and WEB_INSIGHTS_CACHE_TABLE:
                    _table_name = WEB_INSIGHTS_CACHE_TABLE
                    _cache_key = cache_key
                    _payload = _float_to_decimal(insights)
                    _ttl = int(time.time()) + 6 * 3600
                    try:
                        ThreadPoolExecutor(max_workers=1).submit(
                            _write_web_insights_cache,
                            _table_name,
                            _cache_key,
                            _payload,
                            _ttl,
                            AWS_REGION,
                        )
                    except Exception as e:
                        print(f"[{request_id}] Cache write submit failed: {e}")
                if not has_any:
                    disclaimer = True
                    print(f"[{request_id}] Web search returned no results; report will include disclaimer")
        except Exception as e:
            disclaimer = True
            insights = {}
            print(f"[{request_id}] Web search failed (non-blocking): {e}")
        return (insights, disclaimer)

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_athena = executor.submit(_run_athena)
        future_web = executor.submit(_run_web_insights)
        products, athena_error, athena_duration = future_athena.result()
        web_insights, web_search_disclaimer = future_web.result()

    if athena_error:
        print(f"[{request_id}] Athena failed: {athena_error}")
        raise RuntimeError(f"Athena query failed: {str(athena_error)}")
    if not products:
        raise ValueError(f"No trending products found in category '{l2_category}' for the last 30 days")
    print(f"[{request_id}] Athena: {len(products)} products, {athena_duration:.0f}ms")

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
            web_insights=web_insights if web_insights else None,
        )
        print(f"[{request_id}] Brand proposal: {brand_proposal.get('brand_name', '')}")
    except Exception as e:
        print(f"[{request_id}] Brand generation failed: {e}")
        raise RuntimeError(f"Brand generation failed: {str(e)}") from e

    brand_name = brand_proposal.get("brand_name") or ""
    brand_tagline = brand_proposal.get("brand_tagline") or ""

    # Step 5: Product ideas
    try:
        product_ideas_raw = generate_product_ideas(
            market_context=market_context,
            brand_proposal=brand_proposal,
            l2_category=l2_category,
            bedrock_client=bedrock,
            model_id=BEDROCK_PRIMARY_MODEL,
            web_insights=web_insights if web_insights else None,
        )
        print(f"[{request_id}] Product ideas: {len(product_ideas_raw)}")
    except Exception as e:
        print(f"[{request_id}] Product ideas failed: {e}")
        raise RuntimeError(f"Product ideas generation failed: {str(e)}") from e

    # Step 6: Brand logo + product images in parallel
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
                max_workers=4,
            )
            for future in as_completed([future_logo, future_images]):
                if future == future_logo:
                    try:
                        brand_logo_bytes = future.result()
                        if brand_logo_bytes:
                            # Remove light/grey background so PDF and UI show logo only (transparent PNG)
                            cleaned = logo_remove_background(brand_logo_bytes)
                            if cleaned is not None:
                                brand_logo_bytes = cleaned
                        print(f"[{request_id}] Brand logo: ok={brand_logo_bytes is not None}")
                    except Exception as e:
                        print(f"[{request_id}] Brand logo failed: {e}")
                else:
                    try:
                        image_bytes_list = future.result()
                    except Exception as e:
                        print(f"[{request_id}] Product images failed: {e}")
                        raise RuntimeError(f"Image generation failed: {str(e)}") from e
    except Exception as e:
        print(f"[{request_id}] Image step failed: {e}")
        raise RuntimeError(f"Image generation failed: {str(e)}") from e

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

    # Step 7: Format report (V2 structure)
    report = format_report_v2(
        user_query=user_query,
        l2_category=l2_category,
        market_context=market_context,
        brand_proposal=brand_proposal,
        product_ideas=product_ideas,
        brand_logo_bytes=brand_logo_bytes,
        web_search_insights=web_insights,
        web_search_disclaimer=web_search_disclaimer,
    )

    # Step 8: PDF and upload
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

    # Step 9: DynamoDB log (audit)
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

    # Report with thumbnail images for frontend (stored in report_status)
    response_report = _report_with_thumbnail_images(
        report, product_ideas=product_ideas, brand_logo_bytes=brand_logo_bytes
    )
    return {
        "report": response_report,
        "pdf_url": pdf_url,
        "brand_name": brand_proposal.get("brand_name", ""),
        "query": user_query,
        "category": l2_category,
        "execution_time_ms": int(total_duration),
        "product_count": len(product_ideas),
    }


def format_report_v2(
    user_query: str,
    l2_category: str,
    market_context: List[Dict],
    brand_proposal: Dict,
    product_ideas: List[Dict],
    brand_logo_bytes: Optional[bytes] = None,
    web_search_insights: Optional[Dict] = None,
    web_search_disclaimer: bool = False,
) -> Dict:
    """Build report dict for V2. Adds image_base64 for frontend/PDF; brand_proposal gets logo_image_base64; optional web_search_insights and disclaimer."""
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
    # Include top 5 market products for PDF "Market Research" page (name + short description)
    market_list = []
    for p in market_context[:5]:
        name = p.get("product_name") or "Unknown"
        shop = p.get("shop_name") or ""
        rev = float(p.get("revenue_usd") or 0)
        growth = float(p.get("mom_growth_pct") or 0)
        desc = f"Top seller at {shop}. ${rev:,.0f} revenue, {growth:.1f}% growth (Last 30 Days)." if shop else f"${rev:,.0f} revenue, {growth:.1f}% growth (Last 30 Days)."
        market_list.append({"product_name": name, "short_description": desc})
    out = {
        "query": user_query,
        "category": l2_category,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_period": "Last 30 Days",
        "market_context": market_list,
        "brand_proposal": brand_out,
        "product_ideas": ideas_out,
    }
    if web_search_insights is not None:
        out["web_search_insights"] = web_search_insights
    if web_search_disclaimer:
        out["web_search_disclaimer"] = True
    return out


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
    out["brand_proposal"] = {k: v for k, v in bp.items() if k not in ("logo_image_base64", "logo_image_base64_format")}
    ideas = []
    for p in out.get("product_ideas") or []:
        ideas.append({k: v for k, v in (p if isinstance(p, dict) else {}).items() if k not in ("image_base64", "image_base64_format")})
    out["product_ideas"] = ideas
    return out


def _report_with_thumbnail_images(
    report: Dict,
    product_ideas: List[Dict],
    brand_logo_bytes: Optional[bytes] = None,
) -> Dict:
    """Return a copy of the report with thumbnail base64 for frontend; logo as PNG (transparent), product images as JPEG."""
    response_report = _report_for_dynamodb(report)
    thumb_size = 256
    if brand_logo_bytes:
        logo_b64 = logo_to_thumbnail_base64(brand_logo_bytes, size=thumb_size)
        if logo_b64:
            response_report.setdefault("brand_proposal", {})["logo_image_base64"] = logo_b64
            response_report["brand_proposal"]["logo_image_base64_format"] = "png"
    for i, idea in enumerate(product_ideas):
        img_bytes = idea.get("_image_bytes")
        if img_bytes and i < len(response_report.get("product_ideas") or []):
            thumb_b64 = image_bytes_to_thumbnail_base64(img_bytes, size=thumb_size)
            if thumb_b64:
                response_report["product_ideas"][i]["image_base64"] = thumb_b64
                response_report["product_ideas"][i]["image_base64_format"] = "jpeg"
    return response_report


def _write_web_insights_cache(table_name: str, cache_key: str, payload: Any, ttl: int, region_name: str) -> None:
    """Fire-and-forget helper: write web insights to DynamoDB cache (called from a thread, no await)."""
    try:
        res = boto3.resource("dynamodb", region_name=region_name)
        res.Table(table_name).put_item(
            Item={"cache_key": cache_key, "payload": payload, "ttl_expiry": ttl}
        )
    except Exception as e:
        print(f"Web insights cache write failed: {e}")


def _float_to_decimal(obj: Any) -> Any:
    """Recursively convert floats to Decimal for DynamoDB (does not support float)."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: _float_to_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_float_to_decimal(v) for v in obj]
    return obj


def _from_dynamodb(obj: Any) -> Any:
    """Recursively convert Decimal to float for JSON serialization (GET response)."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _from_dynamodb(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_from_dynamodb(v) for v in obj]
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
