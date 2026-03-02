"""
Market Research Agent: Brave Search API integration.
Runs 3 searches (trends, pain_points, competitors) in parallel with 4s total timeout.
Graceful degradation: on failure returns empty result; never blocks report generation.
"""

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any, Optional

import requests

BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"
HTTP_TIMEOUT = (2, 4)  # connect 2s, read 4s
TOTAL_TIMEOUT = 4  # total wall clock for all 3 searches (optimization for 20-25s report target)
COUNT_PER_QUERY = 5


def _brave_search(api_key: str, query: str, count: int = COUNT_PER_QUERY) -> List[Dict[str, str]]:
    """Single Brave web search. Returns list of {title, url, snippet}. On error returns []."""
    if not api_key or not query or not str(query).strip():
        return []
    headers = {"Accept": "application/json", "Accept-Encoding": "gzip", "X-Subscription-Token": api_key}
    params = {"q": str(query).strip(), "count": min(count, 20), "country": "us", "search_lang": "en"}
    try:
        r = requests.get(BRAVE_URL, headers=headers, params=params, timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        out = []
        for res in (data.get("web", {}).get("results") or [])[:count]:
            out.append({
                "title": (res.get("title") or "").strip(),
                "url": (res.get("url") or res.get("href") or "").strip(),
                "snippet": (res.get("description") or res.get("body") or "").strip(),
            })
        return out
    except Exception as e:
        print(f"Brave search failed for '{query[:50]}': {e}")
        return []


def search_all(
    l2_category: str,
    user_query: str,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run 3 Brave searches in parallel (trends, pain_points, competitors) with TOTAL_TIMEOUT seconds total.
    Returns dict with keys: trends, pain_points, competitors, from_cache (always False here).
    On any failure returns empty lists; never raises.
    """
    api_key = (api_key or os.environ.get("BRAVE_SEARCH_API_KEY") or "").strip()
    if not api_key:
        print("MarketResearchAgent: BRAVE_SEARCH_API_KEY not set; skipping web search")
        return {"trends": [], "pain_points": [], "competitors": [], "from_cache": False}

    category = (l2_category or "Beauty").strip()
    queries = {
        "trends": f"{category} beauty trends 2024 2025",
        "pain_points": f"{category} consumer pain points complaints",
        "competitors": f"{category} top brands competitors",
    }
    result: Dict[str, Any] = {"trends": [], "pain_points": [], "competitors": [], "from_cache": False}

    try:
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(_brave_search, api_key, q, COUNT_PER_QUERY): k for k, q in queries.items()}
            try:
                for future in as_completed(futures, timeout=TOTAL_TIMEOUT):
                    key = futures[future]
                    try:
                        result[key] = future.result(timeout=1)
                    except Exception as e:
                        print(f"Brave {key} result failed: {e}")
            except TimeoutError:
                print("MarketResearchAgent: 4s timeout reached; using partial results")
    except Exception as e:
        print(f"MarketResearchAgent: search_all failed: {e}")

    return result
