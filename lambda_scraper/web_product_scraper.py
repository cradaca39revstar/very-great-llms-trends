"""
Web Product Scraper Lambda (invoked by orchestrator only).
Uses Brave Search API and Google Images only.

Rules:
- URL de la marca/producto: Brave Search API (obligatorio; requiere BRAVE_SEARCH_API_KEY).
- Primera imagen del producto: Google Images (búsqueda por marca + nombre producto).
- Opcional: si tenemos URL, hacemos fetch de la página para description y trends_text.

Returns: url (brand/product page), image_url, description, trends_text.
"""

import json
import os
import random
import re
import time
import urllib.parse
from typing import Any, Dict, List

import requests  # type: ignore[import-untyped]
from bs4 import BeautifulSoup  # type: ignore[import-untyped]

# --- Config ---
BRAVE_SEARCH_API_KEY = (os.environ.get("BRAVE_SEARCH_API_KEY") or "").strip()
REQUEST_TIMEOUT = 12
BRAVE_MAX_RESULTS = 10
REQUEST_DELAY_SEC = 1.0
MAX_BODY_SNIPPET = 2000

_BROWSER_USER_AGENTS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
)

# Scoring: product-page paths and supported retailers
PRODUCT_PAGE_PATH_PATTERNS = ("/dp/", "/gp/product/", "/product/", "/p/", "/ip/", "/products/")
SUPPORTED_SEARCH_DOMAINS = ("amazon.com", "sephora.com", "walmart.com", "ulta.com", "target.com")

# Image URLs from these domains often 404; skip when choosing from Google Images
_BLOCKED_IMAGE_DOMAINS = ("walmartimages.com", "i5.walmartimages.com", "i2.walmartimages.com")


