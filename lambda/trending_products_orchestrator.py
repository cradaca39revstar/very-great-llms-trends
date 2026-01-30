"""
LLM Trending Products Report Generator - Lambda Orchestrator
Coordinates Athena queries, Bedrock AI generation, and PDF report creation
Target latency: 20-25 seconds end-to-end
"""

import json
import os
import time
import uuid
import re
from datetime import datetime, timezone
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import boto3
from botocore.exceptions import ClientError

# Import utility modules
from utils.athena_helper import (
    query_athena_top_products,
    validate_athena_connection
)
from utils.bedrock_helper import (
    generate_brand_name,
    generate_supporting_trends,
    search_product_info_via_bedrock
)
from utils.pdf_generator import (
    generate_pdf_report,
    upload_pdf_to_s3
)

# Environment variables
ATHENA_WORKGROUP = os.environ.get('ATHENA_WORKGROUP')
ATHENA_DATABASE = os.environ.get('ATHENA_DATABASE')
BEDROCK_PRIMARY_MODEL = os.environ.get('BEDROCK_PRIMARY_MODEL')
BEDROCK_FALLBACK_MODEL = os.environ.get('BEDROCK_FALLBACK_MODEL')
DYNAMODB_LOGS_TABLE = os.environ.get('DYNAMODB_LOGS_TABLE')
PDF_BUCKET = os.environ.get('PDF_BUCKET')
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'poc')
AWS_REGION = os.environ.get('AWS_REGION_NAME', 'us-east-1')

# AWS clients
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
cloudwatch = boto3.client('cloudwatch', region_name=AWS_REGION)
bedrock = boto3.client('bedrock-runtime', region_name=AWS_REGION)

# Supported L2 categories
SUPPORTED_L2_CATEGORIES = [
    "Skincare",
    "Haircare & Styling",
    "Makeup",
    "Bath & Body Care",
    "Fragrance",
    "Tools & Accessories"
]


def lambda_handler(event, context):
    """
    Main Lambda handler for LLM Trending Products Report Generator
    
    Args:
        event: API Gateway event with body containing user query
        context: Lambda context object
        
    Returns:
        API Gateway response with report and PDF URL
    """
    start_time = time.time()
    request_id = str(uuid.uuid4())
    
    print(f"[{request_id}] Starting LLM Trending Products request")
    
    try:
        # Parse API Gateway event
        body = json.loads(event.get('body', '{}'))
        user_query = body.get('query', '')
        
        if not user_query:
            return error_response(400, "Missing required field: query", request_id)
        
        # Extract user info from JWT claims (from Cognito authorizer)
        user_id = extract_user_id(event)
        user_email = extract_user_email(event)
        
        print(f"[{request_id}] User: {user_email}, Query: {user_query}")
        
        # Step 1: Extract L2 category from query
        try:
            l2_category = extract_l2_category(user_query)
            print(f"[{request_id}] Extracted L2 category: {l2_category}")
        except ValueError as e:
            return error_response(400, str(e), request_id)
        
        # Step 2: Query Athena for top 5 products
        query_start = time.time()
        try:
            products = query_athena_top_products(
                l2_category=l2_category,
                workgroup=ATHENA_WORKGROUP,
                database=ATHENA_DATABASE
            )
            athena_duration = (time.time() - query_start) * 1000
            print(f"[{request_id}] Athena query completed: {len(products)} products, {athena_duration:.0f}ms")
            
            if not products:
                return error_response(
                    404, 
                    f"No trending products found in category '{l2_category}' for the last 30 days",
                    request_id
                )
        except Exception as e:
            print(f"[{request_id}] Athena query failed: {str(e)}")
            return error_response(500, f"Failed to query data: {str(e)}", request_id)
        
        # Step 3: Process products in parallel with AI enhancement
        bedrock_start = time.time()
        try:
            enhanced_products = process_products_parallel(products, request_id)
            bedrock_duration = (time.time() - bedrock_start) * 1000
            print(f"[{request_id}] Bedrock processing completed: {bedrock_duration:.0f}ms")
        except Exception as e:
            print(f"[{request_id}] Bedrock processing failed: {str(e)}")
            return error_response(500, f"Failed to generate AI insights: {str(e)}", request_id)
        
        # Step 4: Format report
        report = format_report(
            query=user_query,
            category=l2_category,
            products=enhanced_products
        )
        
        # Step 5: Generate PDF
        pdf_start = time.time()
        try:
            pdf_url = generate_and_upload_pdf(report, request_id, l2_category)
            pdf_duration = (time.time() - pdf_start) * 1000
            print(f"[{request_id}] PDF generated: {pdf_duration:.0f}ms, URL: {pdf_url}")
        except Exception as e:
            print(f"[{request_id}] PDF generation failed: {str(e)}")
            pdf_url = None
            pdf_duration = 0
        
        # Calculate total execution time
        total_duration = (time.time() - start_time) * 1000
        
        # Step 6: Log to DynamoDB (non-blocking)
        try:
            log_to_dynamodb({
                'request_id': request_id,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'user_id': user_id,
                'user_email': user_email,
                'user_query': user_query,
                'l2_category': l2_category,
                'products_queried': [p.get('product_id') for p in products],
                'final_report': report,
                'pdf_url': pdf_url,
                'execution_time_ms': int(total_duration),
                'athena_duration_ms': int(athena_duration),
                'bedrock_duration_ms': int(bedrock_duration),
                'pdf_duration_ms': int(pdf_duration),
                'status': 'success'
            })
        except Exception as e:
            print(f"[{request_id}] Warning: DynamoDB logging failed: {str(e)}")
        
        # Publish CloudWatch metrics
        publish_metrics({
            'TrendingReportRequests': 1,
            'TotalReportDuration': total_duration,
            'AthenaQueryDuration': athena_duration,
            'BedrockCallDuration': bedrock_duration,
            'PDFGenerationDuration': pdf_duration
        })
        
        print(f"[{request_id}] Request completed successfully in {total_duration:.0f}ms")
        
        # Return success response
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key',
                'Access-Control-Allow-Methods': 'POST,OPTIONS'
            },
            'body': json.dumps({
                'status': 'success',
                'request_id': request_id,
                'query': user_query,
                'category': l2_category,
                'report': report,
                'pdf_url': pdf_url,
                'execution_time_ms': int(total_duration),
                'product_count': len(enhanced_products)
            })
        }
        
    except Exception as e:
        print(f"[{request_id}] Unexpected error: {str(e)}")
        return error_response(500, f"Internal server error: {str(e)}", request_id)


