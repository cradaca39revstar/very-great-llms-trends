"""
AWS Bedrock Helper Module
Wrapper functions for invoking foundation models with retry logic
"""

import json
import re
import time
import os
from typing import Dict, List
import boto3
from botocore.exceptions import ClientError

# Prompt templates
BRAND_NAME_PROMPT = """Based on the following product information, generate the brand name:
Product Name: {product_name}
Shop Name: {shop_name}

Generate only the brand name (e.g., "Vital Proteins", "The Ordinary", "e.l.f. Cosmetics").
Do not include the product name, just the brand.
Output only the brand name, no additional text."""

TRENDS_PROMPT = """Generate 5 macro trends that are driving the success of {product_name} in the {l2_category} category.

Product: {product_name}
Brand: {brand_name}
Category: {l2_category}
Revenue Growth: {mom_growth_pct}%
Revenue: ${revenue_usd:,.0f}
Items Sold: {item_sold:,}
{web_context_section}

Generate 5 trends, each with:
- A descriptive title (2-5 words)
- 2-3 lines of explanation (approximately 40-80 words)

Focus on:
- Market trends and consumer behavior
- Industry insights and competitive dynamics
- Scientific or ingredient-driven trends
- Lifestyle and wellness integration
- Economic or distribution factors

Format each trend exactly as:
1. [Trend Title]
[2-3 lines of detailed explanation]

2. [Trend Title]
[2-3 lines of detailed explanation]

Continue for all 5 trends."""

PRODUCT_SEARCH_PROMPT = """You are a precise assistant for an automated e-commerce product enrichment pipeline.
You MUST respond ONLY with valid JSON, no other text.

Given this product, find the BEST available product page and image:

Brand: {brand_name}
Product: {product_name}
Category: {l2_category}

Your task is to provide:

1. "url": The best product page URL, priority order:
   a) Official brand website product page (highest preference)
   b) Major retailer product page (Amazon, Sephora, Ulta, Walmart, Target, CVS, Walgreens, iHerb)
   c) If neither is known, use ONE of these fallback search URLs (set url_confidence to "search_fallback"):
      - https://www.amazon.com/s?k={{brand_name}}+{{product_name}}
      - https://www.sephora.com/search?q={{brand_name}}+{{product_name}}
      - https://www.walmart.com/search?q={{brand_name}}+{{product_name}}
   d) If you cannot find or reasonably estimate any URL, use "".

   Rules:
   - ONLY provide URLs you are confident exist based on training data.
   - For lesser-known brands, prefer major retailer URLs.
   - Do NOT construct URLs from brand names (like https://{{brand}}.com).
   - Do NOT use example.com or any placeholder domains.

2. "image_url": Direct link to a product image (embeddable URL):
   - Must start with https:// or http://
   - Must end in .jpg, .jpeg, .png, .webp, .gif
     OR contain a known image CDN domain (e.g., cdn.shopify.com, images-na.ssl-images-amazon.com, cloudinary, imgix).
   - Must point to an actual product image (not just a logo or generic banner).
   - If you are NOT confident about a specific image URL, use "".

3. "description": 2–3 sentences describing the product, its benefits, and key ingredients/features.
   - You may generate this; it does NOT need to come from a real page.

4. "url_confidence": One of:
   - "brand_official"       → Official brand website product page
   - "retailer_product"     → Product page on a major retailer
   - "retailer_brand_store" → Official brand store page on a retailer
   - "search_fallback"      → One of the search URLs above
   - "unknown"              → No reliable URL found

Global rules:
- When in doubt about "url" or "image_url", use the empty string "".
- Output ONLY a single JSON object, no markdown, no comments, no explanations.

Return your answer in exactly this JSON shape:
{{"url": "...", "url_confidence": "brand_official|retailer_product|retailer_brand_store|search_fallback|unknown", "image_url": "...", "description": "..."}}"""


def _looks_like_placeholder_url(url: str) -> bool:
    """Return True if URL is empty or a known placeholder/example domain."""
    if not url or not isinstance(url, str):
        return True
    u = url.strip().lower()
    if not u.startswith(("http://", "https://")):
        return True
    # Reject example/placeholder domains
    placeholders = [
        "example.com", "example.org", "example.net",
        "placeholder", "test.com", "dummy.com",
        "sample.com", "brandname.com", "yoursite.com"
    ]
    if any(p in u for p in placeholders):
        return True
    return False


