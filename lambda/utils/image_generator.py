"""
Image Generator Module.
Logo and product images both use Stability SD 3.5 Large (primary) and SD3 Large (fallback) in us-west-2.
Same logic: region, retries, fallback, color palette, and style preset.
"""

import base64
import json
import os
import random
import time
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- Stability: SD 3.5 Large primary, SD3 Large fallback (logos + product images) ---
SD_IMAGE_MODEL_ID = "stability.sd3-5-large-v1:0"
SD_IMAGE_FALLBACK_MODEL_ID = "stability.sd3-large-v1:0"
BEDROCK_IMAGE_REGION = os.environ.get("BEDROCK_LOGO_REGION", "us-west-2")
SD_IMAGE_MAX_RETRIES = 2
SD_IMAGE_RETRY_DELAY_SEC = 2


# --- Style reference (shared) ---


def get_style_reference(brand_name: str) -> str:
    """Returns style reference - strips sensitive words that may trigger content filters."""
    name_clean = (brand_name or "").lower().replace("haircare", "").replace("hair", "").strip()

    if any(word in name_clean for word in ["nature", "terra", "green", "eco", "natural", "organic"]):
        return "Botanical leaf or plant element"
    elif any(word in name_clean for word in ["royal", "crown", "king", "queen", "regal"]):
        return "Royal crown or heraldic crest"
    elif any(word in name_clean for word in ["star", "celeste", "sky", "luna", "stella"]):
        return "Celestial star or constellation"
    elif any(word in name_clean for word in ["ocean", "aqua", "marine", "wave", "sea"]):
        return "Flowing wave or water droplet"
    elif any(word in name_clean for word in ["aura", "glow", "light", "lux", "pure"]):
        return "Radiant sun rays or luminous circle"
    else:
        return "Elegant geometric symbol or abstract mark"


# --- Premium color palettes (logos) ---

PREMIUM_COLOR_PALETTES = {
    "classic_gold": ["#C9A961", "#000000"],
    "noir_elegance": ["#1A1A1A", "#FFFFFF"],
    "champagne": ["#D4AF37", "#2C2C2C"],
    "rose_gold": ["#B76E79", "#FFFFFF"],
    "emerald": ["#0C4B33", "#E8DCC8"],
    "navy_prestige": ["#1B2845", "#D4AF37"],
    "burgundy": ["#6B1C23", "#F5E6D3"],
    "platinum": ["#4A4A4A", "#E5E4E2"],
    "bronze": ["#8B6914", "#FFFFFF"],
    "sage": ["#87906F", "#F8F6F0"],
}


def get_random_premium_palette() -> List[str]:
    """Returns a random premium palette (list of hex colors) for logo generation."""
    return list(random.choice(list(PREMIUM_COLOR_PALETTES.values())))


# --- Hex to descriptive color name for SD prompt (Improvement 5) ---

_HEX_TO_NAME = {
    "#c9a961": "gold",
    "#d4af37": "gold",
    "#000000": "black",
    "#1a1a1a": "black",
    "#2c2c2c": "black",
    "#ffffff": "white",
    "#f5e6d3": "cream",
    "#f8f6f0": "cream",
    "#b76e79": "rose gold",
    "#0c4b33": "emerald green",
    "#1b2845": "navy blue",
    "#6b1c23": "burgundy",
    "#4a4a4a": "silver",
    "#e5e4e2": "platinum",
    "#8b6914": "bronze",
    "#87906f": "sage green",
    "#e8dcc8": "cream",
}


def _hex_to_color_name(hex_color: str) -> str:
    """
    Convert hex color to descriptive name for better model understanding.
    Returns a friendly name (e.g. 'gold', 'black') or the hex if unknown.
    """
    if not hex_color or not isinstance(hex_color, str):
        return "neutral"
    h = hex_color.strip().lower()
    if not h.startswith("#"):
        h = "#" + h
    return _HEX_TO_NAME.get(h, h)


