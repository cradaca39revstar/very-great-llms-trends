"""
Web Product Scraper Lambda (internal, invoked by orchestrator only).
Fetches a product page and extracts url, image_url, trends_text, optional description.
If candidate_url is empty, optionally calls Bedrock to suggest a URL first.
"""

import json
import os
import random
import re
import time
from typing import Dict, Any
import urllib.parse

# #region agent log
def _debug_log_scraper(location: str, message: str, data: Dict[str, Any], hypothesis_id: str = "") -> None:
    try:
        payload = {"location": location, "message": message, "data": data, "timestamp": int(time.time() * 1000), "sessionId": "debug-session", "hypothesisId": hypothesis_id}
        _dp = os.environ.get("DEBUG_LOG_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".cursor", "debug.log"))
        with open(_dp, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload) + "\n")
        print(f"[DEBUG] {json.dumps(payload)}")
    except Exception:
        pass
# #endregion

import boto3  # type: ignore[import-untyped]
import requests  # type: ignore[import-untyped]
from bs4 import BeautifulSoup  # type: ignore[import-untyped]

AWS_REGION = os.environ.get("AWS_REGION_NAME", "us-east-1")
BEDROCK_MODEL = os.environ.get("BEDROCK_PRIMARY_MODEL", "anthropic.claude-3-5-sonnet-v2:0")
REQUEST_TIMEOUT = 10
MAX_BODY_SNIPPET = 2000
# Small delay before second request (search -> product page) to reduce bot detection
REQUEST_DELAY_SEC = 1.5

# Real browser User-Agents (Chrome on Windows) to reduce 503 / bot detection
_BROWSER_USER_AGENTS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
)


