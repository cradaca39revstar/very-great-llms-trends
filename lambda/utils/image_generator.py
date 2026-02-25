"""
Image Generator Module — product-first approach (client priority).

One cohesive image: product + packaging + logo + text.
- Stability AI generates the full product image with an integrated logo/symbol on the packaging,
  using the SAME style reference we use for standalone logos (geometric/botanical/abstract)
  so that style is preserved.
- Pillow adds only the brand name and product name as crisp text at the bottom (AI text is unreliable).
- No separate logo generation; no logo overlay. Logo as standalone file is not a priority.
"""

import base64
import io
import json
import os
import random
import time
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- Stability: SD 3.5 Large primary, SD3 Large fallback ---
SD_IMAGE_MODEL_ID = "stability.sd3-5-large-v1:0"
SD_IMAGE_FALLBACK_MODEL_ID = "stability.sd3-large-v1:0"
BEDROCK_IMAGE_REGION = os.environ.get("BEDROCK_LOGO_REGION", "us-west-2")
SD_IMAGE_MAX_RETRIES = 2
SD_IMAGE_RETRY_DELAY_SEC = 2


# --- Style reference: same conditions as standalone logo (preserve that style in product) ---
_BAD_STYLE_TERMS = (
    "letterform", "monogram", "typographic", "wordmark", "lettermark", "initial",
    "glyph", "character", "calligraphic", "script", "text-based", "text based",
)


def _sanitize_style(value: str) -> str:
    if not value:
        return value
    v = value.lower()
    for term in _BAD_STYLE_TERMS:
        if term in v:
            v = v.replace(term, "").strip()
    return v.strip() or "abstract geometric form"


def get_style_reference(brand_name: str) -> str:
    """
    Same style reference used for standalone logo generation.
    Geometric/botanical/abstract only — so the logo drawn ON the product has that style.
    """
    name = (brand_name or "").lower().replace("haircare", "").replace("hair", "").strip()
    if any(w in name for w in ["nature", "terra", "green", "eco", "natural", "organic"]):
        out = "Botanical leaf or plant element"
    elif any(w in name for w in ["royal", "crown", "king", "queen", "regal"]):
        out = "Royal crown or heraldic crest"
    elif any(w in name for w in ["star", "celeste", "sky", "luna", "stella"]):
        out = "Celestial star or constellation"
    elif any(w in name for w in ["ocean", "aqua", "marine", "wave", "sea"]):
        out = "Flowing wave or water droplet"
    elif any(w in name for w in ["aura", "glow", "light", "lux", "pure"]):
        out = "Radiant sun rays or luminous circle"
    else:
        out = "Elegant geometric symbol or abstract mark"
    return _sanitize_style(out) or "Elegant geometric symbol or abstract mark"


def _get_style_preset(brand_name: str) -> str:
    name = (brand_name or "").lower()
    if any(w in name for w in ["tech", "digital", "modern", "future"]):
        return "digital-art"
    if any(w in name for w in ["luxury", "premium", "elegant", "royal"]):
        return "line-art"
    if any(w in name for w in ["organic", "natural", "eco"]):
        return "analog-film"
    return "line-art"


# --- Product prompt: one image with product + packaging + logo (same style as standalone) ---
# We describe the logo style so the AI draws it integrated on the packaging; we do NOT ask for text
# from the AI (Pillow adds brand/product name for legibility).
SD_PRODUCT_PROMPT_TEMPLATE = (
    "Professional commercial product photography of \"{product_name}\". "
    "{image_prompt_from_llm} "
    "The packaging has an elegant, integrated label area. "
    "On the label, a {logo_style} is integrated as the brand logo — same visual style as a premium standalone logo: "
    "single clear symbol or icon, cohesive with the packaging, no text or letters on the packaging. "
    "Premium, cohesive color palette. Clean white studio background, soft studio lighting, "
    "high-end product packaging, commercial photography, photorealistic, {style_preset} style, 4K quality."
)
SD_PRODUCT_NEGATIVE_PROMPT = (
    "text, words, letters, numbers, writing, brand name on label, typography on packaging, watermark, stamp, "
    "blur, distorted, low quality, cluttered background, cartoon, illustration, drawing, amateur"
)


