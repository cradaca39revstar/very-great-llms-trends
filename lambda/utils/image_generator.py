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
_BRAND_ICON_MAP = [
    (["nature", "terra", "green", "eco", "natural", "organic", "botan", "herb", "plant"],
     "a golden leaf logo printed on"),
    (["royal", "crown", "king", "queen", "regal", "majest", "noble"],
     "a golden crown logo printed on"),
    (["star", "celeste", "sky", "luna", "stella", "astral", "cosmic"],
     "a golden five-pointed star logo printed on"),
    (["ocean", "aqua", "marine", "wave", "sea", "tide", "coral"],
     "a silver water droplet logo printed on"),
    (["aura", "glow", "light", "lux", "lumina", "illumina", "radi", "bright", "lumin"],
     "a golden sunburst circle logo printed on"),
    (["silk", "soft", "velvet", "smooth", "satin", "petal", "blossom", "flora", "bloom"],
     "a golden lotus flower logo printed on"),
    (["derma", "derm", "skin", "clinic", "medic", "pharm", "scienc"],
     "a silver geometric hexagon logo printed on"),
    (["hydra", "moist", "dew", "fresh", "rain", "mist", "spring"],
     "a silver water droplet logo printed on"),
    (["pure", "zen", "calm", "serene", "tranquil", "balance", "harmony"],
     "a golden mandala circle logo printed on"),
    (["vita", "vital", "energy", "power", "boost", "reviv", "renew", "rejuv"],
     "a golden rising sun logo printed on"),
    (["luxe", "luxury", "elegant", "premium", "prestige", "opul"],
     "a golden diamond logo printed on"),
    (["curl", "wave", "coil", "spiral", "twist", "strand", "lock"],
     "a golden spiral logo printed on"),
    (["shield", "protect", "guard", "defense", "barrier", "armor"],
     "a silver shield logo printed on"),
    (["honey", "gold", "amber", "nectar", "bee"],
     "a golden honeycomb hexagon logo printed on"),
    (["crystal", "gem", "jewel", "prism", "clear", "glass"],
     "a silver crystal prism logo printed on"),
    (["moon", "night", "noir", "midnight", "eclipse"],
     "a silver crescent moon logo printed on"),
    (["fire", "flame", "heat", "warm", "blaze", "ember"],
     "a golden flame logo printed on"),
    (["feather", "air", "breeze", "cloud", "float", "wind"],
     "a silver feather logo printed on"),
]

_DEFAULT_FALLBACK_ICONS = [
    "a golden sunburst circle logo printed on",
    "a golden five-pointed star logo printed on",
    "a golden diamond logo printed on",
    "a silver geometric hexagon logo printed on",
    "a golden rising sun logo printed on",
    "a silver crystal prism logo printed on",
]

_CATEGORY_FALLBACK_ICONS = {
    "skincare": [
        "a golden sunburst circle logo printed on",
        "a golden lotus flower logo printed on",
        "a silver geometric hexagon logo printed on",
        "a golden mandala circle logo printed on",
        "a golden diamond logo printed on",
        "a silver water droplet logo printed on",
    ],
    "haircare & styling": [
        "a golden spiral logo printed on",
        "a golden leaf logo printed on",
        "a golden five-pointed star logo printed on",
        "a golden rising sun logo printed on",
        "a silver feather logo printed on",
        "a silver crystal prism logo printed on",
    ],
}


def get_logo_icon(brand_name: str, l2_category: str = "") -> str:
    """
    Return a concrete, drawable icon for the logo. Geometric, elegant, and related
    to the brand name and category. If no keyword matches the brand, picks from a
    category-specific pool using a hash of the brand name for deterministic variety.
    """
    name = (brand_name or "").lower().replace("haircare", "").replace("hair", "").strip()

    for keywords, icon in _BRAND_ICON_MAP:
        if any(w in name for w in keywords):
            return icon

    cat = (l2_category or "").lower()
    pool = _CATEGORY_FALLBACK_ICONS.get(cat, _DEFAULT_FALLBACK_ICONS)
    idx = hash(brand_name or "") % len(pool)
    return pool[idx]


def _get_style_preset(brand_name: str) -> str:
    name = (brand_name or "").lower()
    if any(w in name for w in ["tech", "digital", "modern", "future"]):
        return "digital-art"
    if any(w in name for w in ["luxury", "premium", "elegant", "royal"]):
        return "line-art"
    if any(w in name for w in ["organic", "natural", "eco"]):
        return "analog-film"
    return "line-art"


