"""
AWS Bedrock Helper Module (V2).
Wrapper functions for invoking foundation models with retry logic.
V2: Brand proposal + product ideas generation (no scraper/KB).
"""

import json
import re
import time
import os
from typing import Dict, List, Any
import boto3
from botocore.exceptions import ClientError


# ----- V2 Prompts -----

GENERATE_BRAND_PROPOSAL = """You are a brand strategist. Based on REAL market data below, create ONE new brand concept that identifies gaps and opportunities in the current market.

L2 Category: {l2_category}

Market context (top 5 real products by revenue, last 30 days):
{market_context_text}

Instructions:
- Identify gaps or underserved segments in this market data.
- Create a NEW brand (name, tagline, story, values) that would differentiate from these existing leaders.
- Target a specific demographic and price positioning (mass-market | mid-range | premium | luxury).
- You MUST respond with ONLY valid JSON. No markdown, no code fences, no explanation.

Output exactly this JSON shape (no other fields):
{{"brand_name": "string", "brand_tagline": "string", "brand_story": "string", "brand_values": ["string", "string", "string"], "target_demographic": "string", "price_positioning": "string", "distribution_strategy": "string", "brand_personality": "string"}}"""


GENERATE_PRODUCT_IDEAS = """You are a product innovator. Based on REAL market data and the brand proposal below, create exactly 5 NEW product ideas for that brand. Products must be ORIGINAL concepts, not copies of the market context products.

L2 Category: {l2_category}

Market context (top 5 real products by revenue):
{market_context_text}

Brand proposal:
- Name: {brand_name}
- Tagline: {brand_tagline}
- Positioning: {price_positioning}
- Target: {target_demographic}
- Values: {brand_values}

Instructions:
- Each product must address a real gap or trend visible in the market data.
- For each product you MUST provide exactly 5 macro trends that are driving (or would drive) the success of that product in the market. Each trend has a short title and a full paragraph description (2-4 sentences) explaining how the trend connects to the product and to real consumer/sales behavior.
- supporting_trends_intro must be ONE paragraph (2-3 sentences) that introduces the 5 macro trends for that product. Use this exact style: "Here are 5 macro trends that are driving the success of [product name], and which have helped make it one of the most dominant [relevant subcategory or category] in the market:" (Adapt the wording if the product is new—e.g. "that would help position it" instead of "have helped make it".)
- supporting_trends must be an array of exactly 5 objects. Each object has "title" (short trend name, e.g. "The Mainstreaming of Collagen as a Wellness Staple") and "description" (one paragraph of 2-4 sentences with concrete, market-relevant explanation).
- image_prompt must describe a photorealistic product shot (packaging, colors, style, setting) suitable for AI image generation.
- You MUST respond with ONLY valid JSON. No markdown, no code fences.

Output exactly this JSON shape:
{{"products": [
  {{
    "product_name": "string",
    "description": "string",
    "estimated_price_usd": 29.99,
    "why_it_would_sell": "string",
    "key_ingredients": ["s1", "s2"],
    "supporting_trends_intro": "Here are 5 macro trends that are driving the success of [this product], and which have helped make it one of the most dominant [subcategory] in the market:",
    "supporting_trends": [
      {{"title": "Short Trend Title", "description": "Full paragraph explaining this trend and how it connects to the product and market."}},
      ... exactly 5 items
    ],
    "competitive_advantage": "string",
    "image_prompt": "string"
  }}
]}}
Exactly 5 objects in the "products" array. Each product must have supporting_trends_intro and exactly 5 supporting_trends with title and description."""


# Template to refine image_prompt before sending to Titan Image Generator (used in image_generator.py)
TITAN_IMAGE_PROMPT_TEMPLATE = """Professional product photography of {product_name} by {brand_name}.
{image_prompt_from_llm}
Clean white/gradient background, studio lighting, high-end beauty product packaging, commercial photography style, 4K quality."""


def _format_market_context(market_context: List[Dict[str, Any]]) -> str:
    """Format market context list for prompt injection."""
    lines = []
    for i, p in enumerate(market_context, 1):
        name = p.get("product_name") or p.get("product_name_curated") or "Unknown"
        shop = p.get("shop_name") or ""
        rev = p.get("revenue_usd", 0)
        growth = p.get("mom_growth_pct", 0)
        sold = p.get("item_sold", 0)
        lines.append(f"{i}. {name} | Shop: {shop} | Revenue: ${rev:,.0f} | Growth: {growth}% | Items sold: {sold:,}")
    return "\n".join(lines) if lines else "No data"


def _strip_json_fences(text: str) -> str:
    """Remove markdown code fences from model output."""
    if not text or not isinstance(text, str):
        return ""
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t)
        t = re.sub(r"\s*```\s*$", "", t)
        return t.strip()
    return t