def _palette_to_color_scheme_text(hex_list: List[str]) -> str:
    """Build color scheme sentence for the prompt from a list of hex colors."""
    names = []
    for h in (hex_list or [])[:4]:  # cap at 4 to keep prompt clean
        n = _hex_to_color_name(h)
        if n and n not in names:
            names.append(n)
    if not names:
        return "Color scheme: elegant neutral tones, solid flat colors, no gradients."
    return "Color scheme: " + " and ".join(names) + ", solid flat colors, no gradients."


# --- Dynamic style preset for logo prompt (Improvement 2) ---


def _get_sdxl_style_preset(brand_name: str) -> str:
    """
    Return style preset label based on brand name for prompt text.
    Used to steer logo style (digital-art, line-art, analog-film) in the prompt.
    """
    name = (brand_name or "").lower()
    if any(w in name for w in ["tech", "digital", "modern", "future"]):
        return "digital-art"
    if any(w in name for w in ["luxury", "premium", "elegant", "royal"]):
        return "line-art"
    if any(w in name for w in ["organic", "natural", "eco"]):
        return "analog-film"
    return "line-art"


# --- Logo prompt template (Improvement 3) ---

SD_LOGO_PROMPT_TEMPLATE = (
    "Professional minimalist logo design for luxury {brand_name} brand. {style_reference} as the central iconic element. "
    "Design composition: centered, balanced, symmetrical layout on white background. "
    "Art style: flat vector illustration, clean geometric shapes, minimal details, {style_preset} style. "
    "{color_scheme} "
    "Premium brand identity: timeless, refined, award-winning design quality. "
    "High-end emblem suitable for luxury packaging. "
    "Icon symbol only - absolutely no text, letters, or words of any kind."
)

SD_LOGO_NEGATIVE_PROMPT = (
    "text, letters, words, font, tagline, gradient, texture, watercolor, sketch, blur, 3D, shadow, "
    "complex background, cluttered, low quality, distorted"
)

# --- Product image prompt (same model and region as logo) ---
SD_PRODUCT_PROMPT_TEMPLATE = (
    "Professional product photography of {product_name} by {brand_name}. "
    "{image_prompt_from_llm} "
    "{color_scheme} "
    "Clean white studio background, soft studio lighting, high-end beauty product packaging, "
    "commercial photography style, photorealistic, {style_preset} style, 4K quality."
)
SD_PRODUCT_NEGATIVE_PROMPT = (
    "text, watermark, logo, blur, distorted, low quality, cluttered background, "
    "cartoon, illustration, drawing"
)


# --- Internal: generate logo with a specific Stability model (Improvement 4) ---


def _generate_logo_with_model(
    brand_name: str,
    brand_tagline: str,
    model_id: str,
    region: str,
) -> Optional[bytes]:
    """
    Generate logo using one Stability model (SD 3.5 Large or SD3 Large).
    Uses prompt + negative_prompt; no Titan. Returns PNG bytes or None.
    """
    import boto3

    brand_name_safe = (
        (brand_name or "Brand")
        .replace("Haircare", "")
        .replace("haircare", "")
        .replace("Hair", "")
        .replace("hair", "")
        .strip()
    )
    if not brand_name_safe:
        brand_name_safe = brand_name or "Brand"

    style_ref = get_style_reference(brand_name_safe)
    style_preset = _get_sdxl_style_preset(brand_name_safe)
    palette = get_random_premium_palette()
    color_scheme = _palette_to_color_scheme_text(palette)

    prompt = SD_LOGO_PROMPT_TEMPLATE.format(
        brand_name=brand_name_safe,
        style_reference=style_ref,
        style_preset=style_preset,
        color_scheme=color_scheme,
    ).strip()

    body = {
        "prompt": prompt,
        "negative_prompt": SD_LOGO_NEGATIVE_PROMPT,
        "seed": random.randint(0, 4294967293),
        "aspect_ratio": "1:1",
        "output_format": "png",
    }

    # Log full prompt for debugging
    print(f"[Logo] model_id={model_id} region={region} prompt_length={len(prompt)}")
    print(f"[Logo] prompt={prompt[:200]}...")

    client = boto3.client("bedrock-runtime", region_name=region)

    for attempt in range(SD_IMAGE_MAX_RETRIES):
        try:
            response = client.invoke_model(
                modelId=model_id,
                body=bytes(json.dumps(body), "utf-8"),
                contentType="application/json",
                accept="application/json",
            )
            try:
                resp_body = json.loads(response["body"].read())
            except (json.JSONDecodeError, TypeError) as parse_err:
                print(f"[Logo] failed to parse response body: {parse_err}")
                return None

            # Log response structure when artifacts missing (Improvement 6)
            if "images" not in resp_body:
                print(f"[Logo] response missing 'images': keys={list(resp_body.keys())}")
                finish = resp_body.get("finish_reasons", [None])
                if finish and finish[0] is not None:
                    print(f"[Logo] finish_reasons={finish}")
                return None

            images = resp_body.get("images") or []
            if not images:
                print(f"[Logo] response 'images' empty; finish_reasons={resp_body.get('finish_reasons')}")
                return None

            try:
                return base64.b64decode(images[0])
            except (TypeError, ValueError) as decode_err:
                print(f"[Logo] failed to decode image base64: {decode_err}")
                return None
        except Exception as e:
            print(f"[Logo] model_id={model_id} attempt={attempt + 1}/{SD_IMAGE_MAX_RETRIES} failed: {e}")
            if attempt < SD_IMAGE_MAX_RETRIES - 1:
                time.sleep(SD_IMAGE_RETRY_DELAY_SEC)
    return None