def _looks_like_valid_image_url(url: str) -> bool:
    """Return True if URL looks like a direct image link (extension or known CDN path)."""
    if not url or not isinstance(url, str):
        return False
    u = url.strip()
    if not u.startswith(("http://", "https://")):
        return False
    u_lower = u.lower()
    
    # Common image extensions
    if re.search(r"\.(jpg|jpeg|png|webp|gif)(\?|$)", u_lower):
        return True
    
    # Known image CDN path patterns
    cdn_patterns = [
        r"/(images?|img|assets|media|cdn|productimages)/",
        "cloudfront", "amazonaws", ".cdn.",
        "cdn.shopify.com",
        "images-na.ssl-images-amazon.com",
        "cloudinary", "imgix",
        "sephora.com/productimages",
        "ulta.com/images",
        "target.com/img",
        "walmart.com/images",
        "amazon.com/images",
        "deciem.com/cdn",
        "shopify.com/s/files",
    ]
    
    if any(pattern in u_lower if "/" not in pattern else re.search(pattern, u_lower) for pattern in cdn_patterns):
        return True
    
    return False


VALID_URL_CONFIDENCE = frozenset({
    "brand_official", "retailer_product", "retailer_brand_store", "search_fallback", "unknown"
})


def _clean_product_info(product_info: Dict) -> Dict:
    """
    Validate and clean product_info after JSON parse.
    Clears url/image_url that are placeholders or invalid; keeps description and url_confidence.
    """
    if not isinstance(product_info, dict):
        return {"url": "", "description": "", "image_url": "", "url_confidence": "unknown"}
    raw_confidence = str(product_info.get("url_confidence", "") or "").strip().lower()
    url_confidence = raw_confidence if raw_confidence in VALID_URL_CONFIDENCE else "unknown"
    result = {
        "url": "",
        "description": str(product_info.get("description", "") or "").strip() or "",
        "image_url": "",
        "url_confidence": url_confidence,
    }
    url = str(product_info.get("url", "") or "").strip()
    if url and not _looks_like_placeholder_url(url):
        result["url"] = url
    image_url = str(product_info.get("image_url", "") or "").strip()
    if image_url and _looks_like_valid_image_url(image_url):
        result["image_url"] = image_url
    return result


def generate_brand_name(
    product_name: str,
    shop_name: str,
    bedrock_client,
    model_id: str
) -> str:
    """
    Generate brand name from product and shop name using Bedrock
    
    Args:
        product_name: Product name from data
        shop_name: Shop name from data
        bedrock_client: Boto3 Bedrock client
        model_id: Bedrock model ID to use
        
    Returns:
        Brand name string
    """
    prompt = BRAND_NAME_PROMPT.format(
        product_name=product_name,
        shop_name=shop_name
    )
    
    response = invoke_model_with_retry(
        bedrock_client=bedrock_client,
        model_id=model_id,
        prompt=prompt,
        max_tokens=100
    )
    
    brand_name = extract_text_from_response(response, model_id)
    
    # Clean up the response
    brand_name = brand_name.strip().strip('"').strip("'")
    
    return brand_name


def generate_supporting_trends(
    product_data: Dict,
    bedrock_client,
    model_id: str
) -> List[str]:
    """
    Generate 5 supporting trends for a product using Bedrock
    
    Args:
        product_data: Dict with product information (may include trends_text or web_context from scraper/KB)
        bedrock_client: Boto3 Bedrock client
        model_id: Bedrock model ID to use
        
    Returns:
        List of 5 trend strings with titles and explanations
    """
    web_context = (product_data.get('trends_text') or product_data.get('web_context') or '').strip()
    web_context_section = (
        "Use the following context from the product page if relevant:\n" + web_context
        if web_context else ""
    )
    prompt = TRENDS_PROMPT.format(
        product_name=product_data.get('product_name', ''),
        brand_name=product_data.get('brand_name', ''),
        l2_category=product_data.get('l2_category', ''),
        mom_growth_pct=product_data.get('mom_growth_pct', 0),
        revenue_usd=product_data.get('revenue_usd', 0),
        item_sold=product_data.get('item_sold', 0),
        web_context_section=web_context_section
    )
    
    response = invoke_model_with_retry(
        bedrock_client=bedrock_client,
        model_id=model_id,
        prompt=prompt,
        max_tokens=2000
    )
    
    trends_text = extract_text_from_response(response, model_id)
    
    # Parse trends from response
    trends = parse_trends_from_text(trends_text)
    
    return trends


