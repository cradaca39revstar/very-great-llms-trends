"""
Image Generator Module.
Logo and product images both use Stability SD 3.5 Large (primary) and SD3 Large (fallback) in us-west-2.
Hybrid approach: AI generates a symbol (logo) or product shot with blank label, then Pillow composes
the final output — brand name text is drawn programmatically for crisp rendering.
"""

import base64
import io
import json
import os
import random
import time
from typing import List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- Stability: SD 3.5 Large primary, SD3 Large fallback (logos + product images) ---
SD_IMAGE_MODEL_ID = "stability.sd3-5-large-v1:0"
SD_IMAGE_FALLBACK_MODEL_ID = "stability.sd3-large-v1:0"
BEDROCK_IMAGE_REGION = os.environ.get("BEDROCK_LOGO_REGION", "us-west-2")
SD_IMAGE_MAX_RETRIES = 2
SD_IMAGE_RETRY_DELAY_SEC = 2


# --- Style reference (shared) ---
# CRITICAL: style_reference and style_preset must ONLY describe geometric shapes, botanical elements,
# or abstract visual forms. NEVER use: letterform, monogram, typographic, wordmark, lettermark,
# initial, glyph, character, calligraphic, script, text-based.
# GOOD: "geometric leaf drop shape", "abstract radial botanical motif", "minimal diamond geometric form".
# BAD: "monogram-style mark", "letterform inspired", "typographic minimal".

_BAD_STYLE_TERMS = (
    "letterform", "monogram", "typographic", "wordmark", "lettermark", "initial",
    "glyph", "character", "calligraphic", "script", "text-based", "text based",
)


def _sanitize_style_for_logo(value: str) -> str:
    """Ensure style strings never contain terms that could steer the model toward text/letters."""
    if not value:
        return value
    v = value.lower()
    for term in _BAD_STYLE_TERMS:
        if term in v:
            v = v.replace(term, "").strip()
    return v.strip() or "abstract geometric form"


def get_style_reference(brand_name: str) -> str:
    """
    Returns style reference for logo prompt — geometric/botanical/abstract only.
    CRITICAL: Only geometric shapes, botanical elements, or abstract visual forms.
    Never letterform, monogram, typographic, wordmark, or text-based terms.
    """
    name_clean = (brand_name or "").lower().replace("haircare", "").replace("hair", "").strip()

    if any(word in name_clean for word in ["nature", "terra", "green", "eco", "natural", "organic"]):
        out = "Botanical leaf or plant element"
    elif any(word in name_clean for word in ["royal", "crown", "king", "queen", "regal"]):
        out = "Royal crown or heraldic crest"
    elif any(word in name_clean for word in ["star", "celeste", "sky", "luna", "stella"]):
        out = "Celestial star or constellation"
    elif any(word in name_clean for word in ["ocean", "aqua", "marine", "wave", "sea"]):
        out = "Flowing wave or water droplet"
    elif any(word in name_clean for word in ["aura", "glow", "light", "lux", "pure"]):
        out = "Radiant sun rays or luminous circle"
    else:
        out = "Elegant geometric symbol or abstract mark"
    return _sanitize_style_for_logo(out) or "Elegant geometric symbol or abstract mark"


# --- Dynamic style preset for logo prompt (Improvement 2) ---


def _get_sdxl_style_preset(brand_name: str) -> str:
    """
    Return style preset for logo prompt (digital-art, line-art, analog-film).
    CRITICAL: Only visual style labels — no letterform, typographic, or text-based terms.
    """
    name = (brand_name or "").lower()
    if any(w in name for w in ["tech", "digital", "modern", "future"]):
        out = "digital-art"
    elif any(w in name for w in ["luxury", "premium", "elegant", "royal"]):
        out = "line-art"
    elif any(w in name for w in ["organic", "natural", "eco"]):
        out = "analog-film"
    else:
        out = "line-art"
    return _sanitize_style_for_logo(out) or "line-art"


# --- Logo prompt template: AI generates ONLY the symbol/mark — no text ---

SD_LOGO_PROMPT_TEMPLATE = (
    "Abstract geometric icon for {category} — {style_reference}, {style_preset} style. Pure graphic shape, completely text-free. "
    "Standalone graphic mark only. Single centered symbol on plain white background. "
    "No text, no letters, no words, no numbers anywhere in the image. "
    "Premium, minimalist, clean, 4K."
)

