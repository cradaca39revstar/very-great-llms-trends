"""
Image helpers for Lambda (thumbnails for API response; full size used in PDF).
Uses Pillow when available.
"""

import base64
from io import BytesIO
from typing import Optional

try:
    from PIL import Image
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False


def image_bytes_to_thumbnail_base64(image_bytes: Optional[bytes], size: int = 256) -> Optional[str]:
    """
    Resize image to a square thumbnail and return as base64 string.
    Keeps response payload small so frontend can show images without timeout.
    Returns None if Pillow unavailable or resize fails.
    """
    if not _PIL_AVAILABLE or not image_bytes:
        return None
    try:
        img = Image.open(BytesIO(image_bytes))
        img = img.convert("RGB")
        img.thumbnail((size, size), Image.LANCZOS)
        out = BytesIO()
        img.save(out, format="JPEG", quality=85)
        return base64.b64encode(out.getvalue()).decode("ascii")
    except Exception:
        return None
