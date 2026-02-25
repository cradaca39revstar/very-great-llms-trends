"""
Image Generator Module — logo priority.

- Logo is generated independently (Stability AI: symbol only, then composed with brand name)
  and must be clearly visible on each product.
- Product image: clean product photography (smooth label area, no text/no logo from AI),
  then we overlay the composed logo prominently, then Pillow adds brand + product name at bottom.
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


# --- Logo: AI generates symbol only; we compose with brand name for overlay and brand card ---
SD_LOGO_PROMPT_TEMPLATE = (
    "Abstract geometric icon for {category} — {style_reference}, {style_preset} style. "
    "Pure graphic shape, completely text-free. Standalone graphic mark only. "
    "Single centered symbol on plain white background. No text, no letters, no words, no numbers. "
    "Premium, minimalist, clean, 4K."
)
SD_LOGO_NEGATIVE_PROMPT = (
    "text, letter, word, number, glyph, character, alphabet, script, typography, font, brand name, "
    "label, watermark, monogram, initial, letterform, blur, distorted, low quality, cluttered, "
    "cartoon, bottle, jar, product, packaging, sketch, amateur"
)

# --- Product: consistent composition so logo (fixed position) always lands on the product ---
SD_PRODUCT_PROMPT_TEMPLATE = (
    "Professional commercial product photography. Single product only, centered in the frame. "
    "The product is the main subject, same composition for every shot: product in the center of the image, "
    "vertical orientation, product body occupying the central area so a label would sit in the middle of the frame. "
    "\"{product_name}\". {image_prompt_from_llm} "
    "Bottle, jar, or package clearly in focus, consistent framing. "
    "The packaging has a smooth, elegant label area on the front — same material or finish as the product, no text, no logo. "
    "Premium, cohesive color palette. Clean white studio background, soft studio lighting, "
    "high-end product packaging, commercial photography, photorealistic, {style_preset} style, 4K quality."
)
SD_PRODUCT_NEGATIVE_PROMPT = (
    "text, words, letters, numbers, writing, brand name, typography, logo on label, watermark, stamp, "
    "blur, distorted, low quality, cluttered background, cartoon, illustration, drawing, amateur"
)


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


def symbol_only_logo_image(symbol_bytes: bytes) -> bytes:
    """Logo = symbol only on white canvas. No text. Used for brand card, overlay, and img2img init."""
    from PIL import Image

    symbol = Image.open(io.BytesIO(symbol_bytes)).convert("RGBA")
    canvas_w, canvas_h = 480, 380
    symbol_size = (220, 220)
    symbol_top = 30
    symbol = symbol.resize(symbol_size, Image.LANCZOS)
    canvas = Image.new("RGBA", (canvas_w, canvas_h), (255, 255, 255, 255))
    x = (canvas_w - symbol.width) // 2
    canvas.paste(symbol, (x, symbol_top), symbol)
    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


def generate_brand_logo(
    brand_name: str,
    brand_tagline: str,
    l2_category: str,
    bedrock_client=None,
) -> Optional[bytes]:
    """Generate logo: symbol only (no text). Returns PNG bytes for brand card, overlay, and img2img init."""
    region = BEDROCK_IMAGE_REGION
    brand_safe = (brand_name or "Brand").replace("Haircare", "").replace("haircare", "").replace("Hair", "").replace("hair", "").strip() or (brand_name or "Brand")
    category = (l2_category or "Beauty").strip()
    style_ref = get_style_reference(brand_safe)
    style_preset = _get_style_preset(brand_safe)
    prompt = SD_LOGO_PROMPT_TEMPLATE.format(
        category=category,
        style_reference=style_ref,
        style_preset=style_preset,
    ).strip()

    symbol = None
    for model_id in (SD_IMAGE_MODEL_ID, SD_IMAGE_FALLBACK_MODEL_ID):
        symbol = _invoke_stability(prompt, SD_LOGO_NEGATIVE_PROMPT, model_id, region, "Logo")
        if symbol:
            break
    if not symbol:
        print("[Logo] all attempts failed")
        return None

    try:
        logo_no_text = symbol_only_logo_image(symbol)
        print("[Logo] symbol only (no text) ok")
        return logo_no_text
    except Exception as e:
        print(f"[Logo] symbol_only_logo_image failed: {e}")
        return symbol


def _logo_transparent_background(img):
    """PNG sin fondo: white and near-white pixels → transparent so logo adheres to product."""
    img = img.convert("RGBA")
    data = list(img.getdata())
    thresh = 238  # slightly below 245 so light halos become transparent
    out = []
    for item in data:
        r, g, b, a = item
        lum = (r * 299 + g * 587 + b * 114) / 1000
        out.append((r, g, b, 0 if lum >= thresh else 255))
    img.putdata(out)
    return img


def overlay_logo_on_product(product_image_bytes: bytes, logo_image_bytes: bytes) -> bytes:
    """
    Overlay the logo on the product: PNG sin fondo, in the "label zone" (center).
    Logo position is clamped so it never goes outside the image; product prompt
    asks for consistent centered composition so the logo always lands on the product.
    """
    from PIL import Image, ImageFilter

    product = Image.open(io.BytesIO(product_image_bytes)).convert("RGBA")
    logo = Image.open(io.BytesIO(logo_image_bytes)).convert("RGBA")
    logo = _logo_transparent_background(logo)

    w, h = product.size
    margin = max(4, w // 64)
    logo_w = min(int(w * 0.24), w - 2 * margin)
    logo_h = min(int(logo_w * logo.height / logo.width), h - 2 * margin)
    logo = logo.resize((logo_w, logo_h), Image.LANCZOS)

    # Label zone: center of frame (product prompt asks for product centered)
    lx = (w - logo_w) // 2
    ly = int(h * 0.46)
    lx = max(margin, min(lx, w - logo_w - margin))
    ly = max(margin, min(ly, h - logo_h - margin))

    # Subtle drop shadow so logo reads on any packaging and looks adhered
    shadow_offset = max(2, w // 256)
    logo_data = list(logo.getdata())
    shadow_data = [(0, 0, 0, min(90, int(a * 0.45))) for r, g, b, a in logo_data]
    shadow = Image.new("RGBA", (logo_w, logo_h), (0, 0, 0, 0))
    shadow.putdata(shadow_data)
    try:
        shadow = shadow.filter(ImageFilter.GaussianBlur(radius=max(2, w // 180)))
    except Exception:
        pass
    sx, sy = lx + shadow_offset, ly + shadow_offset
    if sx >= 0 and sy >= 0 and sx + logo_w <= w and sy + logo_h <= h:
        product.paste(shadow, (sx, sy), shadow)
    product.paste(logo, (lx, ly), logo)

    buf = io.BytesIO()
    product.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


def _generate_product_image_with_model(
    product_name: str,
    brand_name: str,
    image_prompt: str,
    model_id: str,
    region: str,
) -> Optional[bytes]:
    """Generate one product image (text-to-image, no init)."""
    import boto3

    product_name_safe = (product_name or "Product").strip()
    brand_name_safe = (brand_name or "Brand").strip()
    image_prompt_safe = (image_prompt or "Product packaging, professional shot.").strip()
    style_preset = _get_style_preset(brand_name_safe)

    prompt = SD_PRODUCT_PROMPT_TEMPLATE.format(
        product_name=product_name_safe,
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
    logo_bytes: Optional[bytes] = None,
) -> Optional[bytes]:
    """
    Product image: always text-to-image (full product photo, professional). Then overlay logo + text bar.
    Image-to-image with logo as init was producing tiny/no product; text-to-image keeps product visible.
    """
    region = BEDROCK_IMAGE_REGION
    raw: Optional[bytes] = None

    # 1) Always use text-to-image so the product is a proper, visible product shot
    try:
        raw = _generate_product_image_with_model(
            product_name, brand_name, image_prompt, SD_IMAGE_MODEL_ID, region,
        )
        if raw is not None:
            print(f"[Product] text-to-image ok with {SD_IMAGE_MODEL_ID}")
    except Exception as e:
        print(f"[Product] primary error: {e}")
        raw = None
    if raw is None:
        try:
            raw = _generate_product_image_with_model(
                product_name, brand_name, image_prompt, SD_IMAGE_FALLBACK_MODEL_ID, region,
            )
            if raw is not None:
                print(f"[Product] text-to-image ok with fallback")
        except Exception as e:
            print(f"[Product] fallback error: {e}")

    if raw is None:
        print("[Product] all attempts failed")
        return None

    # 2) Overlay logo (symbol only) so it's clearly visible on the product
    if logo_bytes:
        try:
            raw = overlay_logo_on_product(raw, logo_bytes)
            print(f"[Product] logo overlay applied for '{product_name}'")
        except Exception as e:
            print(f"[Product] logo overlay skipped for '{product_name}': {e}")

    try:
        out = _overlay_branding_text(raw, brand_name, product_name)
        print(f"[Product] text overlay applied for '{product_name}'")
        return out
    except Exception as e:
        print(f"[Product] text overlay failed, returning raw: {e}")
        return raw


def generate_images_parallel(
    product_ideas: List[dict],
    brand_name: str,
    bedrock_client=None,
    max_workers: int = 5,
    logo_bytes: Optional[bytes] = None,
) -> List[Optional[bytes]]:
    """Generate product images in parallel. Each: product photo + logo overlay (clear) + text bar."""
    brand_name = brand_name or ""
    results: List[Optional[bytes]] = [None] * len(product_ideas)

    def task(i: int, idea: dict) -> tuple:
        name = idea.get("product_name") or ""
        prompt = idea.get("image_prompt") or ""
        start = time.time()
        img = generate_product_image(name, brand_name, prompt, bedrock_client, logo_bytes)
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