SD_LOGO_NEGATIVE_PROMPT = (
    "text, letter, letters, word, words, number, numbers, glyph, character, "
    "alphabet, script, typography, font, brand name, label, watermark, "
    "monogram, initial, letterform, calligraphy, any written symbol, "
    "blur, distorted, low quality, cluttered, cartoon, "
    "bottle, jar, product, packaging, gradient texture, sketch, amateur"
)

# --- Product prompt: blank white label area for programmatic logo overlay ---
SD_PRODUCT_PROMPT_TEMPLATE = (
    "Professional product photography of {product_name} beauty product. "
    "{image_prompt_from_llm} "
    "The packaging has a clean, completely blank white rectangular label area — no text, no logo printed on it. "
    "Elegant, cohesive color palette of the model's choice for luxury beauty. "
    "Clean white studio background, soft studio lighting, high-end beauty product packaging, "
    "commercial photography style, photorealistic, {style_preset} style, 4K quality."
)
SD_PRODUCT_NEGATIVE_PROMPT = (
    "text, letters, words, brand name, typography, font, logo printed on label, "
    "watermark, blur, distorted, low quality, cluttered background, "
    "cartoon, illustration, drawing"
)

# --- Font path for compose_logo() ---
_ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "fonts")
_FONT_CORMORANT = os.path.join(_ASSETS_DIR, "Cormorant-Light.ttf")
_FONT_REGULAR = os.path.join(_ASSETS_DIR, "arial.ttf")
_FONT_BOLD = os.path.join(_ASSETS_DIR, "arialbd.ttf")

# Fixed canvas for final brand image: symbol on top, brand name below (logo only, no product/packaging)
_COMPOSE_LOGO_CANVAS_W = 480
_COMPOSE_LOGO_CANVAS_H = 380
_COMPOSE_LOGO_SYMBOL_SIZE = (240, 240)
_COMPOSE_LOGO_SYMBOL_TOP = 30
_COMPOSE_LOGO_TEXT_Y = 290
_COMPOSE_LOGO_FONT_SIZE = 40


# --- Pillow composition utilities ---


def symbol_only_logo_image(symbol_image_bytes: bytes) -> bytes:
    """
    Place the AI-generated symbol centered on a white canvas with no text.
    Used as the brand image on the card (no letters in the logo; label is shown separately below).
    Returns PNG bytes (RGB).
    """
    from PIL import Image

    symbol = Image.open(io.BytesIO(symbol_image_bytes)).convert("RGBA")
    symbol = symbol.resize(_COMPOSE_LOGO_SYMBOL_SIZE, Image.LANCZOS)
    canvas_w, canvas_h = _COMPOSE_LOGO_CANVAS_W, _COMPOSE_LOGO_CANVAS_H
    canvas = Image.new("RGBA", (canvas_w, canvas_h), (255, 255, 255, 255))
    x = (canvas_w - symbol.width) // 2
    canvas.paste(symbol, (x, _COMPOSE_LOGO_SYMBOL_TOP), symbol)
    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