def _extract_packaging_keywords(ref: str) -> str:
    """
    Detect non-bottle packaging keywords in product name (lowercase).
    Returns the most relevant phrase (e.g. 'sonic toothbrush', 'heating pad') or '' if none.
    """
    if not ref or not isinstance(ref, str):
        return ""
    r = ref.lower().strip()
    # Compound phrases first (most specific)
    if "sonic" in r and "toothbrush" in r:
        return "sonic toothbrush"
    if "heating" in r and "pad" in r:
        return "heating pad"
    if "face" in r and "mask" in r:
        return "face mask"
    if "sheet" in r and "mask" in r:
        return "sheet mask"
    if "body" in r and "wrap" in r:
        return "body wrap"
    if "eye" in r and "patch" in r:
        return "eye patch"
    if "lip" in r and "patch" in r:
        return "lip patch"
    if "roll-on" in r:
        return "roll-on"
    # Single-word / device/appliance non-bottle packaging
    if "toothbrush" in r or "flosser" in r:
        return "toothbrush"
    if "trimmer" in r or "razor" in r:
        return "razor or trimmer"
    if "plush" in r:
        return "plush"
    if "pad" in r:
        return "heating pad"
    if "mask" in r:
        return "face mask"
    if "wrap" in r:
        return "body wrap"
    if "patch" in r:
        return "patch"
    if "wipe" in r:
        return "wipe"
    if "sheet" in r:
        return "sheet mask"
    if "stick" in r:
        return "stick"
    if "sponge" in r:
        return "sponge"
    if "device" in r or "appliance" in r:
        return "beauty device"
    if "brush" in r and ("makeup" in r or "cosmetic" in r or "lip" in r or "eye" in r):
        return "cosmetic brush"
    if "kit" in r:
        return "kit"
    if "pack" in r:
        return "pack"
    if "tool" in r:
        return "beauty tool"
    return ""


def _get_product_type_phrase(
    l2_category: str,
    product_name: str = "",
    top_product_name: str = "",
) -> str:
    """Return the main product PACKAGING phrase (physical object with label). Same idea in all categories: product + logo."""
    ref = (top_product_name or product_name or "").lower()
    cat = (l2_category or "").lower().strip()
    if "makeup" in cat or "cosmetic" in cat or any(w in ref for w in ["lip", "mascara", "eye", "gloss", "compact", "blush", "eyeshadow"]):
        return "luxury makeup packaging (lipstick tube, mascara tube, or cosmetic compact case) with"
    if "hair" in cat or "beard" in cat or "grooming" in cat or any(w in ref for w in ["hair", "beard", "conditioner", "serum", "scalp"]):
        return "luxury haircare bottle with"
    packaging_kw = _extract_packaging_keywords(ref)
    if packaging_kw:
        return f"luxury {packaging_kw} with"
    cat_label = cat if cat else "beauty care"
    return f"luxury {cat_label} product bottle with"


def _get_default_visual_desc(
    l2_category: str,
    product_name: str = "",
    product_description: str = "",
    top_product_name: str = "",
) -> str:
    """Default: physical product packaging on clean background. Never applied makeup or person."""
    cat = (l2_category or "").lower().strip()
    desc = (product_description or "").strip()
    ref = (top_product_name or product_name or "").lower()
    if "makeup" in cat or "cosmetic" in cat or any(w in ref for w in ["lip", "mascara", "eye", "gloss", "compact"]):
        base = "physical makeup packaging (tube or compact) on clean white background, product shot only, luxury cosmetic aesthetic"
    elif "hair" in cat or "beard" in cat or "grooming" in cat or any(w in ref for w in ["hair", "beard", "conditioner", "scalp"]):
        base = "physical haircare bottle on clean white background, product shot only, luxury cosmetic aesthetic"
    else:
        packaging_kw = _extract_packaging_keywords(ref)
        if packaging_kw:
            base = f"physical {packaging_kw} on clean white background, product shot only, luxury aesthetic"
        else:
            cat_label = cat if cat else "beauty care"
            base = f"physical {cat_label} product bottle on clean white background, product shot only, luxury cosmetic aesthetic"
    if desc:
        short = desc[:120].strip()
        if short:
            base = f"{base}. Visual style: {short}"
    return base


# ============================================================================
# Holistic product prompt — product + packaging + logo icon + brand name
# ============================================================================
SD_PRODUCT_NEGATIVE_PROMPT = (
    "no icon, no logo, missing logo, invisible logo, plain bottle without icon, "
    "bare bottle, blank label, empty label, label with only text, text-only label, "
    "duplicate brand name, repeated brand name, repeated text, brand name in two places, "
    "flat label, pasted label, badly photoshopped, "
    "cluttered design, low quality, blurry text, blur, distorted, "
    "cartoon, illustration, drawing, amateur, "
    "lips, face, model, person, woman, man, applied makeup, makeup on skin, close-up of face, face shot, portrait, human, "
    "face in logo, face in sunburst, sunburst with face, human face in icon, logo with face, "
    "sunburst as separate object, floating sunburst, floating icon, logo floating, decorative object separate from product, sunburst next to product"
)


