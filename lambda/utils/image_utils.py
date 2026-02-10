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


def logo_remove_background(image_bytes: Optional[bytes]) -> Optional[bytes]:
    """
    Remove grey/gradient background from a logo so only the logo shows (transparent PNG).
    Samples all edge pixels to detect background; removes any pixel that matches the
    gradient (grey tones) or is close to edge colors. Returns PNG bytes with alpha.
    """
    if not _PIL_AVAILABLE or not image_bytes:
        return None
    try:
        img = Image.open(BytesIO(image_bytes)).convert("RGB")
        w, h = img.size
        if w < 2 or h < 2:
            return None
        pixels = img.load()
        # Sample full perimeter (gradient can vary corner to corner)
        edge_colors = []
        for x in range(0, w, max(1, w // 20)):
            edge_colors.append(pixels[x, 0])
            edge_colors.append(pixels[x, h - 1])
        for y in range(0, h, max(1, h // 20)):
            edge_colors.append(pixels[0, y])
            edge_colors.append(pixels[w - 1, y])
        n = len(edge_colors)
        bg_r = sum(c[0] for c in edge_colors) // n
        bg_g = sum(c[1] for c in edge_colors) // n
        bg_b = sum(c[2] for c in edge_colors) // n
        # Pixel is background if: (1) close to average edge color, OR (2) grey in mid range (not white/black logo)
        dist_threshold = 85
        out = Image.new("RGBA", (w, h))
        out_pixels = out.load()
        for y in range(h):
            for x in range(w):
                r, g, b = pixels[x, y]
                luminance = (r + g + b) / 3
                spread = max(r, g, b) - min(r, g, b)
                dist = ((r - bg_r) ** 2 + (g - bg_g) ** 2 + (b - bg_b) ** 2) ** 0.5
                is_edge_like = dist <= dist_threshold
                # Remove grey gradient; keep white (luminance > 240) and dark (luminance < 90) as logo
                is_mid_grey = spread <= 55 and 90 <= luminance <= 238
                if is_edge_like or is_mid_grey:
                    out_pixels[x, y] = (r, g, b, 0)
                else:
                    out_pixels[x, y] = (r, g, b, 255)
        # If logo content is mostly white/light, invert so it's visible on light backgrounds
        visible_lum = []
        for y in range(h):
            for x in range(w):
                if out_pixels[x, y][3] == 255:
                    r, g, b, a = out_pixels[x, y]
                    visible_lum.append((r + g + b) / 3)
        if visible_lum:
            avg_lum = sum(visible_lum) / len(visible_lum)
            if avg_lum > 195:
                for y in range(h):
                    for x in range(w):
                        r, g, b, a = out_pixels[x, y]
                        if a == 255:
                            out_pixels[x, y] = (255 - r, 255 - g, 255 - b, 255)
        buf = BytesIO()
        out.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return None


def logo_to_thumbnail_base64(image_bytes: Optional[bytes], size: int = 256) -> Optional[str]:
    """
    Resize logo (PNG with alpha) to thumbnail, keep transparency. Returns base64 PNG string.
    Use for brand logo so chat shows logo without background.
    """
    if not _PIL_AVAILABLE or not image_bytes:
        return None
    try:
        img = Image.open(BytesIO(image_bytes))
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        img.thumbnail((size, size), Image.LANCZOS)
        out = BytesIO()
        img.save(out, format="PNG")
        return base64.b64encode(out.getvalue()).decode("ascii")
    except Exception:
        return None


def image_bytes_to_thumbnail_base64(image_bytes: Optional[bytes], size: int = 256) -> Optional[str]:
    """
    Resize image to a square thumbnail and return as base64 string (JPEG).
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
