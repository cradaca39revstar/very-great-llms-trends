"""
AWS Bedrock Helper Module (V2).
Wrapper functions for invoking foundation models with retry logic.
V2: Brand proposal + product ideas generation (no scraper/KB).
"""

import json
import re
import time
import os
from typing import Dict, List, Any, Optional
import boto3
from botocore.exceptions import ClientError


# ----- V2 Prompts -----

GENERATE_BRAND_PROPOSAL = """You are a brand strategist. Based on REAL market data below, create ONE new brand concept.

L2 Category: {l2_category}

Market context (top real products by revenue, last 30 days):
{market_context_text}
{web_insights_section}

The brand concept should be inspired by the #1 top product ("{top_product_name}"), but DO NOT copy it. Identify what makes it successful (audience, positioning, ingredients, format) and create something that DIFFERENTIATES from it — a fresh angle, new format, underserved niche, or innovative approach.

Instructions:
- Create a NEW brand (name, tagline, story, values) that captures an adjacent market opportunity.
- The brand_story should explain how the brand fills a gap the top product does not cover. Do NOT mention the top product by name in the story.
- Target a specific demographic and price positioning (mass-market | mid-range | premium | luxury).
- You MUST respond with ONLY valid JSON. No markdown, no code fences, no explanation.

Output exactly this JSON shape (no other fields):
{{"brand_name": "string", "brand_tagline": "string", "brand_story": "string", "brand_values": ["string", "string", "string"], "target_demographic": "string", "price_positioning": "string", "distribution_strategy": "string", "brand_personality": "string"}}"""


# Report delivers 1 product concept based on brand + top product (client requirement)
PRODUCT_IDEAS_COUNT = 1

GENERATE_PRODUCT_IDEAS = """You are a product innovator. Based on REAL market data and the brand proposal below, create exactly 1 proposed product concept for that brand.

L2 Category: {l2_category}

Market context (top real products by revenue):
{market_context_text}
{web_insights_section}

Brand proposal:
- Name: {brand_name}
- Tagline: {brand_tagline}
- Positioning: {price_positioning}
- Target: {target_demographic}
- Values: {brand_values}

The product concept is inspired by the #1 top product ("{top_product_name}"), but it MUST BE DIFFERENT. Do NOT replicate the same formula, format, or name. Instead, create something that:
- Addresses a gap or limitation of the top product (e.g. different format, new ingredient combination, different use case, complementary product).
- Has its own unique identity and value proposition.
- Do NOT mention the top product by name in the description or why_it_would_sell.

Instructions:
- Create ONE innovative product concept that feels like a natural fit for the brand.
- Provide exactly 5 macro trends (supporting_trends_intro + supporting_trends array of 5 objects with "title" and "description").
- image_prompt must describe a photorealistic product shot: packaging shape, colors, materials, and style that appeal to the target demographic ({target_demographic}). Focus on visual elements only (no text instructions). Clean studio background.
- You MUST respond with ONLY valid JSON. No markdown, no code fences.

Output exactly this JSON shape:
{{"products": [
  {{
    "product_name": "string",
    "description": "string",
    "estimated_price_usd": 29.99,
    "why_it_would_sell": "string",
    "key_ingredients": ["s1", "s2"],
    "supporting_trends_intro": "Here are 5 macro trends that are driving the success of this product...",
    "supporting_trends": [
      {{"title": "Short Trend Title", "description": "Full paragraph."}},
      ... exactly 5 items
    ],
    "competitive_advantage": "string",
    "image_prompt": "string"
  }}
]}}
Exactly 1 object in the "products" array. The product must have supporting_trends_intro and exactly 5 supporting_trends with title and description."""


# Template to refine image_prompt before sending to Titan Image Generator (used in image_generator.py)
# Note: Titan V2 cannot render readable text on images; keep prompt focused on visual/photographic style.
TITAN_IMAGE_PROMPT_TEMPLATE = """Professional product photography of {product_name} by {brand_name}.
{image_prompt_from_llm}
Clean white studio background, soft studio lighting, high-end beauty product packaging, commercial photography style, 4K quality."""


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