def build_product_prompt(
    brand_name: str,
    product_name: str,
    image_prompt: str = "",
    key_ingredients: Optional[List[str]] = None,
    l2_category: str = "",
    product_description: str = "",
    top_product_name: str = "",
) -> str:
    """
    Build a holistic SD 3.5 prompt. Product type and default visual depend on
    l2_category, product description, and top #1 market product for focus.
    """
    brand = (brand_name or "Brand").strip()
    product = (product_name or "Product").strip()
    cat = (l2_category or "").lower().strip()
    top_name = (top_product_name or "").strip()

    if image_prompt and image_prompt.strip():
        visual_desc = image_prompt.strip()
    else:
        visual_desc = _get_default_visual_desc(cat, product, product_description or "", top_name)

    product_type_phrase = _get_product_type_phrase(cat, product, top_name)
    logo_icon = get_logo_icon(brand, l2_category)
    style_preset = _get_style_preset(brand)

    benefit_line = ""
    if key_ingredients:
        top = [k.strip() for k in key_ingredients[:3] if k and k.strip()]
        if top:
            benefit_line = f" ({', '.join(top)})"

    packaging_line = (
        "The label wraps naturally around the bottle with realistic curvature."
        if "bottle" in product_type_phrase
        else "Elegant packaging with clear, minimal branding."
    )

    prompt = (
        f"Physical product packaging only. A {product_type_phrase} {logo_icon} the front label. "
        f"The logo icon is large, centered, and clearly visible on the label. "
        f"Below the icon, the brand name \"{brand}\" in elegant typography, once. "
        f"Below that, \"{product}\"{benefit_line} in smaller text. "
        f"Professional product photography, {visual_desc}. "
        f"{packaging_line} "
        f"No other text or branding anywhere else on the packaging. "
        f"Clean minimal design, soft studio lighting, {style_preset} style, photorealistic, 4K. "
        f"Product packaging only, no person no face. Logo and brand name clearly visible on the packaging."
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
    l2_category: str = "",
    product_description: str = "",
    top_product_name: str = "",
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
        l2_category=l2_category,
        product_description=product_description,
        top_product_name=top_product_name,
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
    l2_category: str = "",
    top_product_name: str = "",
) -> List[Optional[bytes]]:
    """Generate holistic product images in parallel via SD 3.5 Large. Focused on top #1 market product."""
    brand_name = brand_name or ""
    results: List[Optional[bytes]] = [None] * len(product_ideas)

    def task(i: int, idea: dict) -> tuple:
        name = idea.get("product_name") or ""
        prompt = idea.get("image_prompt") or ""
        description = idea.get("description") or ""
        ingredients = idea.get("key_ingredients") if isinstance(idea.get("key_ingredients"), list) else None
        start = time.time()
        img = generate_product_image(
            name, brand_name, prompt, None, ingredients, l2_category,
            product_description=description,
            top_product_name=top_product_name,
        )
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


# ============================================================================
# Tests — product type and visual desc (run: python image_generator.py)
# ============================================================================
if __name__ == "__main__":
    # 1. fragrance → "luxury fragrance product bottle with"
    out = _get_product_type_phrase("fragrance", "")
    assert out == "luxury fragrance product bottle with", f"got: {out}"

    # 2. nails + Essie Nail Polish Set → "luxury nails product bottle with"
    out = _get_product_type_phrase("nails", "Essie Nail Polish Set")
    assert out == "luxury nails product bottle with", f"got: {out}"

    # 3. special personal care + Heating Pad Plush → "luxury heating pad with"
    out = _get_product_type_phrase("special personal care", "Squishmallows Heating Pad Microwavable Plush")
    assert out == "luxury heating pad with", f"got: {out}"

    # 4. makeup + tarte lip gloss → original makeup branch
    out = _get_product_type_phrase("makeup", "tarte lip gloss")
    assert out == "luxury makeup packaging (lipstick tube, mascara tube, or cosmetic compact case) with", f"got: {out}"

    # 5. empty cat + empty name → "luxury beauty care product bottle with"
    out = _get_product_type_phrase("", "")
    assert out == "luxury beauty care product bottle with", f"got: {out}"

    # 6. Personal Care Appliances + sonic toothbrush → "luxury sonic toothbrush with"
    out = _get_product_type_phrase("Personal Care Appliances", "AquaPure Luxe Sonic Toothbrush")
    assert out == "luxury sonic toothbrush with", f"got: {out}"

    print("All 6 _get_product_type_phrase tests passed.")