def _normalize_product_idea_trends(p: Dict[str, Any], default_trend: Dict[str, str]) -> Dict[str, Any]:
    """Ensure product has supporting_trends_intro and supporting_trends as list of {title, description} (5 items)."""
    out = dict(p)
    intro = out.get("supporting_trends_intro")
    if not isinstance(intro, str):
        intro = ""
    out["supporting_trends_intro"] = intro
    raw = out.get("supporting_trends")
    if isinstance(raw, list) and len(raw) > 0 and isinstance(raw[0], dict):
        trends = []
        for i, t in enumerate(raw[:5]):
            if isinstance(t, dict):
                trends.append({
                    "title": str(t.get("title") or "").strip(),
                    "description": str(t.get("description") or "").strip(),
                })
            else:
                trends.append(dict(default_trend))
        while len(trends) < 5:
            trends.append(dict(default_trend))
        out["supporting_trends"] = trends[:5]
    elif isinstance(raw, list) and len(raw) > 0:
        # Old format: list of strings ("Title: explanation" or plain explanation)
        trends = []
        for s in raw[:5]:
            s = str(s).strip()
            if ":" in s and len(s.split(":", 1)[0]) < 80:
                title, _, desc = s.partition(":")
                trends.append({"title": title.strip(), "description": desc.strip() or title.strip()})
            else:
                trends.append({"title": "", "description": s})
        while len(trends) < 5:
            trends.append(dict(default_trend))
        out["supporting_trends"] = trends[:5]
    else:
        out["supporting_trends"] = [dict(default_trend) for _ in range(5)]
    return out


def generate_brand_proposal(
    market_context: List[Dict[str, Any]],
    l2_category: str,
    bedrock_client,
    model_id: str,
) -> Dict[str, Any]:
    """
    Generate a brand proposal from market context. Single Bedrock call.
    Returns dict with brand_name, brand_tagline, brand_story, brand_values, etc.
    On JSON parse failure, returns a sensible default with brand_name derived from category.
    """
    market_context_text = _format_market_context(market_context)
    prompt = GENERATE_BRAND_PROPOSAL.format(
        l2_category=l2_category or "Beauty",
        market_context_text=market_context_text,
    )
    try:
        response = invoke_model_with_retry(
            bedrock_client=bedrock_client,
            model_id=model_id,
            prompt=prompt,
            max_tokens=1500,
        )
        text = extract_text_from_response(response, model_id)
        text = _strip_json_fences(text)
        data = json.loads(text)
        if isinstance(data, dict):
            # Ensure required keys exist
            default_name = (l2_category or "Beauty").replace(" ", "") + "Brand"
            return {
                "brand_name": data.get("brand_name") or default_name,
                "brand_tagline": data.get("brand_tagline") or "",
                "brand_story": data.get("brand_story") or "",
                "brand_values": data.get("brand_values") if isinstance(data.get("brand_values"), list) else [],
                "target_demographic": data.get("target_demographic") or "",
                "price_positioning": data.get("price_positioning") or "mid-range",
                "distribution_strategy": data.get("distribution_strategy") or "",
                "brand_personality": data.get("brand_personality") or "",
            }
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"Brand proposal JSON parse failed: {e}")
    default_name = (l2_category or "Beauty").replace(" ", "") + "Brand"
    return {
        "brand_name": default_name,
        "brand_tagline": "",
        "brand_story": "",
        "brand_values": [],
        "target_demographic": "",
        "price_positioning": "mid-range",
        "distribution_strategy": "",
        "brand_personality": "",
    }


def generate_product_ideas(
    market_context: List[Dict[str, Any]],
    brand_proposal: Dict[str, Any],
    l2_category: str,
    bedrock_client,
    model_id: str,
) -> List[Dict[str, Any]]:
    """
    Generate 5 product ideas from market context + brand proposal. Single Bedrock call.
    Returns list of 5 product dicts. Pads with defaults if fewer than 5 returned.
    """
    market_context_text = _format_market_context(market_context)
    brand_name = brand_proposal.get("brand_name") or ""
    brand_tagline = brand_proposal.get("brand_tagline") or ""
    price_positioning = brand_proposal.get("price_positioning") or ""
    target_demographic = brand_proposal.get("target_demographic") or ""
    brand_values = brand_proposal.get("brand_values") or []
    brand_values_str = ", ".join(brand_values) if isinstance(brand_values, list) else str(brand_values)

    prompt = GENERATE_PRODUCT_IDEAS.format(
        l2_category=l2_category or "Beauty",
        market_context_text=market_context_text,
        brand_name=brand_name,
        brand_tagline=brand_tagline,
        price_positioning=price_positioning,
        target_demographic=target_demographic,
        brand_values=brand_values_str,
    )
    try:
        response = invoke_model_with_retry(
            bedrock_client=bedrock_client,
            model_id=model_id,
            prompt=prompt,
            max_tokens=4000,
        )
        text = extract_text_from_response(response, model_id)
        text = _strip_json_fences(text)
        data = json.loads(text)
        products = data.get("products")
        if not isinstance(products, list):
            products = []
        default_trend = {"title": "", "description": ""}
        default_product = {
            "product_name": "Concept Product",
            "description": "",
            "estimated_price_usd": 0,
            "why_it_would_sell": "",
            "key_ingredients": [],
            "supporting_trends_intro": "",
            "supporting_trends": [dict(default_trend) for _ in range(5)],
            "competitive_advantage": "",
            "image_prompt": "Product bottle or package, clean background",
        }
        out = []
        for p in products[:5]:
            normalized = _normalize_product_idea_trends(p, default_trend)
            out.append(normalized)
        while len(out) < 5:
            out.append(default_product.copy())
        return out[:5]
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"Product ideas JSON parse failed: {e}")
        default_trend = {"title": "", "description": ""}
        return [
            {
                "product_name": "Concept Product",
                "description": "",
                "estimated_price_usd": 0,
                "why_it_would_sell": "",
                "key_ingredients": [],
                "supporting_trends_intro": "",
                "supporting_trends": [dict(default_trend) for _ in range(5)],
                "competitive_advantage": "",
                "image_prompt": "Product bottle or package, clean background",
            }
            for _ in range(5)
        ]