def _generate_product_image_with_model(
    product_name: str,
    brand_name: str,
    image_prompt: str,
    model_id: str,
    region: str,
) -> Optional[bytes]:
    """Generate one product image with integrated logo (same style as standalone)."""
    import boto3

    product_name_safe = (product_name or "Product").strip()
    brand_name_safe = (brand_name or "Brand").strip()
    image_prompt_safe = (image_prompt or "Product packaging, professional shot.").strip()

    style_preset = _get_style_preset(brand_name_safe)
    logo_style = get_style_reference(brand_name_safe)

    prompt = SD_PRODUCT_PROMPT_TEMPLATE.format(
        product_name=product_name_safe,
        image_prompt_from_llm=image_prompt_safe,
        logo_style=logo_style,
        style_preset=style_preset,
    ).strip()

    body = {
        "prompt": prompt,
        "negative_prompt": SD_PRODUCT_NEGATIVE_PROMPT,
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
            try:
                resp_body = json.loads(response["body"].read())
            except (json.JSONDecodeError, TypeError) as parse_err:
                print(f"[Product] parse error: {parse_err}")
                return None

            if "images" not in resp_body:
                print(f"[Product] no 'images': {list(resp_body.keys())}")
                return None
            images = resp_body.get("images") or []
            if not images:
                print(f"[Product] empty images; finish_reasons={resp_body.get('finish_reasons')}")
                return None
            return base64.b64decode(images[0])
        except Exception as e:
            print(f"[Product] {model_id} attempt {attempt + 1}/{SD_IMAGE_MAX_RETRIES}: {e}")
            if attempt < SD_IMAGE_MAX_RETRIES - 1:
                time.sleep(SD_IMAGE_RETRY_DELAY_SEC)
    return None


def _overlay_branding_text(
    image_bytes: bytes,
    brand_name: str,
    product_name: str,
) -> bytes:
    """Overlay brand name + product name at bottom (crisp typography). Text from AI is not reliable."""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    w, h = img.size

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw_ov = ImageDraw.Draw(overlay)
    grad_h = int(h * 0.28)
    for y in range(grad_h):
        alpha = int(170 * (y / grad_h))
        draw_ov.line([(0, h - grad_h + y), (w, h - grad_h + y)], fill=(0, 0, 0, alpha))

    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    brand_size = max(int(w * 0.055), 24)
    product_size = max(int(w * 0.032), 16)

    try:
        brand_font = ImageFont.load_default(size=brand_size)
        product_font = ImageFont.load_default(size=product_size)
    except TypeError:
        brand_font = ImageFont.load_default()
        product_font = brand_font

    brand_text = (brand_name or "").strip().upper()
    product_text = (product_name or "").strip()

    bb = draw.textbbox((0, 0), brand_text, font=brand_font)
    bw, bh = bb[2] - bb[0], bb[3] - bb[1]
    pb = draw.textbbox((0, 0), product_text, font=product_font)
    pw, ph = pb[2] - pb[0], pb[3] - pb[1]

    gap = int(h * 0.012)
    total_h = bh + gap + ph
    y0 = h - total_h - int(h * 0.04)

    bx = (w - bw) // 2
    draw.text((bx + 2, y0 + 2), brand_text, fill=(0, 0, 0, 180), font=brand_font)
    draw.text((bx, y0), brand_text, fill=(255, 255, 255, 255), font=brand_font)

    px = (w - pw) // 2
    py = y0 + bh + gap
    draw.text((px + 1, py + 1), product_text, fill=(0, 0, 0, 150), font=product_font)
    draw.text((px, py), product_text, fill=(210, 210, 210, 255), font=product_font)

    result = img.convert("RGB")
    buf = io.BytesIO()
    result.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def generate_product_image(
    product_name: str,
    brand_name: str,
    image_prompt: str,
    bedrock_client=None,
) -> Optional[bytes]:
    """
    One cohesive image: product + packaging + logo (same style as standalone) + text bar.
    AI draws the logo integrated on the packaging; Pillow adds brand/product name at bottom.
    Returns PNG bytes or None.
    """
    region = BEDROCK_IMAGE_REGION

    try:
        raw = _generate_product_image_with_model(
            product_name, brand_name, image_prompt, SD_IMAGE_MODEL_ID, region,
        )
        if raw is not None:
            print(f"[Product] ok with {SD_IMAGE_MODEL_ID}")
    except Exception as e:
        print(f"[Product] primary error: {e}")
        raw = None

    if raw is None:
        try:
            raw = _generate_product_image_with_model(
                product_name, brand_name, image_prompt, SD_IMAGE_FALLBACK_MODEL_ID, region,
            )
            if raw is not None:
                print(f"[Product] ok with fallback {SD_IMAGE_FALLBACK_MODEL_ID}")
        except Exception as e:
            print(f"[Product] fallback error: {e}")

    if raw is None:
        print("[Product] all attempts failed")
        return None

    try:
        out = _overlay_branding_text(raw, brand_name, product_name)
        print(f"[Product] text overlay applied for '{product_name}'")
        return out
    except Exception as e:
        print(f"[Product] overlay failed, returning raw: {e}")
        return raw


def generate_images_parallel(
    product_ideas: List[dict],
    brand_name: str,
    bedrock_client=None,
    max_workers: int = 5,
) -> List[Optional[bytes]]:
    """Generate product images in parallel. Each image: product + integrated logo style + text bar."""
    brand_name = brand_name or ""
    results: List[Optional[bytes]] = [None] * len(product_ideas)

    def task(i: int, idea: dict) -> tuple:
        name = idea.get("product_name") or ""
        prompt = idea.get("image_prompt") or ""
        start = time.time()
        img = generate_product_image(name, brand_name, prompt, bedrock_client)
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