# --- Product image: same SD 3.5 Large + SD3 fallback and same region/palette/style logic ---


def _generate_product_image_with_model(
    product_name: str,
    brand_name: str,
    image_prompt: str,
    model_id: str,
    region: str,
) -> Optional[bytes]:
    """
    Generate one product image using a Stability model (SD 3.5 Large or SD3 Large).
    Uses same API as logo: prompt, negative_prompt, seed, aspect_ratio. Includes color_scheme and style_preset.
    """
    import boto3

    product_name_safe = (product_name or "Product").strip()
    brand_name_safe = (brand_name or "Brand").strip()
    image_prompt_safe = (image_prompt or "Product packaging, professional shot.").strip()

    style_preset = _get_sdxl_style_preset(brand_name_safe)
    palette = get_random_premium_palette()
    color_scheme = _palette_to_color_scheme_text(palette)

    prompt = SD_PRODUCT_PROMPT_TEMPLATE.format(
        product_name=product_name_safe,
        brand_name=brand_name_safe,
        image_prompt_from_llm=image_prompt_safe,
        style_preset=style_preset,
        color_scheme=color_scheme,
    ).strip()

    body = {
        "prompt": prompt,
        "negative_prompt": SD_PRODUCT_NEGATIVE_PROMPT,
        "seed": random.randint(0, 4294967293),
        "aspect_ratio": "4:5",
        "output_format": "png",
    }

    print(f"[Product] model_id={model_id} region={region} prompt_length={len(prompt)}")
    print(f"[Product] prompt={prompt[:200]}...")

    client = boto3.client("bedrock-runtime", region_name=region)

    for attempt in range(SD_IMAGE_MAX_RETRIES):
        try:
            response = client.invoke_model(
                modelId=model_id,
                body=bytes(json.dumps(body), "utf-8"),
                contentType="application/json",
                accept="application/json",
            )
            try:
                resp_body = json.loads(response["body"].read())
            except (json.JSONDecodeError, TypeError) as parse_err:
                print(f"[Product] failed to parse response body: {parse_err}")
                return None

            if "images" not in resp_body:
                print(f"[Product] response missing 'images': keys={list(resp_body.keys())}")
                return None
            images = resp_body.get("images") or []
            if not images:
                print(f"[Product] response 'images' empty; finish_reasons={resp_body.get('finish_reasons')}")
                return None
            try:
                return base64.b64decode(images[0])
            except (TypeError, ValueError) as decode_err:
                print(f"[Product] failed to decode image base64: {decode_err}")
                return None
        except Exception as e:
            print(f"[Product] model_id={model_id} attempt={attempt + 1}/{SD_IMAGE_MAX_RETRIES} failed: {e}")
            if attempt < SD_IMAGE_MAX_RETRIES - 1:
                time.sleep(SD_IMAGE_RETRY_DELAY_SEC)
    return None


