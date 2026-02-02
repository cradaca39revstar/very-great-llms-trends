"""
Web Product Scraper Lambda (internal, invoked by orchestrator only).
Fetches a product page and extracts url, image_url, trends_text, optional description.
If candidate_url is empty, optionally calls Bedrock to suggest a URL first.
"""

import json
import os
import re
from typing import Dict, Any
import urllib.parse

import boto3
import requests
from bs4 import BeautifulSoup

AWS_REGION = os.environ.get("AWS_REGION_NAME", "us-east-1")
BEDROCK_MODEL = os.environ.get("BEDROCK_PRIMARY_MODEL", "anthropic.claude-3-5-sonnet-v2:0")
REQUEST_TIMEOUT = 10
MAX_BODY_SNIPPET = 2000

# Prompt for Bedrock to suggest a product URL when candidate_url is empty
URL_SUGGEST_PROMPT = """You are a precise assistant. Respond ONLY with a single valid product page URL, nothing else.

Given this product, suggest ONE best product page URL:
Brand: {brand_name}
Product: {product_name}
Category: {l2_category}

Prefer: official brand site, then Amazon/Sephora/Ulta/Walmart/Target. If unsure, use a search URL like https://www.amazon.com/s?k={encoded_query}
Output only the URL, no explanation."""


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Payload: brand_name, product_name, l2_category, candidate_url (optional).
    Returns: url, image_url, trends_text, description (optional).
    On failure returns empty strings so orchestrator can fall back to LLM.
    """
    try:
        body = event if isinstance(event, dict) else json.loads(event)
    except (TypeError, json.JSONDecodeError):
        body = {}

    brand_name = (body.get("brand_name") or "").strip()
    product_name = (body.get("product_name") or "").strip()
    l2_category = (body.get("l2_category") or "").strip() or "beauty product"
    candidate_url = (body.get("candidate_url") or "").strip()

    result = {
        "url": "",
        "image_url": "",
        "trends_text": "",
        "description": "",
    }

    if not candidate_url and (brand_name or product_name):
        candidate_url = _get_candidate_url_from_bedrock(
            brand_name=brand_name,
            product_name=product_name,
            l2_category=l2_category,
        )

    if not candidate_url or not candidate_url.startswith(("http://", "https://")):
        return result

    try:
        resp = requests.get(
            candidate_url,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; BeautyProductsScraper/1.0)"},
        )
        resp.raise_for_status()
    except (requests.RequestException, requests.Timeout) as e:
        print(f"Scraper fetch failed: {e}")
        return result

    final_url = resp.url
    result["url"] = final_url

    try:
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        print(f"Scraper parse failed: {e}")
        return result

    # Prefer og:image, then first large img in main/product container
    image_url = _extract_image_url(soup, final_url)
    if image_url:
        result["image_url"] = image_url

    # Meta description or first paragraph
    desc = _extract_description(soup)
    if desc:
        result["description"] = desc[:500]

    # Optional trends snippet: section with "trending"/"popular" or first N chars of body
    trends_text = _extract_trends_snippet(soup)
    if trends_text:
        result["trends_text"] = trends_text[:MAX_BODY_SNIPPET]

    return result


def _get_candidate_url_from_bedrock(
    brand_name: str,
    product_name: str,
    l2_category: str,
) -> str:
    """Call Bedrock once to suggest a product URL. Returns empty string on failure.
    Supports Claude, Nova, and Cohere via model_id (BEDROCK_PRIMARY_MODEL).
    """
    try:
        client = boto3.client("bedrock-runtime", region_name=AWS_REGION)
        model_id = BEDROCK_MODEL
        encoded_query = urllib.parse.quote(f"{brand_name} {product_name}")
        prompt = URL_SUGGEST_PROMPT.format(
            brand_name=brand_name,
            product_name=product_name,
            l2_category=l2_category,
            encoded_query=encoded_query,
        )
        # Build request body by model provider (same logic as bedrock_helper.invoke_model)
        if "anthropic.claude" in model_id:
            req_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 200,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
            }
        elif "amazon.nova" in model_id:
            req_body = {
                "messages": [
                    {"role": "user", "content": [{"text": prompt}]}
                ],
                "inferenceConfig": {"maxTokens": 200, "temperature": 0.7},
            }
        elif "cohere" in model_id:
            req_body = {
                "prompt": prompt,
                "max_tokens": 200,
                "temperature": 0.7,
            }
        else:
            # Default: Nova-style for unknown Amazon/other models
            req_body = {
                "messages": [
                    {"role": "user", "content": [{"text": prompt}]}
                ],
                "inferenceConfig": {"maxTokens": 200, "temperature": 0.7},
            }
        response = client.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(req_body),
        )
        resp_body = json.loads(response["body"].read())
        # Parse response by model provider (same logic as bedrock_helper.extract_text_from_response)
        if "anthropic.claude" in model_id:
            text = ""
            for block in resp_body.get("content", []):
                if block.get("type") == "text":
                    text += block.get("text", "")
        elif "amazon.nova" in model_id:
            msg = (resp_body.get("output") or {}).get("message") or {}
            parts = msg.get("content") or []
            text = parts[0].get("text", "") if parts else ""
        elif "cohere" in model_id:
            gens = resp_body.get("generations") or [{}]
            text = gens[0].get("text", "") if gens else ""
        else:
            msg = (resp_body.get("output") or {}).get("message") or {}
            parts = msg.get("content") or []
            text = parts[0].get("text", "") if parts else ""
        url = (text or "").strip()
        if url and url.startswith(("http://", "https://")):
            return url
    except Exception as e:
        print(f"Bedrock URL suggest failed: {e}")
    return ""


def _extract_image_url(soup: BeautifulSoup, base_url: str) -> str:
    """Extract product image URL: og:image first, then first suitable img."""
    # og:image
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        href = og["content"].strip()
        if href.startswith(("http://", "https://")):
            return href
        if href.startswith("//"):
            return "https:" + href
        try:
            return urllib.parse.urljoin(base_url, href)
        except Exception:
            pass

    # First img with product-like src (common CDN or product paths)
    for img in soup.find_all("img", src=True):
        src = (img.get("src") or "").strip()
        if not src or any(x in src.lower() for x in ["logo", "icon", "pixel", "1x1"]):
            continue
        if src.startswith(("http://", "https://")):
            return src
        if src.startswith("//"):
            return "https:" + src
        try:
            return urllib.parse.urljoin(base_url, src)
        except Exception:
            pass
    return ""


def _extract_description(soup: BeautifulSoup) -> str:
    """Meta description or first substantial paragraph."""
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        return meta["content"].strip()
    meta = soup.find("meta", property="og:description")
    if meta and meta.get("content"):
        return meta["content"].strip()
    for p in soup.find_all("p"):
        text = (p.get_text() or "").strip()
        if len(text) > 30:
            return text
    return ""


def _extract_trends_snippet(soup: BeautifulSoup) -> str:
    """Try to find a 'trending'/'popular' section, else first part of body text."""
    body = soup.find("body")
    if not body:
        return ""

    # Look for sections with trending/popular
    for tag in body.find_all(["section", "div"], class_=re.compile(r"trend|popular|insight", re.I)):
        text = (tag.get_text() or "").strip()
        if len(text) > 50:
            return text

    # Fallback: first N chars of body text
    text = (body.get_text() or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text
