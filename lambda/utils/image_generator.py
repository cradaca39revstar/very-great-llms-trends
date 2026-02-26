"""
Image Generator Module — Stability SD 3.5 Large (fully holistic).

Every product image is generated in ONE shot via SD 3.5 Large: product + packaging +
wrapped label + prominent graphic logo icon + brand name + product name — all together.
No separate logo generation, no overlay, no logo extraction.
"""

import base64
import io
import json
import os
import random
import time
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

SD_IMAGE_MODEL_ID = "stability.sd3-5-large-v1:0"
SD_IMAGE_FALLBACK_MODEL_ID = "stability.sd3-large-v1:0"
BEDROCK_IMAGE_REGION = os.environ.get("BEDROCK_LOGO_REGION", "us-west-2")
SD_IMAGE_MAX_RETRIES = 2
SD_IMAGE_RETRY_DELAY_SEC = 2


# ============================================================================
# Style helpers — concrete, drawable icon shapes that SD 3.5 reliably renders
# ============================================================================
def get_logo_icon(brand_name: str) -> str:
    """
    Return a concrete, simple icon description. Must be a shape SD 3.5 knows
    how to draw (like the sunburst that worked perfectly for dermaluxe).
    All descriptions follow the same pattern: color + recognizable shape + "embossed on".
    """
    name = (brand_name or "").lower().replace("haircare", "").replace("hair", "").strip()
    if any(w in name for w in ["nature", "terra", "green", "eco", "natural", "organic"]):
        return "a golden leaf embossed on"
    if any(w in name for w in ["royal", "crown", "king", "queen", "regal"]):
        return "a golden crown embossed on"
    if any(w in name for w in ["star", "celeste", "sky", "luna", "stella"]):
        return "a golden star embossed on"
    if any(w in name for w in ["ocean", "aqua", "marine", "wave", "sea"]):
        return "a silver water droplet embossed on"
    if any(w in name for w in ["aura", "glow", "light", "lux", "pure", "lumina", "illumina", "radi"]):
        return "a golden sunburst circle embossed on"
    if any(w in name for w in ["silk", "soft", "velvet", "smooth", "satin"]):
        return "a golden lotus flower embossed on"
    if any(w in name for w in ["derma", "skin", "derm", "hydra", "moist"]):
        return "a golden sunburst circle embossed on"
    return "a golden sunburst circle embossed on"


def _get_style_preset(brand_name: str) -> str:
    name = (brand_name or "").lower()
    if any(w in name for w in ["tech", "digital", "modern", "future"]):
        return "digital-art"
    if any(w in name for w in ["luxury", "premium", "elegant", "royal"]):
        return "line-art"
    if any(w in name for w in ["organic", "natural", "eco"]):
        return "analog-film"
    return "line-art"


# ============================================================================
# Holistic product prompt — product + packaging + logo icon + brand name
# ============================================================================
SD_PRODUCT_NEGATIVE_PROMPT = (
    "no icon, no logo, missing logo, invisible logo, plain bottle without icon, "
    "bare bottle, blank label, empty label, label with only text, text-only label, "
    "duplicate brand name, repeated brand name, repeated text, brand name in two places, "
    "flat label, pasted label, badly photoshopped, "
    "cluttered design, low quality, blurry text, blur, distorted, "
    "cartoon, illustration, drawing, amateur"
)


def build_product_prompt(
    brand_name: str,
    product_name: str,
    image_prompt: str = "",
    key_ingredients: Optional[List[str]] = None,
) -> str:
    """
    Build a holistic SD 3.5 prompt. The icon/logo is described FIRST so the model
    prioritizes rendering it. Uses concrete shapes (sunburst, leaf, crown, droplet)
    that SD 3.5 reliably draws.
    """
    brand = (brand_name or "Brand").strip()
    product = (product_name or "Product").strip()
    visual_desc = (image_prompt or "premium skincare bottle on a clean background, luxury cosmetic aesthetic").strip()
    logo_icon = get_logo_icon(brand)
    style_preset = _get_style_preset(brand)

    benefit_line = ""
    if key_ingredients:
        top = [k.strip() for k in key_ingredients[:3] if k and k.strip()]
        if top:
            benefit_line = f" ({', '.join(top)})"

    prompt = (
        f"A luxury skincare bottle with {logo_icon} the front label. "
        f"The embossed icon is large, centered, and clearly visible on the label. "
        f"Below the icon, the brand name \"{brand}\" in elegant typography, once. "
        f"Below that, \"{product}\"{benefit_line} in smaller text. "
        f"Professional studio photograph, {visual_desc}. "
        f"The label wraps naturally around the bottle with realistic curvature. "
        f"No other text or branding anywhere else on the bottle. "
        f"Clean minimal design, soft studio lighting, {style_preset} style, photorealistic, 4K."
    )

    return prompt