def _browser_headers(referer: str | None = None) -> Dict[str, str]:
    headers = {
        "User-Agent": random.choice(_BROWSER_USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-User": "?1",
        "Connection": "keep-alive",
    }
    if referer:
        headers["Referer"] = referer
    return headers


# ---------- Brave Search API: URL de la marca/producto ----------


def _search_brave_api(query: str, max_results: int = BRAVE_MAX_RESULTS) -> List[Dict[str, str]]:
    """
    Brave Search API (web search). Returns list of {title, href, body}.
    On 429, retry once after 2s.
    """
    if not BRAVE_SEARCH_API_KEY or not query or not query.strip():
        return []
    url = "https://api.search.brave.com/res/v1/web/search"
    params = {"q": query.strip(), "count": min(max_results, 20), "country": "us", "search_lang": "en"}
    headers = {"Accept": "application/json", "Accept-Encoding": "gzip", "X-Subscription-Token": BRAVE_SEARCH_API_KEY}

    for attempt in range(2):
        try:
            if attempt > 0:
                time.sleep(2)
                print("Scraper: Brave API retry after 429...")
            resp = requests.get(url, params=params, headers=headers, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 429:
                if attempt == 0:
                    print("Scraper: Brave Search API 429; retrying in 2s...")
                    continue
                return []
            resp.raise_for_status()
            data = resp.json()
            out: List[Dict[str, str]] = []
            for r in (data.get("web") or {}).get("results") or []:
                href = (r.get("url") or "").strip()
                if not href or not href.startswith(("http://", "https://")):
                    continue
                out.append({
                    "title": (r.get("title") or "")[:300],
                    "href": href,
                    "body": (r.get("description") or "")[:500],
                })
            if out:
                print(f"Scraper: Brave API returned {len(out)} results for query={query[:50]}...")
            return out
        except Exception as e:
            print(f"Scraper: Brave Search API failed: {e}")
            return []
    return []


def _brand_domain_slugs(shop_or_brand: str) -> List[str]:
    """E.g. 'The Ordinary Store' -> ['theordinary', 'the-ordinary', 'terezandhonor']."""
    if not shop_or_brand or not shop_or_brand.strip():
        return []
    raw = (shop_or_brand or "").lower().strip()
    for suffix in (" store", " shop", " inc", " llc", " co", " company", " official"):
        if raw.endswith(suffix):
            raw = raw[: -len(suffix)].strip()
    no_spaces = re.sub(r"\s+", "", raw)
    with_hyphens = re.sub(r"\s+", "-", raw)
    no_spaces_no_amp = re.sub(r"[&\s]+", "", raw)
    slugs = []
    if no_spaces:
        slugs.append(no_spaces)
    if with_hyphens and with_hyphens not in slugs:
        slugs.append(with_hyphens)
    if no_spaces_no_amp and no_spaces_no_amp not in slugs:
        slugs.append(no_spaces_no_amp)
    first_word = raw.split()[0] if raw.split() else ""
    if first_word and first_word not in ("the", "a", "an") and first_word not in slugs:
        slugs.append(first_word)
    return slugs


def _url_host_slug(href: str) -> str:
    try:
        host = (urllib.parse.urlparse(href).netloc or "").lower().strip()
        if host.startswith("www."):
            host = host[4:]
        return host.split(".")[0] if host else ""
    except Exception:
        return ""


def _pick_best_result_url(
    results: List[Dict[str, str]],
    product_name: str,
    shop_or_brand: str,
) -> str:
    """
    Score results and return the best URL (official brand domain > product paths > retailers).
    Excludes review/aggregator sites.
    """
    if not results:
        return ""
    product_lower = (product_name or "").lower()
    shop_lower = (shop_or_brand or "").lower()
    brand_slugs = _brand_domain_slugs(shop_or_brand)
    review_domains = (
        "myprosandcons", "trustpilot", "yelp.com", "g2.com", "capterra", "sitejabber",
        "consumeraffairs", "reviews.io", "resellerratings", "wikipedia.org", "youtube.com",
        "facebook.com", "twitter.com", "instagram.com", "pinterest.com",
    )

    def score_item(item: Dict[str, Any]) -> int:
        href = (item.get("href") or item.get("url") or "").strip()
        title = (item.get("title") or "").lower()
        body = (item.get("body") or "").lower()
        if not href or not href.startswith(("http://", "https://")):
            return -1
        href_lower = href.lower()
        if any(rd in href_lower for rd in review_domains):
            return -1
        points = 0
        host_slug = _url_host_slug(href)
        try:
            netloc = urllib.parse.urlparse(href).netloc.lower()
            main_slug = (netloc.split(".")[-2] if "." in netloc else "") or host_slug
        except Exception:
            main_slug = host_slug
        if host_slug and brand_slugs:
            if main_slug and main_slug in brand_slugs:
                points += 35
            elif any(bs in host_slug or host_slug in bs for bs in brand_slugs):
                points += 25
        for pattern in PRODUCT_PAGE_PATH_PATTERNS:
            if pattern in href.lower():
                points += 20
                break
        if any(d in href.lower() for d in SUPPORTED_SEARCH_DOMAINS):
            points += 10
        if product_lower and product_lower[:20] in title:
            points += 5
        if product_lower and product_lower[:20] in body:
            points += 3
        if shop_lower and shop_lower[:15] in title:
            points += 3
        return points

    best_url = ""
    best_score = -1
    first_valid = ""
    for item in results:
        href = (item.get("href") or item.get("url") or "").strip()
        if not href or not href.startswith(("http://", "https://")):
            continue
        if any(rd in href.lower() for rd in review_domains):
            continue
        if not first_valid:
            first_valid = href
        s = score_item(item)
        if s > best_score:
            best_score = s
            best_url = href
    chosen = best_url if best_url.startswith(("http://", "https://")) else first_valid
    if chosen:
        print(f"Scraper: Picked URL (score={best_score}): {chosen[:70]}...")
    return chosen or ""


# ---------- Google Images: primera imagen del producto ----------


def _is_blocked_image_domain(url: str) -> bool:
    if not url:
        return True
    try:
        netloc = urllib.parse.urlparse(url).netloc.lower()
        return any(b in netloc for b in _BLOCKED_IMAGE_DOMAINS)
    except Exception:
        return False


def _get_first_image_brave_api(query: str) -> str:
    """
    Brave Image Search API (https://api.search.brave.com/res/v1/images/search).
    Devuelve la URL de la primera imagen válida. 429 → retry una vez a los 2s.
    """
    if not BRAVE_SEARCH_API_KEY or not query or not query.strip():
        return ""
    url_api = "https://api.search.brave.com/res/v1/images/search"
    params = {"q": query.strip()[:200], "count": 10, "country": "us"}
    headers = {"Accept": "application/json", "Accept-Encoding": "gzip", "X-Subscription-Token": BRAVE_SEARCH_API_KEY}

    for attempt in range(2):
        try:
            if attempt > 0:
                time.sleep(2)
                print("Scraper: Brave Image API retry after 429...")
            resp = requests.get(url_api, params=params, headers=headers, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 429:
                if attempt == 0:
                    print("Scraper: Brave Image API 429; retrying in 2s...")
                    continue
                return ""
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results") or []
            for r in results:
                if not isinstance(r, dict):
                    continue
                # properties.url = imagen; thumbnail.src = thumbnail servido
                img_url = (r.get("properties") or {}).get("url") or (r.get("thumbnail") or {}).get("src") or ""
                img_url = (img_url or "").strip()
                if not img_url or not img_url.startswith(("http://", "https://")):
                    continue
                if _is_blocked_image_domain(img_url):
                    continue
                print(f"Scraper: Brave Image API first image: {img_url[:70]}...")
                return img_url
            if results:
                print("Scraper: Brave Image API returned results but no valid image URL")
            else:
                print("Scraper: Brave Image API returned 0 results")
            return ""
        except Exception as e:
            print(f"Scraper: Brave Image API failed: {e}")
            return ""
    return ""


def _get_first_image_google_images(query: str) -> str:
    """
    Busca en Google Imágenes (tbm=isch) y devuelve la URL de la primera imagen.
    Parsea el HTML/script donde Google embebe las URLs (p.ej. "ou":"https://...").
    """
    if not query or not query.strip():
        return ""
    url = "https://www.google.com/search"
    params = {"q": query.strip(), "tbm": "isch", "hl": "en"}
    try:
        resp = requests.get(url, params=params, headers=_browser_headers(), timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        html = resp.text
    except Exception as e:
        print(f"Scraper: Google Images request failed: {e}")
        return ""

    # Google embeds image URLs in script/data. Common patterns: "ou":"https://...", or "url":"https://..."
    # Also data-src, data-iurl in img tags on some versions
    candidates: List[str] = []

    # 1) Regex: "ou":"https://..." (original image URL in Google's JSON)
    for m in re.finditer(r'"ou"\s*:\s*"(https?://[^"]+)"', html):
        u = m.group(1).replace("\\u003d", "=").replace("\\/", "/").strip()
        if u and u.startswith(("http://", "https://")) and "google." not in u.lower():
            candidates.append(u)

    # 2) data-iurl or data-src on img (thumbnail/full)
    soup = BeautifulSoup(html, "html.parser")
    for img in soup.find_all("img", attrs={"data-src": True}):
        u = (img.get("data-src") or "").strip()
        if u.startswith(("http://", "https://")) and "google." not in u.lower():
            candidates.append(u)
    for img in soup.find_all("img", attrs={"data-iurl": True}):
        u = (img.get("data-iurl") or "").strip()
        if u.startswith(("http://", "https://")) and "google." not in u.lower():
            candidates.append(u)

    for u in candidates:
        if _is_blocked_image_domain(u):
            continue
        # Prefer URLs that look like image files or CDNs
        if any(ext in u.lower() for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif")):
            print(f"Scraper: Google Images first image: {u[:80]}...")
            return u
        if any(cdn in u.lower() for cdn in ("cdn.", "images.", "img.", "static.", "shopify", "amazon.com/images")):
            print(f"Scraper: Google Images first image (CDN): {u[:80]}...")
            return u

    if candidates:
        first = candidates[0]
        print(f"Scraper: Google Images first result: {first[:80]}...")
        return first
    print("Scraper: Google Images returned no parseable image URLs")
    return ""


# ---------- Página del producto: description, trends_text, imagen (fallback) ----------


def _extract_image_from_product_page(soup: BeautifulSoup, base_url: str) -> str:
    """
    Extrae la URL de la imagen del producto desde la página (og:image, itemprop=image, o primera img útil).
    Fallback cuando Google Images no devuelve nada.
    """
    # 1) og:image (muy común en tiendas)
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        href = (og["content"] or "").strip()
        if href.startswith(("http://", "https://")):
            return href
        if href.startswith("//"):
            return "https:" + href
        try:
            return urllib.parse.urljoin(base_url, href)
        except Exception:
            pass
    # 2) img[itemprop="image"]
    for img in soup.find_all("img", itemprop="image"):
        src = (img.get("src") or img.get("data-src") or "").strip()
        if not src or src.lower().startswith("data:"):
            continue
        if src.startswith(("http://", "https://")):
            return src
        if src.startswith("//"):
            return "https:" + src
        try:
            return urllib.parse.urljoin(base_url, src)
        except Exception:
            pass
    # 3) Primera img con src que parezca producto (cdn, product, images)
    for img in soup.find_all("img"):
        src = (img.get("src") or img.get("data-src") or "").strip()
        if not src or src.lower().startswith("data:") or "logo" in (img.get("alt") or "").lower():
            continue
        if "pixel" in src or "1x1" in src or "tracking" in src.lower():
            continue
        if any(x in src.lower() for x in ("/product", "cdn.", "images.", "shopify", "amazon.com/images")):
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
    body = soup.find("body")
    if not body:
        return ""
    for tag in body.find_all(["section", "div"], class_=re.compile(r"trend|popular|insight", re.I)):
        text = (tag.get_text() or "").strip()
        if len(text) > 50:
            return text
    text = (body.get_text() or "").strip()
    return re.sub(r"\s+", " ", text)[:MAX_BODY_SNIPPET]


# ---------- Handler principal ----------


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Payload: brand_name, product_name, shop_name, l2_category, candidate_url (opcional).
    Returns: url (brand/product page), image_url, description, trends_text.

    Orden (importante para que Lambda = local):
    1) URL de la marca: Brave Search API (o candidate_url).
    2) Fetch página del producto → description, trends_text, imagen (og:image / product img).
    3) Si no hay imagen: Brave Image Search API (fiable en Lambda), luego Google Images.
    """
    try:
        body = event if isinstance(event, dict) else json.loads(event)
    except (TypeError, json.JSONDecodeError):
        body = {}

    brand_name = (body.get("brand_name") or "").strip()
    product_name = (body.get("product_name") or "").strip()
    shop_name = (body.get("shop_name") or "").strip()
    candidate_url = (body.get("candidate_url") or "").strip()

    result = {
        "url": "",
        "image_url": "",
        "trends_text": "",
        "description": "",
    }

    search_query = f"{shop_name or brand_name} {product_name}".strip()

    # 1) URL de la marca/producto: solo Brave
    if candidate_url and candidate_url.startswith(("http://", "https://")):
        result["url"] = candidate_url
        print(f"Scraper: Using provided candidate_url: {candidate_url[:70]}...")
    elif BRAVE_SEARCH_API_KEY and search_query:
        brave_results = _search_brave_api(search_query, max_results=BRAVE_MAX_RESULTS)
        result["url"] = _pick_best_result_url(brave_results, product_name=product_name, shop_or_brand=shop_name or brand_name)
    else:
        if not BRAVE_SEARCH_API_KEY:
            print("Scraper: BRAVE_SEARCH_API_KEY not set; cannot resolve brand URL")
        elif not search_query:
            print("Scraper: No brand/product name for search")

    # 2) Fetch página del producto primero: description, trends_text e imagen de la marca
    if result["url"]:
        print(f"Scraper: Fetching product page for image/description: {result['url'][:70]}...")
        time.sleep(REQUEST_DELAY_SEC)
        try:
            resp = requests.get(
                result["url"],
                timeout=REQUEST_TIMEOUT,
                allow_redirects=True,
                headers=_browser_headers(referer=result["url"]),
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            desc = _extract_description(soup)
            if desc:
                result["description"] = desc[:500]
            trends = _extract_trends_snippet(soup)
            if trends:
                result["trends_text"] = trends[:MAX_BODY_SNIPPET]
            # Prioridad: imagen de la página del producto (misma marca), no Google/Amazon
            page_image = _extract_image_from_product_page(soup, result["url"])
            if page_image and not _is_blocked_image_domain(page_image):
                result["image_url"] = page_image
                print(f"Scraper: Image from product page: {page_image[:70]}...")
            elif not page_image:
                # Página cargó pero sin og:image/product img (posible SPA/JS o HTML distinto para Lambda)
                print("Scraper: Product page has no extractable image (og:image/itemprop/img); falling back to Google Images")
        except Exception as e:
            print(f"Scraper: Fetch product page failed: {e}")
            if not result["image_url"]:
                print("Scraper: No image from product page (fetch failed); will try Google Images if available")

    # 3) Si no hay imagen: Brave Image Search API (fiable desde Lambda), luego Google Imágenes
    if not result["image_url"] and search_query:
        result["image_url"] = _get_first_image_brave_api(search_query)
        if not result["image_url"]:
            result["image_url"] = _get_first_image_google_images(search_query)

    return result