def generate_product_image(
    product_name: str,
    brand_name: str,
    image_prompt: str,
    bedrock_client,
) -> Optional[bytes]:
    """
    Generate a single product image using Stability SD 3.5 Large (primary) or SD3 Large (fallback).
    Same logic as logo: region us-west-2, color palette and style preset in prompt. Same signature for
    backward compatibility; bedrock_client is not used (we use BEDROCK_IMAGE_REGION).
    Returns PNG bytes or None on failure.
    """
    region = BEDROCK_IMAGE_REGION

    try:
        img_bytes = _generate_product_image_with_model(
            product_name, brand_name, image_prompt, SD_IMAGE_MODEL_ID, region
        )
        if img_bytes is not None:
            print(f"[Product] succeeded with model_id={SD_IMAGE_MODEL_ID}")
            return img_bytes
    except Exception as e:
        print(f"[Product] primary model {SD_IMAGE_MODEL_ID} error: {e}")

    try:
        img_bytes = _generate_product_image_with_model(
            product_name, brand_name, image_prompt, SD_IMAGE_FALLBACK_MODEL_ID, region
        )
        if img_bytes is not None:
            print(f"[Product] succeeded with fallback model_id={SD_IMAGE_FALLBACK_MODEL_ID}")
            return img_bytes
    except Exception as e:
        print(f"[Product] fallback model {SD_IMAGE_FALLBACK_MODEL_ID} error: {e}")

    print("[Product] all product image model attempts failed")
    return None


# --- Brand logo: SD 3.5 Large with SD3 fallback (Improvements 1–4, 6) ---


def generate_brand_logo(brand_name: str, brand_tagline: str, bedrock_client) -> Optional[bytes]:
    """
    Generate a brand logo using Stability SD 3.5 Large (primary) or SD3 Large (fallback).
    Same model/region/fallback as product images. bedrock_client unused (we use BEDROCK_IMAGE_REGION).
    Returns PNG bytes or None on failure.
    """
    region = BEDROCK_IMAGE_REGION

    try:
        logo_bytes = _generate_logo_with_model(
            brand_name, brand_tagline, SD_IMAGE_MODEL_ID, region
        )
        if logo_bytes is not None:
            print(f"[Logo] succeeded with model_id={SD_IMAGE_MODEL_ID}")
            return logo_bytes
    except Exception as e:
        print(f"[Logo] primary model {SD_IMAGE_MODEL_ID} error: {e}")

    try:
        logo_bytes = _generate_logo_with_model(
            brand_name, brand_tagline, SD_IMAGE_FALLBACK_MODEL_ID, region
        )
        if logo_bytes is not None:
            print(f"[Logo] succeeded with fallback model_id={SD_IMAGE_FALLBACK_MODEL_ID}")
            return logo_bytes
    except Exception as e:
        print(f"[Logo] fallback model {SD_IMAGE_FALLBACK_MODEL_ID} error: {e}")

    print("[Logo] all logo model attempts failed")
    return None


def generate_images_parallel(
    product_ideas: List[dict],
    brand_name: str,
    bedrock_client,
    max_workers: int = 5,
) -> List[Optional[bytes]]:
    """
    Generate images for all product ideas in parallel (SD 3.5 Large / SD3 fallback, same as logo).
    Returns list of image bytes (or None) in same order as product_ideas.
    """
    brand_name = brand_name or ""
    results: List[Optional[bytes]] = [None] * len(product_ideas)

    def task(i: int, idea: dict) -> tuple:
        name = idea.get("product_name") or ""
        prompt = idea.get("image_prompt") or ""
        start = time.time()
        img = generate_product_image(name, brand_name, prompt, bedrock_client)
        elapsed = (time.time() - start) * 1000
        print(f"[Product] image {i + 1} completed in {elapsed:.0f}ms (ok={img is not None})")
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