def compose_logo(
    brand_name: str,
    symbol_image_bytes: bytes,
    font_path: Optional[str] = None,
) -> bytes:
    """
    Compose the final brand image: AI-generated symbol only on top, brand name drawn below with Pillow.
    The raw AI symbol must NOT be returned to the frontend — this composed image is the logo output.
    Returns PNG bytes (RGB).
    """
    from PIL import Image, ImageDraw, ImageFont

    symbol = Image.open(io.BytesIO(symbol_image_bytes)).convert("RGBA")
    symbol = symbol.resize(_COMPOSE_LOGO_SYMBOL_SIZE, Image.LANCZOS)

    canvas_w, canvas_h = _COMPOSE_LOGO_CANVAS_W, _COMPOSE_LOGO_CANVAS_H
    canvas = Image.new("RGBA", (canvas_w, canvas_h), (255, 255, 255, 255))

    # Center symbol at top
    x = (canvas_w - symbol.width) // 2
    canvas.paste(symbol, (x, _COMPOSE_LOGO_SYMBOL_TOP), symbol)

    # Brand name text below symbol
    draw = ImageDraw.Draw(canvas)
    chosen = font_path or (_FONT_CORMORANT if os.path.exists(_FONT_CORMORANT) else _FONT_BOLD if os.path.exists(_FONT_BOLD) else _FONT_REGULAR)
    try:
        font = ImageFont.truetype(chosen, size=_COMPOSE_LOGO_FONT_SIZE) if chosen and os.path.exists(chosen) else ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), brand_name, font=font)
    text_w = bbox[2] - bbox[0]
    draw.text(((canvas_w - text_w) // 2, _COMPOSE_LOGO_TEXT_Y), brand_name, font=font, fill=(30, 30, 30, 255))

    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


def overlay_logo_on_product(
    product_image_bytes: bytes,
    logo_image_bytes: bytes,
    label_box: Optional[Tuple[int, int, int, int]] = None,
) -> bytes:
    """
    Overlay the composed logo onto the product image at the label area.
    Pipeline: product image (blank label) + composed logo → final product concept with logo on packaging.
    If label_box is None, defaults to centered, middle-lower third: 30% width, 18% height, y at 52%.
    Returns PNG bytes of the composited image.
    """
    from PIL import Image

    product = Image.open(io.BytesIO(product_image_bytes)).convert("RGBA")
    logo = Image.open(io.BytesIO(logo_image_bytes)).convert("RGBA")

    img_w, img_h = product.size

    if label_box is None:
        label_w = int(img_w * 0.30)
        label_h = int(img_h * 0.18)
        label_x = (img_w - label_w) // 2
        label_y = int(img_h * 0.52)
        label_box = (label_x, label_y, label_w, label_h)

    lx, ly, lw, lh = label_box

    # Fit logo inside label box preserving aspect ratio with inner padding
    inner_pad = max(4, lw // 12)
    max_w = lw - inner_pad * 2
    max_h = lh - inner_pad * 2
    logo_ratio = logo.width / logo.height
    if max_w / logo_ratio <= max_h:
        fit_w = max_w
        fit_h = int(max_w / logo_ratio)
    else:
        fit_h = max_h
        fit_w = int(max_h * logo_ratio)

    logo_resized = logo.resize((fit_w, fit_h), Image.LANCZOS)

    # Center logo within label box
    paste_x = lx + (lw - fit_w) // 2
    paste_y = ly + (lh - fit_h) // 2

    product.paste(logo_resized, (paste_x, paste_y), logo_resized)

    out = io.BytesIO()
    product.convert("RGB").save(out, format="PNG")
    return out.getvalue()


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

    # brand_name intentionally omitted — AI generates symbol only; text is added by compose_logo()
    prompt = SD_LOGO_PROMPT_TEMPLATE.format(
        category=category,
        style_reference=style_ref,
        style_preset=style_preset,
    ).strip()

    # SD3 / Stable Image format: prompt + negative_prompt (model applies negative prompt; no text_prompts array)
    body = {
        "prompt": prompt,
        "negative_prompt": SD_LOGO_NEGATIVE_PROMPT,
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
) -> Optional[Tuple[bytes, bytes]]:
    """
    Generate brand logo assets using Stability SD 3.5 Large (primary) or SD3 Large (fallback).
    AI produces the symbol only (no text).
    Returns (symbol_only_bytes, composed_logo_bytes) or None on failure.
    - symbol_only_bytes: for the brand image on the card (no letters; label is shown separately).
    - composed_logo_bytes: symbol + brand name text, for overlaying on product packaging.
    """
    region = BEDROCK_IMAGE_REGION
    symbol_bytes = None

    try:
        symbol_bytes = _generate_logo_with_model(
            brand_name, brand_tagline, l2_category, SD_IMAGE_MODEL_ID, region
        )
        if symbol_bytes is not None:
            print(f"[Logo] succeeded with model_id={SD_IMAGE_MODEL_ID}")
    except Exception as e:
        print(f"[Logo] primary model {SD_IMAGE_MODEL_ID} error: {e}")

    if symbol_bytes is None:
        try:
            symbol_bytes = _generate_logo_with_model(
                brand_name, brand_tagline, l2_category, SD_IMAGE_FALLBACK_MODEL_ID, region
            )
            if symbol_bytes is not None:
                print(f"[Logo] succeeded with fallback model_id={SD_IMAGE_FALLBACK_MODEL_ID}")
        except Exception as e:
            print(f"[Logo] fallback model {SD_IMAGE_FALLBACK_MODEL_ID} error: {e}")

    if symbol_bytes is None:
        print("[Logo] all logo model attempts failed")
        return None

    try:
        symbol_only = symbol_only_logo_image(symbol_bytes)
        composed = compose_logo(brand_name, symbol_bytes)
        print(f"[Logo] symbol_only + compose_logo() ok")
        return (symbol_only, composed)
    except Exception as e:
        print(f"[Logo] symbol_only/compose_logo failed: {e}; returning (raw symbol, raw symbol)")
        return (symbol_bytes, symbol_bytes)


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