def _browser_headers(referer: str | None = None) -> Dict[str, str]:
    """Return headers that mimic a real browser to reduce bot detection (503)."""
    headers = {
        "User-Agent": random.choice(_BROWSER_USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none" if not referer else "cross-site",
        "Sec-Fetch-User": "?1",
        "Connection": "keep-alive",
    }
    if referer:
        headers["Referer"] = referer
    return headers


# Supported search domains (we can parse product links from these). Add more as needed.
SUPPORTED_SEARCH_DOMAINS = (
    "amazon.com",
    "sephora.com",
    "walmart.com",
    "ulta.com",
    "target.com",
)

# Prompt: return ONE search URL from any major retailer (examples). One line only.
URL_SUGGEST_PROMPT = """You are a precise assistant. Respond with exactly ONE line: a search results page URL. No other text.

Product to search: Brand "{brand_name}" - {product_name}

Return ONE of these search URLs (use the encoded query below). Choose any one retailer:
- Amazon: https://www.amazon.com/s?k={encoded_query}
- Sephora: https://www.sephora.com/search?keyword={encoded_query}
- Walmart: https://www.walmart.com/search?q={encoded_query}
- Ulta: https://www.ulta.com/shop/search?query={encoded_query}
- Target: https://www.target.com/s?searchTerm={encoded_query}

Output only the single URL, nothing else."""


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
        candidate_url = _build_fallback_search_url(brand_name, product_name)
    if not candidate_url:
        return result

    headers = _browser_headers()
    resp = None
    try:
        resp = requests.get(
            candidate_url,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
            headers=headers,
        )
        resp.raise_for_status()
    except (requests.RequestException, requests.Timeout) as e:
        print(f"Scraper fetch failed (will try search fallback): {e}")
        candidate_url = _build_fallback_search_url(brand_name, product_name)
        if candidate_url:
            try:
                headers = _browser_headers(referer="https://www.google.com/")
                resp = requests.get(candidate_url, timeout=REQUEST_TIMEOUT, allow_redirects=True, headers=headers)
                resp.raise_for_status()
            except (requests.RequestException, requests.Timeout) as e2:
                print(f"Scraper search fallback failed: {e2}")
                # #region agent log
                try:
                    _debug_log_scraper("scraper:search_fallback_failed", "returning empty after 503", {"brand_name": brand_name, "product_name_preview": (product_name or "")[:40], "candidate_url_preview": (candidate_url or "")[:60]}, "H5")
                except Exception:
                    pass
                # #endregion
                return result
        else:
            return result

    try:
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        print(f"Scraper parse failed: {e}")
        return result

    final_url = resp.url
    # If this is a search page, extract first product link and optionally fetch product page for image/description
    if _is_search_url(final_url):
        product_url = _extract_first_product_url_from_search(soup, final_url)
        if product_url:
            time.sleep(REQUEST_DELAY_SEC)
            try:
                prod_headers = _browser_headers(referer=final_url)
                prod_resp = requests.get(product_url, timeout=REQUEST_TIMEOUT, allow_redirects=True, headers=prod_headers)
                prod_resp.raise_for_status()
                final_url = prod_resp.url
                soup = BeautifulSoup(prod_resp.text, "html.parser")
            except (requests.RequestException, requests.Timeout):
                # Keep search page url and first result image if any
                final_url = product_url
    result["url"] = final_url

    image_url = _extract_image_url(soup, final_url)
    if image_url:
        result["image_url"] = image_url

    desc = _extract_description(soup)
    if desc:
        result["description"] = desc[:500]

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
        raw = (text or "").strip()
        url = _extract_url_from_model_response(raw)
        if url and _is_supported_search_url(url):
            return url
    except Exception as e:
        print(f"Bedrock URL suggest failed: {e}")
    return ""


def _extract_url_from_model_response(text: str) -> str:
    """Extract the first valid http(s) URL from model output (avoids extra text breaking the request)."""
    if not text:
        return ""
    # First line that looks like a URL
    for line in text.splitlines():
        line = line.strip()
        if line.startswith(("http://", "https://")):
            # Trim trailing punctuation or parentheses
            match = re.match(r"(https?://[^\s\)\]\>]+)", line)
            if match:
                return match.group(1).rstrip(".,;:)")
            return line.rstrip(".,;:)")
    # Or first URL-like substring anywhere
    match = re.search(r"(https?://[^\s\)\]\>]+)", text)
    if match:
        return match.group(1).rstrip(".,;:)")
    return ""


def _is_supported_search_url(url: str) -> bool:
    """True if URL is a search page from a supported retailer we can parse."""
    if not url:
        return False
    u = url.lower()
    return any(domain in u for domain in SUPPORTED_SEARCH_DOMAINS)


def _build_fallback_search_url(brand_name: str, product_name: str) -> str:
    """Build a stable search URL (Amazon first; always exists). No Bedrock needed."""
    query = f"{brand_name} {product_name}".strip()
    if not query:
        return ""
    encoded = urllib.parse.quote(query)
    return f"https://www.amazon.com/s?k={encoded}"


def _is_search_url(url: str) -> bool:
    """True if URL looks like a search/results page, not a direct product page."""
    if not url:
        return False
    u = url.lower().split("?")[0]
    if "amazon.com/s" in u or "amazon.com/gp/search" in u:
        return True
    if "sephora.com/search" in u:
        return True
    if "walmart.com/search" in u or "walmart.com/ip" not in u and "walmart.com" in u and "search" in url.lower():
        return True
    return False


def _extract_first_product_url_from_search(soup: BeautifulSoup, page_url: str) -> str:
    """Extract first product link from Amazon or Sephora search results page."""
    if not page_url:
        return ""
    page_url_lower = page_url.lower()
    # Amazon: product links contain /dp/ or /gp/product/
    if "amazon.com" in page_url_lower:
        for a in soup.find_all("a", href=True):
            href = (a.get("href") or "").strip()
            if not href or href.startswith("#"):
                continue
            if "/dp/" in href or "/gp/product/" in href:
                # Clean query params to get canonical product URL
                if href.startswith("/"):
                    href = "https://www.amazon.com" + href.split("?")[0]
                else:
                    href = href.split("?")[0]
                if "amazon.com" in href:
                    return href
    # Sephora: product links contain /product/
    if "sephora.com" in page_url_lower:
        for a in soup.find_all("a", href=True):
            href = (a.get("href") or "").strip()
            if "/product/" in href and "sephora.com" in href.lower():
                if href.startswith("/"):
                    href = "https://www.sephora.com" + href.split("?")[0]
                else:
                    href = href.split("?")[0]
                return href
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