def invoke_model_with_retry(
    bedrock_client,
    model_id: str,
    prompt: str,
    max_tokens: int = 1000,
    retries: int = 3,
) -> Dict:
    """
    Invoke Bedrock model with exponential backoff retry.
    """
    last_error = None
    current_model_id = model_id
    for attempt in range(retries):
        try:
            return invoke_model(bedrock_client, current_model_id, prompt, max_tokens)
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            last_error = e
            if error_code == "ThrottlingException":
                wait_time = (2**attempt) + (time.time() % 1)
                print(f"Bedrock throttled, retrying in {wait_time:.2f}s (attempt {attempt + 1}/{retries})")
                time.sleep(wait_time)
                if attempt == retries - 1 and current_model_id != os.environ.get("BEDROCK_FALLBACK_MODEL"):
                    fallback = os.environ.get("BEDROCK_FALLBACK_MODEL")
                    if fallback:
                        print(f"Switching to fallback model: {fallback}")
                        current_model_id = fallback
            else:
                raise
    raise Exception(f"Bedrock invocation failed after {retries} attempts: {str(last_error)}")


def invoke_model(
    bedrock_client,
    model_id: str,
    prompt: str,
    max_tokens: int = 1000,
) -> Dict:
    """Invoke Bedrock foundation model (Claude, Nova, Cohere)."""
    if "anthropic.claude" in model_id:
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.7,
        }
    elif "amazon.nova" in model_id:
        body = {
            "messages": [{"role": "user", "content": [{"text": prompt}]}],
            "inferenceConfig": {"maxTokens": max_tokens, "temperature": 0.7},
        }
    elif "cohere" in model_id:
        body = {"prompt": prompt, "max_tokens": max_tokens, "temperature": 0.7}
    else:
        raise ValueError(f"Unsupported model ID: {model_id}")

    response = bedrock_client.invoke_model(
        modelId=model_id,
        body=json.dumps(body),
        contentType="application/json",
        accept="application/json",
    )
    return response


def extract_text_from_response(response: Dict, model_id: str) -> str:
    """Extract generated text from Bedrock response."""
    response_body = json.loads(response["body"].read())
    if "anthropic.claude" in model_id:
        return response_body["content"][0]["text"]
    if "amazon.nova" in model_id:
        return response_body["output"]["message"]["content"][0]["text"]
    if "cohere" in model_id:
        return response_body["generations"][0]["text"]
    raise ValueError(f"Unsupported model response format: {model_id}")


def parse_trends_from_text(trends_text: str) -> List[str]:
    """Parse trends from AI-generated text into list. Kept for compatibility."""
    trends = []
    pattern = r"\d+\.\s+(.+?)(?=\d+\.\s+|\Z)"
    matches = re.findall(pattern, trends_text or "", re.DOTALL)
    for match in matches:
        trend = match.strip()
        if trend:
            trends.append(trend)
    if len(trends) < 3:
        sections = re.split(r"\n\n+", (trends_text or "").strip())
        for section in sections:
            section = section.strip()
            if not section:
                continue
            lines = section.split("\n")
            if len(lines) >= 2:
                title = lines[0].strip()
                explanation = "\n".join(lines[1:]).strip()
                if 2 <= len(title.split()) <= 15 and len(explanation) > 20:
                    trends.append(f"{title}\n{explanation}")
            elif len(section) > 50:
                trends.append(section)
    while len(trends) < 5:
        trends.append("Market trend analysis unavailable.")
    return trends[:5]


def get_token_count(text: str) -> int:
    """Estimate token count (rough approximation)."""
    return len(text) // 4