def extract_l2_category(user_query: str) -> str:
    """
    Extract L2 category from natural language query
    
    Args:
        user_query: User's natural language question
        
    Returns:
        L2 category name
        
    Raises:
        ValueError: If category cannot be extracted
    """
    query_lower = user_query.lower()
    
    # Check each supported category
    for category in SUPPORTED_L2_CATEGORIES:
        # Check exact match or partial match
        if category.lower() in query_lower:
            return category
        
        # Handle common variations
        if category == "Haircare & Styling" and ("haircare" in query_lower or "hair care" in query_lower):
            return category
        if category == "Bath & Body Care" and ("bath" in query_lower or "body care" in query_lower):
            return category
        if category == "Tools & Accessories" and ("tools" in query_lower or "accessories" in query_lower):
            return category
    
    # Category not found
    raise ValueError(
        f"Category not found in query: '{user_query}'. "
        f"Supported categories: {', '.join(SUPPORTED_L2_CATEGORIES)}"
    )


def process_products_parallel(products: List[Dict], request_id: str) -> List[Dict]:
    """
    Process all products in parallel with AI enhancement
    CRITICAL: This achieves 10-15s vs 50-75s sequential processing
    
    Args:
        products: List of product dicts from Athena
        request_id: Request ID for logging
        
    Returns:
        List of enhanced product dicts with brand names, URLs, trends
    """
    enhanced_products = []
    
    # Use ThreadPoolExecutor for parallel processing
    with ThreadPoolExecutor(max_workers=5) as executor:
        # Submit all products for processing
        future_to_product = {
            executor.submit(process_single_product, product, request_id): product
            for product in products
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_product):
            product = future_to_product[future]
            try:
                enhanced_product = future.result()
                enhanced_products.append(enhanced_product)
            except Exception as e:
                print(f"[{request_id}] Error processing product {product.get('product_id')}: {str(e)}")
                # Continue with partial data
                enhanced_products.append(product)
    
    # Sort by revenue rank to maintain order
    enhanced_products.sort(key=lambda p: p.get('revenue_rank', 999))
    
    return enhanced_products


