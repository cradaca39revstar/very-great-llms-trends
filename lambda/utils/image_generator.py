"""
Titan Image Generator Module (V2).
Generates product concept images via Amazon Titan Image Generator v2.
"""

import base64
import json
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

# Logo: minimal, elegant brand mark (Titan works best with clear product/photography prompts; logo is stylized)
TITAN_LOGO_PROMPT_TEMPLATE = """Minimal luxury brand logo for "{brand_name}". {tagline}
Clean, elegant wordmark or symbol, premium beauty or skincare brand, white or soft gradient background, professional, high-end, 4K quality."""


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
    Generate a brand logo image using Titan Image Generator v2.
    Returns decoded PNG bytes or None on failure.
    """
    prompt = TITAN_LOGO_PROMPT_TEMPLATE.format(
        brand_name=brand_name or "Brand",
        tagline=f"Tagline: {brand_tagline}" if brand_tagline else "Luxury brand identity.",
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