def retrieve_product_info_from_kb(
    brand_name: str,
    product_name: str,
    l2_category: str,
    knowledge_base_id: str,
    region: str
) -> Dict:
    """
    Option A: Retrieve product URL/image/snippets from Bedrock Knowledge Base.
    Returns same shape as search_product_info_via_bedrock or empty dict.
    """
    if not knowledge_base_id or not knowledge_base_id.strip():
        return {}
    try:
        client = boto3.client("bedrock-agent-runtime", region_name=region)
        query = f"Product page URL and product image URL for: {brand_name} {product_name} {l2_category}"
        resp = client.retrieve(
            knowledgeBaseId=knowledge_base_id.strip(),
            retrievalQuery={"text": query},
            retrievalConfiguration={
                "vectorSearchConfiguration": {
                    "numberOfResults": 5
                }
            },
        )
        url = ""
        image_url = ""
        description = ""
        snippets = []
        for result in resp.get("retrievalResults", []):
            content = (result.get("content") or {}).get("text") or ""
            if content:
                snippets.append(content)
            # Try to find URL and image URL in result location
            loc = result.get("location", {}) or {}
            if isinstance(loc.get("s3Location"), dict):
                s3_loc = loc["s3Location"].get("uri", "")
                if s3_loc and not url:
                    url = s3_loc if s3_loc.startswith("http") else ""
            # Often KB returns text; try to parse URL from content
            if "http" in content and not url:
                for part in content.replace(",", " ").split():
                    if part.startswith("http") and ("amazon" in part or "sephora" in part or "ulta" in part or "product" in part.lower()):
                        url = part.strip(".,;")
                        break
            if not image_url and (".jpg" in content or ".png" in content or "cdn" in content.lower() or "image" in content.lower()):
                for part in content.replace(",", " ").split():
                    if part.startswith("http") and (".jpg" in part or ".png" in part or ".webp" in part):
                        image_url = part.strip(".,;")
                        break
        if snippets:
            description = " ".join(snippets)[:500]
        result_dict = {
            "url": url[:2000] if url else "",
            "image_url": image_url[:2000] if image_url else "",
            "description": description,
            "url_confidence": "unknown",
        }
        if result_dict["url"] or result_dict["image_url"]:
            return _clean_product_info(result_dict)
        return {}
    except Exception as e:
        print(f"Knowledge Base retrieve failed: {e}")
        return {}