def process_single_product(product: Dict, request_id: str) -> Dict:
    """
    Process a single product with AI enhancement
    
    Args:
        product: Product dict from Athena
        request_id: Request ID for logging
        
    Returns:
        Enhanced product dict
    """
    product_id = product.get('product_id')
    product_name = product.get('product_name')
    shop_name = product.get('shop_name')
    
    print(f"[{request_id}] Processing product {product_id}: {product_name[:50]}...")
    
    # Generate brand name
    try:
        brand_name = generate_brand_name(
            product_name=product_name,
            shop_name=shop_name,
            bedrock_client=bedrock,
            model_id=BEDROCK_PRIMARY_MODEL
        )
        product['brand_name'] = brand_name
        print(f"[{request_id}] Product {product_id} brand: {brand_name}")
    except Exception as e:
        print(f"[{request_id}] Brand generation failed for {product_id}: {str(e)}")
        # Fallback: Extract brand from shop name
        product['brand_name'] = shop_name.split()[0] if shop_name else "Unknown"
    
    # Search for product info (URL, description, image)
    try:
        product_info = search_product_info_via_bedrock(
            brand_name=product.get('brand_name', ''),
            product_name=product_name,
            bedrock_client=bedrock,
            model_id=BEDROCK_PRIMARY_MODEL
        )
        product['url'] = product_info.get('url', '')
        product['description'] = product_info.get('description', '')
        product['image_url'] = product_info.get('image_url', '')
    except Exception as e:
        print(f"[{request_id}] Product search failed for {product_id}: {str(e)}")
        product['url'] = ''
        product['description'] = f"A trending {product.get('l2_category', 'beauty')} product."
        product['image_url'] = ''
    
    # Generate 5 supporting trends
    try:
        trends = generate_supporting_trends(
            product_data=product,
            bedrock_client=bedrock,
            model_id=BEDROCK_PRIMARY_MODEL
        )
        product['supporting_trends'] = trends
        print(f"[{request_id}] Product {product_id} trends generated: {len(trends)} trends")
    except Exception as e:
        print(f"[{request_id}] Trends generation failed for {product_id}: {str(e)}")
        product['supporting_trends'] = []
    
    return product


def format_report(query: str, category: str, products: List[Dict]) -> Dict:
    """
    Format final report structure matching architecture specifications
    
    Args:
        query: Original user query
        category: L2 category
        products: List of enhanced products
        
    Returns:
        Formatted report dict
    """
    return {
        'query': query,
        'category': category,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'data_period': 'Last 30 Days',
        'products': [
            {
                'rank': i + 1,
                'product_id': p.get('product_id'),
                'brand_name': p.get('brand_name', 'Unknown'),
                'product_name': clean_product_name(p.get('product_name', '')),
                'image_url': p.get('image_url', ''),
                'brand_url': p.get('url', ''),
                'description': p.get('description', ''),
                'revenue_trend': format_revenue_trend(p.get('mom_growth_pct', 0)),
                'revenue_scale': format_revenue_scale(p.get('revenue_usd', 0)),
                'category_rank': format_category_rank(p.get('revenue_rank', i + 1)),
                'supporting_trends': p.get('supporting_trends', [])
            }
            for i, p in enumerate(products)
        ]
    }


def generate_and_upload_pdf(report: Dict, request_id: str, category: str) -> str:
    """
    Generate PDF and upload to S3, return signed URL
    
    Args:
        report: Formatted report dict
        request_id: Request ID for filename
        category: L2 category for filename
        
    Returns:
        Pre-signed S3 URL (1-hour expiration)
    """
    # Generate PDF bytes
    pdf_bytes = generate_pdf_report(report)
    
    # Create filename with timestamp
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    category_slug = category.lower().replace(' & ', '-').replace(' ', '-')
    filename = f"trending-products-{category_slug}-{timestamp}.pdf"
    
    # Upload to S3 with date-based folder structure
    date_path = datetime.now(timezone.utc).strftime('%Y/%m/%d')
    s3_key = f"reports/{date_path}/{filename}"
    
    # Upload and get signed URL
    pdf_url = upload_pdf_to_s3(
        pdf_bytes=pdf_bytes,
        bucket=PDF_BUCKET,
        key=s3_key,
        expiration=3600  # 1 hour
    )
    
    return pdf_url


