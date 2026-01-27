"""
AWS Bedrock Helper Module
Wrapper functions for invoking foundation models with retry logic
"""

import json
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

PRODUCT_SEARCH_PROMPT = """Based on the following product information, generate a product description and provide the official brand website URL.

Brand: {brand_name}
Product: {product_name}
Category: {l2_category}

Provide:
1. Official website URL (if known, or best estimate)
2. Product description (2-3 sentences describing the product, its benefits, and key ingredients/features)

Format your response as JSON:
{{
  "url": "https://www.example.com/product-page",
  "description": "Product description here...",
  "image_url": "https://www.example.com/image.jpg"
}}

If you don't know the exact URL, provide the brand's main website or a reasonable estimate."""


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
        product_data: Dict with product information
        bedrock_client: Boto3 Bedrock client
        model_id: Bedrock model ID to use
        
    Returns:
        List of 5 trend strings with titles and explanations
    """
    prompt = TRENDS_PROMPT.format(
        product_name=product_data.get('product_name', ''),
        brand_name=product_data.get('brand_name', ''),
        l2_category=product_data.get('l2_category', ''),
        mom_growth_pct=product_data.get('mom_growth_pct', 0),
        revenue_usd=product_data.get('revenue_usd', 0),
        item_sold=product_data.get('item_sold', 0)
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


def search_product_info_via_bedrock(
    brand_name: str,
    product_name: str,
    bedrock_client,
    model_id: str
) -> Dict:
    """
    Search for product information using Bedrock
    (In production, this could use Bedrock Knowledge Bases with web search)
    
    Args:
        brand_name: Brand name
        product_name: Product name
        bedrock_client: Boto3 Bedrock client
        model_id: Bedrock model ID to use
        
    Returns:
        Dict with url, description, image_url
    """
    prompt = PRODUCT_SEARCH_PROMPT.format(
        brand_name=brand_name,
        product_name=product_name,
        l2_category="beauty product"
    )
    
    try:
        response = invoke_model_with_retry(
            bedrock_client=bedrock_client,
            model_id=model_id,
            prompt=prompt,
            max_tokens=500
        )
        
        response_text = extract_text_from_response(response, model_id)
        
        # Try to parse as JSON
        try:
            product_info = json.loads(response_text)
            return product_info
        except json.JSONDecodeError:
            # Fallback: extract info from text
            return {
                'url': f"https://www.{brand_name.lower().replace(' ', '')}.com",
                'description': response_text[:200],
                'image_url': ''
            }
    except Exception as e:
        print(f"Product search failed: {str(e)}")
        # Return default values
        return {
            'url': '',
            'description': f"A trending {product_name} product.",
            'image_url': ''
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