def search_product_info_via_bedrock(
    brand_name: str,
    product_name: str,
    bedrock_client,
    model_id: str,
    l2_category: str = ""
) -> Dict:
    """
    Search for product information using Bedrock.
    If KNOWLEDGE_BASE_ID is set, tries KB first; otherwise or on empty result, uses LLM.
    
    Args:
        brand_name: Brand name
        product_name: Product name
        bedrock_client: Boto3 Bedrock client
        model_id: Bedrock model ID to use
        l2_category: Optional L2 category (from product dict)
        
    Returns:
        Dict with url, description, image_url, url_confidence
    """
    kb_id = (os.environ.get("KNOWLEDGE_BASE_ID") or "").strip()
    if kb_id:
        region = os.environ.get("AWS_REGION_NAME") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"
        kb_result = retrieve_product_info_from_kb(
            brand_name=brand_name,
            product_name=product_name,
            l2_category=l2_category or "beauty product",
            knowledge_base_id=kb_id,
            region=region,
        )
        if kb_result and (kb_result.get("url") or kb_result.get("image_url")):
            return kb_result

    l2_cat = (l2_category or "").strip() or "beauty product"
    prompt = PRODUCT_SEARCH_PROMPT.format(
        brand_name=brand_name,
        product_name=product_name,
        l2_category=l2_cat
    )
    
    try:
        response = invoke_model_with_retry(
            bedrock_client=bedrock_client,
            model_id=model_id,
            prompt=prompt,
            max_tokens=500
        )
        
        response_text = extract_text_from_response(response, model_id)
        # Strip markdown code fences if present
        text = (response_text or "").strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```\s*$", "", text)
            text = text.strip()
        else:
            text = response_text

        # Try to parse as JSON
        try:
            product_info = json.loads(text)
            return _clean_product_info(product_info)
        except json.JSONDecodeError:
            # Fallback: do not construct fake URLs from brand names
            return {
                "url": "",
                "description": (response_text[:500] if response_text else "").strip() or f"A trending {product_name} product.",
                "image_url": "",
                "url_confidence": "unknown",
            }
    except Exception as e:
        print(f"Product search failed: {str(e)}")
        # Return default values
        return {
            "url": "",
            "description": f"A trending {product_name} product.",
            "image_url": "",
            "url_confidence": "unknown",
        }


def invoke_model_with_retry(
    bedrock_client,
    model_id: str,
    prompt: str,
    max_tokens: int = 1000,
    retries: int = 3
) -> Dict:
    """
    Invoke Bedrock model with exponential backoff retry
    
    Args:
        bedrock_client: Boto3 Bedrock client
        model_id: Model ID (Claude, Nova, Cohere)
        prompt: Prompt text
        max_tokens: Maximum tokens to generate
        retries: Number of retry attempts
        
    Returns:
        Bedrock API response dict
        
    Raises:
        Exception: If all retries fail
    """
    last_error = None
    
    for attempt in range(retries):
        try:
            return invoke_model(bedrock_client, model_id, prompt, max_tokens)
        except ClientError as e:
            error_code = e.response['Error']['Code']
            last_error = e
            
            if error_code == 'ThrottlingException':
                # Exponential backoff
                wait_time = (2 ** attempt) + (time.time() % 1)
                print(f"Bedrock throttled, retrying in {wait_time:.2f}s (attempt {attempt + 1}/{retries})")
                time.sleep(wait_time)
                
                # Try fallback model on last attempt
                if attempt == retries - 1 and model_id != os.environ.get('BEDROCK_FALLBACK_MODEL'):
                    print(f"Switching to fallback model: {os.environ.get('BEDROCK_FALLBACK_MODEL')}")
                    model_id = os.environ.get('BEDROCK_FALLBACK_MODEL')
            else:
                # Non-throttling error, raise immediately
                raise
    
    # All retries failed
    raise Exception(f"Bedrock invocation failed after {retries} attempts: {str(last_error)}")


def invoke_model(
    bedrock_client,
    model_id: str,
    prompt: str,
    max_tokens: int = 1000
) -> Dict:
    """
    Invoke Bedrock foundation model
    
    Args:
        bedrock_client: Boto3 Bedrock client
        model_id: Model ID
        prompt: Prompt text
        max_tokens: Maximum tokens
        
    Returns:
        Bedrock API response
    """
    # Build request body based on model provider
    if "anthropic.claude" in model_id:
        # Claude format
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": max_tokens,
            "temperature": 0.7
        }
    elif "amazon.nova" in model_id:
        # Nova format
        body = {
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": prompt}]
                }
            ],
            "inferenceConfig": {
                "maxTokens": max_tokens,
                "temperature": 0.7
            }
        }
    elif "cohere" in model_id:
        # Cohere format
        body = {
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": 0.7
        }
    else:
        raise ValueError(f"Unsupported model ID: {model_id}")
    
    # Invoke model
    response = bedrock_client.invoke_model(
        modelId=model_id,
        body=json.dumps(body),
        contentType='application/json',
        accept='application/json'
    )
    
    return response


def extract_text_from_response(response: Dict, model_id: str) -> str:
    """
    Extract generated text from Bedrock response
    
    Args:
        response: Bedrock API response
        model_id: Model ID to determine response format
        
    Returns:
        Generated text string
    """
    response_body = json.loads(response['body'].read())
    
    if "anthropic.claude" in model_id:
        # Claude response format
        return response_body['content'][0]['text']
    elif "amazon.nova" in model_id:
        # Nova response format
        return response_body['output']['message']['content'][0]['text']
    elif "cohere" in model_id:
        # Cohere response format
        return response_body['generations'][0]['text']
    else:
        raise ValueError(f"Unsupported model response format: {model_id}")


def parse_trends_from_text(trends_text: str) -> List[str]:
    """
    Parse trends from AI-generated text into list
    Handles both numbered (1. Title\nExplanation) and unnumbered (Title\nExplanation) formats
    
    Args:
        trends_text: Raw text with trends
        
    Returns:
        List of trend strings (each with title and explanation)
    """
    trends = []
    import re
    
    # Method 1: Try parsing with numbers (1., 2., 3., etc.)
    pattern = r'\d+\.\s+(.+?)(?=\d+\.\s+|\Z)'
    matches = re.findall(pattern, trends_text, re.DOTALL)
    
    for match in matches:
        trend = match.strip()
        if trend:
            trends.append(trend)
    
    # Method 2: If no numbered trends found, parse unnumbered format
    # Look for title patterns: short lines (2-5 words) followed by longer paragraphs
    if len(trends) < 3:
        # Split by double newlines or patterns that indicate new trends
        # Titles are typically short lines (less than 100 chars) followed by longer text
        sections = re.split(r'\n\n+', trends_text.strip())
        
        for section in sections:
            section = section.strip()
            if not section:
                continue
                
            # Check if this looks like a trend (has title + explanation)
            lines = section.split('\n')
            if len(lines) >= 2:
                # First line is likely the title, rest is explanation
                title = lines[0].strip()
                explanation = '\n'.join(lines[1:]).strip()
                
                # Validate: title should be relatively short (2-10 words)
                title_words = len(title.split())
                if 2 <= title_words <= 15 and len(explanation) > 20:
                    trend = f"{title}\n{explanation}"
                    trends.append(trend)
            elif len(section) > 50:  # Single paragraph trend
                trends.append(section)
    
    # Ensure we have 5 trends
    while len(trends) < 5:
        trends.append("Market trend analysis unavailable.")
    
    return trends[:5]  # Return exactly 5 trends


def get_token_count(text: str) -> int:
    """
    Estimate token count (rough approximation)
    
    Args:
        text: Text to count tokens for
        
    Returns:
        Estimated token count
    """
    # Rough estimate: 1 token ≈ 4 characters
    return len(text) // 4