# ============================================================================
# Stability SD 3.5 invocation
# ============================================================================
def _invoke_stability(prompt: str, negative_prompt: str, model_id: str, region: str, tag: str = "Img") -> Optional[bytes]:
    """Call Stability model. Returns PNG bytes or None."""
    import boto3
    body = {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "seed": random.randint(0, 4294967293),
        "aspect_ratio": "1:1",
        "output_format": "png",
    }
    client = boto3.client("bedrock-runtime", region_name=region)
    for attempt in range(SD_IMAGE_MAX_RETRIES):
        try:
            response = client.invoke_model(
                modelId=model_id,
                body=bytes(json.dumps(body), "utf-8"),
                contentType="application/json",
                accept="application/json",
            )
            resp_body = json.loads(response["body"].read())
            if "images" not in resp_body or not resp_body.get("images"):
                return None
            return base64.b64decode(resp_body["images"][0])
        except Exception as e:
            print(f"[{tag}] {model_id} attempt {attempt + 1}: {e}")
            if attempt < SD_IMAGE_MAX_RETRIES - 1:
                time.sleep(SD_IMAGE_RETRY_DELAY_SEC)
    return None


# ============================================================================
# Public API
# ============================================================================
def generate_product_image(
    product_name: str,
    brand_name: str,
    image_prompt: str,
    bedrock_client=None,
    key_ingredients: Optional[List[str]] = None,
) -> Optional[bytes]:
    """
    Generate a holistic product image via SD 3.5 Large: product + packaging + label +
    logo icon + brand name all in one shot. Falls back to SD3 Large.
    """
    region = BEDROCK_IMAGE_REGION
    prompt = build_product_prompt(
        brand_name=brand_name,
        product_name=product_name,
        image_prompt=image_prompt,
        key_ingredients=key_ingredients,
    )

    for model_id in (SD_IMAGE_MODEL_ID, SD_IMAGE_FALLBACK_MODEL_ID):
        raw = _invoke_stability(prompt, SD_PRODUCT_NEGATIVE_PROMPT, model_id, region, "Product")
        if raw:
            print(f"[Product] ok with {model_id} for '{product_name}'")
            return raw

    print(f"[Product] all attempts failed for '{product_name}'")
    return None


def generate_images_parallel(
    product_ideas: List[dict],
    brand_name: str,
    bedrock_client=None,
    max_workers: int = 4,
) -> List[Optional[bytes]]:
    """Generate holistic product images in parallel via SD 3.5 Large."""
    brand_name = brand_name or ""
    results: List[Optional[bytes]] = [None] * len(product_ideas)

    def task(i: int, idea: dict) -> tuple:
        name = idea.get("product_name") or ""
        prompt = idea.get("image_prompt") or ""
        ingredients = idea.get("key_ingredients") if isinstance(idea.get("key_ingredients"), list) else None
        start = time.time()
        img = generate_product_image(name, brand_name, prompt, None, ingredients)
        elapsed = (time.time() - start) * 1000
        print(f"[Product] image {i + 1} done in {elapsed:.0f}ms (ok={img is not None})")
        return (i, img)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(task, i, idea): i
            for i, idea in enumerate(product_ideas)
        }
        for future in as_completed(futures):
            try:
                idx, img_bytes = future.result()
                results[idx] = img_bytes
            except Exception as e:
                print(f"Image task failed: {e}")
    return results
