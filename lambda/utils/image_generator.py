"""
Titan Image Generator Module (V2).
Generates product concept images via Amazon Titan Image Generator v2.
"""

import base64
import json
import random
import time
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from utils.bedrock_helper import TITAN_IMAGE_PROMPT_TEMPLATE

TITAN_IMAGE_MODEL_ID = "amazon.titan-image-generator-v2:0"
TITAN_MAX_RETRIES = 2
TITAN_RETRY_DELAY_SEC = 2
# Titan textToImageParams/text has a 512 character limit
TITAN_PROMPT_MAX_LENGTH = 512


def _truncate_prompt_for_titan(prompt: str, max_len: int = TITAN_PROMPT_MAX_LENGTH) -> str:
    """Truncate prompt to max_len chars; avoid cutting mid-word when possible."""
    if not prompt or len(prompt) <= max_len:
        return prompt or ""
    truncated = prompt[:max_len]
    last_space = truncated.rfind(" ")
    if last_space > max_len // 2:
        return truncated[:last_space]
    return truncated

# Logo: premium symbol only; style reference and palettes for elegant icons.
TITAN_LOGO_PROMPT_TEMPLATE = """Luxury brand icon for "{brand_name}". {style_reference}, high-end emblem style. Premium craftsmanship: timeless, iconic, refined. Clean vector lines, balanced, professional, minimal. Solid flat background (white or cream). Symbol only - no text, letters, words."""


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


# 2-color palettes for elegant premium logos (Titan V2 COLOR_GUIDED_GENERATION)
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
    """Devuelve una paleta premium aleatoria para colorGuidedGenerationParams.colors."""
    return list(random.choice(list(PREMIUM_COLOR_PALETTES.values())))


def generate_product_image(
    product_name: str,
    brand_name: str,
    image_prompt: str,
    bedrock_client,
) -> Optional[bytes]:
    """
    Generate a single product image using Titan Image Generator v2.
    Builds prompt from TITAN_IMAGE_PROMPT_TEMPLATE. Returns decoded image bytes or None on failure.
    """
    prompt = TITAN_IMAGE_PROMPT_TEMPLATE.format(
        product_name=product_name or "Product",
        brand_name=brand_name or "Brand",
        image_prompt_from_llm=image_prompt or "Product packaging, professional shot.",
    ).strip()
    prompt = _truncate_prompt_for_titan(prompt)

    body = {
        "textToImageParams": {"text": prompt},
        "taskType": "TEXT_IMAGE",
        "imageGenerationConfig": {
            "numberOfImages": 1,
            "height": 512,
            "width": 512,
            "cfgScale": 8.0,
        },
    }

    for attempt in range(TITAN_MAX_RETRIES):
        try:
            response = bedrock_client.invoke_model(
                modelId=TITAN_IMAGE_MODEL_ID,
                body=bytes(json.dumps(body), "utf-8"),
                contentType="application/json",
                accept="application/json",
            )
            resp_body = json.loads(response["body"].read())
            images = resp_body.get("images")
            if images and len(images) > 0:
                b64 = images[0]
                return base64.b64decode(b64)
            return None
        except Exception as e:
            print(f"Titan image generation failed (attempt {attempt + 1}/{TITAN_MAX_RETRIES}): {e}")
            if attempt < TITAN_MAX_RETRIES - 1:
                time.sleep(TITAN_RETRY_DELAY_SEC)
    return None


def generate_brand_logo(brand_name: str, brand_tagline: str, bedrock_client) -> Optional[bytes]:
    """
    Generate a brand logo image using Titan Image Generator v2 with Color Palette Control.
    Uses COLOR_GUIDED_GENERATION for consistent premium colors; style reference from brand name.
    Returns decoded PNG bytes or None on failure.
    """
    brand_name_safe = (brand_name or "Brand").replace("Haircare", "").replace("haircare", "").replace("Hair", "").replace("hair", "").strip()
    if not brand_name_safe:
        brand_name_safe = brand_name or "Brand"

    style_ref = get_style_reference(brand_name_safe)
    prompt = TITAN_LOGO_PROMPT_TEMPLATE.format(
        brand_name=brand_name_safe,
        style_reference=style_ref,
    ).strip()

    negative = "text, letters, words, font, tagline, gradient, texture, watercolor, sketch, blur, 3D, shadow"
    total_length = len(prompt) + len(negative)
    if total_length > 512:
        max_prompt_len = 512 - len(negative) - 5
        if max_prompt_len > 0:
            prompt = prompt[:max_prompt_len].rsplit(" ", 1)[0]
        total_length = len(prompt) + len(negative)
    print(f"Logo prompt length: {len(prompt)}, negative: {len(negative)}, total: {total_length}")

    body = {
        "taskType": "COLOR_GUIDED_GENERATION",
        "colorGuidedGenerationParams": {
            "text": prompt,
            "colors": get_random_premium_palette(),
            "negativeText": negative,
        },
        "imageGenerationConfig": {
            "numberOfImages": 1,
            "height": 1024,
            "width": 1024,
            "cfgScale": 8.5,
            "seed": random.randint(0, 2147483647),
        },
    }
    for attempt in range(TITAN_MAX_RETRIES):
        try:
            response = bedrock_client.invoke_model(
                modelId=TITAN_IMAGE_MODEL_ID,
                body=bytes(json.dumps(body), "utf-8"),
                contentType="application/json",
                accept="application/json",
            )
            resp_body = json.loads(response["body"].read())
            images = resp_body.get("images")
            if images and len(images) > 0:
                return base64.b64decode(images[0])
            return None
        except Exception as e:
            print(f"Titan brand logo generation failed (attempt {attempt + 1}/{TITAN_MAX_RETRIES}): {e}")
            if attempt < TITAN_MAX_RETRIES - 1:
                time.sleep(TITAN_RETRY_DELAY_SEC)
    return None


def generate_images_parallel(
    product_ideas: List[dict],
    brand_name: str,
    bedrock_client,
    max_workers: int = 5,
) -> List[Optional[bytes]]:
    """
    Generate images for all product ideas in parallel. Returns list of image bytes (or None) in same order as product_ideas.
    """
    brand_name = brand_name or ""
    results: List[Optional[bytes]] = [None] * len(product_ideas)

    def task(i: int, idea: dict) -> tuple:
        name = idea.get("product_name") or ""
        prompt = idea.get("image_prompt") or ""
        start = time.time()
        img = generate_product_image(name, brand_name, prompt, bedrock_client)
        elapsed = (time.time() - start) * 1000
        print(f"Titan image {i + 1} completed in {elapsed:.0f}ms (ok={img is not None})")
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