def extract_user_id(event: Dict) -> str:
    """Extract user ID from API Gateway authorizer context"""
    try:
        claims = event.get('requestContext', {}).get('authorizer', {}).get('claims', {})
        return claims.get('sub', 'unknown')
    except:
        return 'unknown'


def extract_user_email(event: Dict) -> str:
    """Extract user email from API Gateway authorizer context"""
    try:
        claims = event.get('requestContext', {}).get('authorizer', {}).get('claims', {})
        return claims.get('email', 'unknown')
    except:
        return 'unknown'


def clean_product_name(product_name: str) -> str:
    """
    Clean product name by removing promotional text and normalizing
    
    Args:
        product_name: Raw product name from data
        
    Returns:
        Cleaned product name
    """
    # Remove common promotional keywords
    promotional_keywords = [
        'TikTokShopBlackFriday',
        'Buy 1 Get 1 Free',
        'BOGO',
        'Limited Edition',
        'New Release'
    ]
    
    cleaned = product_name
    for keyword in promotional_keywords:
        cleaned = cleaned.replace(keyword, '')
    
    # Remove excessive whitespace
    cleaned = ' '.join(cleaned.split())
    
    return cleaned


def format_revenue_trend(mom_growth_pct: float) -> str:
    """Format revenue trend as percentage with +/- sign"""
    try:
        val = float(mom_growth_pct) if mom_growth_pct not in (None, '') else 0.0
    except (TypeError, ValueError):
        val = 0.0
    if val >= 0:
        return f"+{val:.1f}% Last 30 Days"
    else:
        return f"{val:.1f}% Last 30 Days"


def format_revenue_scale(revenue_usd: float) -> str:
    """Format revenue as USD currency"""
    try:
        val = float(revenue_usd) if revenue_usd not in (None, '') else 0.0
    except (TypeError, ValueError):
        val = 0.0
    return f"${val:,.0f} Last 30 Days"


def format_category_rank(rank: int) -> str:
    """Format category rank with change indicator"""
    try:
        val = int(rank) if rank not in (None, '') else 0
    except (TypeError, ValueError):
        val = 0
    return f"[{val}], +0 in Last 30 Days"


def log_to_dynamodb(log_data: Dict):
    """
    Log request data to DynamoDB for audit trail
    Non-blocking - don't fail if logging fails
    
    Args:
        log_data: Dict with request metadata
    """
    try:
        table = dynamodb.Table(DYNAMODB_LOGS_TABLE)
        
        # Add TTL (90 days from now)
        ttl_expiry = int(time.time()) + (90 * 24 * 60 * 60)
        log_data['ttl_expiry'] = ttl_expiry
        
        table.put_item(Item=log_data)
        print(f"[{log_data['request_id']}] Logged to DynamoDB")
    except Exception as e:
        print(f"Warning: DynamoDB logging failed: {str(e)}")
        # Don't raise - logging failure shouldn't break the request


def publish_metrics(metrics: Dict):
    """
    Publish custom metrics to CloudWatch
    
    Args:
        metrics: Dict of metric_name: value
    """
    try:
        metric_data = [
            {
                'MetricName': name,
                'Value': value,
                'Unit': 'Milliseconds' if 'Duration' in name else 'Count',
                'Timestamp': datetime.now(timezone.utc)
            }
            for name, value in metrics.items()
        ]
        
        cloudwatch.put_metric_data(
            Namespace='BeautyProducts/LLM',
            MetricData=metric_data
        )
    except Exception as e:
        print(f"Warning: CloudWatch metrics publishing failed: {str(e)}")


def error_response(status_code: int, message: str, request_id: str) -> Dict:
    """
    Generate standardized error response
    
    Args:
        status_code: HTTP status code
        message: Error message
        request_id: Request ID for tracking
        
    Returns:
        API Gateway response dict
    """
    # Log error metric
    try:
        cloudwatch.put_metric_data(
            Namespace='BeautyProducts/LLM',
            MetricData=[
                {
                    'MetricName': 'ErrorCount',
                    'Value': 1,
                    'Unit': 'Count',
                    'Timestamp': datetime.now(timezone.utc)
                }
            ]
        )
    except:
        pass
    
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'error': True,
            'message': message,
            'request_id': request_id,
            'supported_categories': SUPPORTED_L2_CATEGORIES if status_code == 400 else None
        })
    }