def _format_web_insights(web_insights: Optional[Dict[str, Any]]) -> str:
    """Format web search results for prompt injection. Returns empty string if no insights."""
    if not web_insights:
        return ""
    trends = web_insights.get("trends") or []
    pain_points = web_insights.get("pain_points") or []
    competitors = web_insights.get("competitors") or []
    if not trends and not pain_points and not competitors:
        return ""
    lines = ["Web search insights (trends, pain points, competitors):"]
    for label, items in [("Trends", trends), ("Pain points", pain_points), ("Competitors", competitors)]:
        if items:
            parts = []
            for x in items[:3]:
                if isinstance(x, dict):
                    title = (x.get("title") or "").strip()
                    snippet = (x.get("snippet") or "").strip()[:120]
                    parts.append(title or snippet or "")
                elif isinstance(x, str):
                    parts.append(x[:120])
            if parts:
                lines.append(f"- {label}: " + " | ".join(parts))
    if len(lines) <= 1:
        return ""
    return "\n".join(lines) + "\n\n"


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
    web_insights: Optional[Dict[str, Any]] = None,
    top_product_name: str = "",
) -> Dict[str, Any]:
    """
    Generate a brand proposal from market context. Single Bedrock call.
    Optional web_insights (Brave search results) are injected into the prompt when provided.
    top_product_name: name of the #1 Athena product (injected by backend, not LLM-dependent).
    Returns dict with brand_name, brand_tagline, brand_story, brand_values, etc.
    On JSON parse failure, returns a sensible default with brand_name derived from category.
    """
    market_context_text = _format_market_context(market_context)
    web_insights_section = _format_web_insights(web_insights) if web_insights else ""
    # Resolve top product name: use explicit param or fallback to first item in market_context
    if not top_product_name and market_context:
        top_product_name = market_context[0].get("product_name") or "top product"
    prompt = GENERATE_BRAND_PROPOSAL.format(
        l2_category=l2_category or "Beauty",
        market_context_text=market_context_text,
        web_insights_section=web_insights_section,
        top_product_name=top_product_name,
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
    web_insights: Optional[Dict[str, Any]] = None,
    top_product_name: str = "",
) -> List[Dict[str, Any]]:
    """
    Generate 1 product concept from market context + brand proposal. Single Bedrock call.
    top_product_name: name of the #1 Athena product (injected by backend).
    Optional web_insights (Brave search results) are injected into the prompt when provided.
    Returns list of product dicts. Pads with defaults if fewer than expected.
    """
    market_context_text = _format_market_context(market_context)
    web_insights_section = _format_web_insights(web_insights) if web_insights else ""
    brand_name = brand_proposal.get("brand_name") or ""
    brand_tagline = brand_proposal.get("brand_tagline") or ""
    price_positioning = brand_proposal.get("price_positioning") or ""
    target_demographic = brand_proposal.get("target_demographic") or ""
    brand_values = brand_proposal.get("brand_values") or []
    brand_values_str = ", ".join(brand_values) if isinstance(brand_values, list) else str(brand_values)
    # Resolve top product name: use explicit param or fallback to first item in market_context
    if not top_product_name and market_context:
        top_product_name = market_context[0].get("product_name") or "top product"

    prompt = GENERATE_PRODUCT_IDEAS.format(
        l2_category=l2_category or "Beauty",
        market_context_text=market_context_text,
        web_insights_section=web_insights_section,
        brand_name=brand_name,
        brand_tagline=brand_tagline,
        price_positioning=price_positioning,
        target_demographic=target_demographic,
        brand_values=brand_values_str,
        top_product_name=top_product_name,
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
        for p in products[:PRODUCT_IDEAS_COUNT]:
            normalized = _normalize_product_idea_trends(p, default_trend)
            out.append(normalized)
        while len(out) < PRODUCT_IDEAS_COUNT:
            out.append(default_product.copy())
        return out[:PRODUCT_IDEAS_COUNT]
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
            for _ in range(PRODUCT_IDEAS_COUNT)
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
