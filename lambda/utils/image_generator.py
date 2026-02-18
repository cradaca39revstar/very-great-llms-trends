"""
Image Generator Module.
Logo and product images both use Stability SD 3.5 Large (primary) and SD3 Large (fallback) in us-west-2.
Same logic: region, retries, fallback, and style preset. Color palette removed — model chooses colors freely.
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


# --- Logo prompt template: luxury product pack shot with brand mark on packaging (client feedback) ---

SD_LOGO_PROMPT_TEMPLATE = (
    "Professional product photography of luxury {brand_name} {category} packaging. "
    "The hero is the physical product — bottle, jar, or packaging appropriate for {category} — with premium materials: "
    "soft-touch matte finish, subtle embossing, hot foil accents. "
    "Elegant, cohesive color palette of the model's choice for luxury beauty. "
    "The brand mark featuring {style_reference} is clearly visible and prominently displayed on the packaging — "
    "centered or dominant, {style_preset} in style — embossed, foil-stamped, or printed so the brand mark is a focal element. "
    "Studio-quality lighting: soft diffused key light, gentle fill, clean white or neutral background. "
    "Composition: 3/4 angle product shot showcasing product form, material quality, and the brand mark. "
    "Quality bar: Aesop, Le Labo, Bottega Veneta — minimalist, premium, editorial. "
    "Photorealistic, commercial beauty packaging photography, 4K."
)

SD_LOGO_NEGATIVE_PROMPT = (
    "watermark, blur, distorted, low quality, cluttered, cartoon, illustration, flat vector, "
    "isolated icon on white, logo floating alone, gradient texture, sketch, amateur"
)

# --- Product image prompt (same model and region as logo) ---
SD_PRODUCT_PROMPT_TEMPLATE = (
    "Professional product photography of {product_name} by {brand_name}. "
    "{image_prompt_from_llm} "
    "Elegant, cohesive color palette of the model's choice for luxury beauty. "
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
    l2_category: str,
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
    category = (l2_category or "Beauty").strip()

    prompt = SD_LOGO_PROMPT_TEMPLATE.format(
        brand_name=brand_name_safe,
        category=category,
        style_reference=style_ref,
        style_preset=style_preset,
    ).strip()

    body = {
        "prompt": prompt,
        "negative_prompt": SD_LOGO_NEGATIVE_PROMPT,
        "seed": random.randint(0, 4294967293),
        "aspect_ratio": "4:5",
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
    Uses same API as logo: prompt, negative_prompt, seed, aspect_ratio. Includes style_preset; model chooses colors.
    """
    import boto3

    product_name_safe = (product_name or "Product").strip()
    brand_name_safe = (brand_name or "Brand").strip()
    image_prompt_safe = (image_prompt or "Product packaging, professional shot.").strip()

    style_preset = _get_sdxl_style_preset(brand_name_safe)

    prompt = SD_PRODUCT_PROMPT_TEMPLATE.format(
        product_name=product_name_safe,
        brand_name=brand_name_safe,
        image_prompt_from_llm=image_prompt_safe,
        style_preset=style_preset,
    ).strip()

    body = {
        "prompt": prompt,
        "negative_prompt": SD_PRODUCT_NEGATIVE_PROMPT,
        "seed": random.randint(0, 4294967293),
        "aspect_ratio": "4:5",
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
    Same logic as logo: region us-west-2, style preset in prompt; model chooses colors. Same signature for
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


def generate_brand_logo(
    brand_name: str,
    brand_tagline: str,
    l2_category: str,
    bedrock_client,
) -> Optional[bytes]:
    """
    Generate a brand logo using Stability SD 3.5 Large (primary) or SD3 Large (fallback).
    Same model/region/fallback as product images. bedrock_client unused (we use BEDROCK_IMAGE_REGION).
    l2_category: L2 product category (e.g. Skincare, Makeup) for category-specific product type.
    Returns PNG bytes or None on failure.
    """
    region = BEDROCK_IMAGE_REGION

    try:
        logo_bytes = _generate_logo_with_model(
            brand_name, brand_tagline, l2_category, SD_IMAGE_MODEL_ID, region
        )
        if logo_bytes is not None:
            print(f"[Logo] succeeded with model_id={SD_IMAGE_MODEL_ID}")
            return logo_bytes
    except Exception as e:
        print(f"[Logo] primary model {SD_IMAGE_MODEL_ID} error: {e}")

    try:
        logo_bytes = _generate_logo_with_model(
            brand_name, brand_tagline, l2_category, SD_IMAGE_FALLBACK_MODEL_ID, region
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
