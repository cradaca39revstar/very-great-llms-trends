"""
Image helpers for Lambda (thumbnails for API response; full size used in PDF).
Uses Pillow when available.
"""

import base64
from collections import deque
from io import BytesIO
from statistics import median
from typing import Optional

try:
    from PIL import Image, ImageFilter
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False


def _color_dist(c1: tuple, c2: tuple) -> float:
    return ((c1[0] - c2[0]) ** 2 + (c1[1] - c2[1]) ** 2 + (c1[2] - c2[2]) ** 2) ** 0.5


def logo_remove_background(image_bytes: Optional[bytes]) -> Optional[bytes]:
    """
    Remove background from a logo so only the symbol shows (transparent PNG).
    Uses median of edge pixels + conservative tolerance to preserve symbol details.
    Falls back to border flood-fill if median-based removal leaves too little content.
    """
    if not _PIL_AVAILABLE or not image_bytes:
        return None
    try:
        img = Image.open(BytesIO(image_bytes)).convert("RGB")
        w, h = img.size
        if w < 2 or h < 2:
            return None
        pixels = img.load()
        # 1) Median of edge pixels (conservative background color)
        edge_r, edge_g, edge_b = [], [], []
        step = max(1, w // 30)
        for x in range(0, w, step):
            c = pixels[x, 0]
            edge_r.append(c[0])
            edge_g.append(c[1])
            edge_b.append(c[2])
            c = pixels[x, h - 1]
            edge_r.append(c[0])
            edge_g.append(c[1])
            edge_b.append(c[2])
        step = max(1, h // 30)
        for y in range(0, h, step):
            c = pixels[0, y]
            edge_r.append(c[0])
            edge_g.append(c[1])
            edge_b.append(c[2])
            c = pixels[w - 1, y]
            edge_r.append(c[0])
            edge_g.append(c[1])
            edge_b.append(c[2])
        bg_r, bg_g, bg_b = int(median(edge_r)), int(median(edge_g)), int(median(edge_b))
        # 2) Conservative tolerance (40) to preserve symbol details
        tolerance = 40
        out = Image.new("RGBA", (w, h))
        out_pixels = out.load()
        for y in range(h):
            for x in range(w):
                r, g, b = pixels[x, y]
                is_bg = (
                    abs(r - bg_r) <= tolerance
                    and abs(g - bg_g) <= tolerance
                    and abs(b - bg_b) <= tolerance
                )
                if is_bg:
                    out_pixels[x, y] = (r, g, b, 0)
                else:
                    out_pixels[x, y] = (r, g, b, 255)
        # If almost nothing left (e.g. gradient), use flood-fill from border
        opaque_count = sum(1 for y in range(h) for x in range(w) if out_pixels[x, y][3] == 255)
        if opaque_count < 50:
            out = Image.new("RGBA", (w, h))
            out_pixels = out.load()
            q = deque()
            for x in range(w):
                q.append((x, 0))
                q.append((x, h - 1))
            for y in range(1, h - 1):
                q.append((0, y))
                q.append((w - 1, y))
            is_bg = [[True] * w for _ in range(h)]
            for x, y in q:
                is_bg[y][x] = True
            while q:
                x, y = q.popleft()
                c0 = pixels[x, y]
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w and 0 <= ny < h and not is_bg[ny][nx]:
                        if _color_dist(c0, pixels[nx, ny]) <= 28:
                            is_bg[ny][nx] = True
                            q.append((nx, ny))
            for y in range(h):
                for x in range(w):
                    r, g, b = pixels[x, y]
                    out_pixels[x, y] = (r, g, b, 0 if is_bg[y][x] else 255)
        # 3) Invert if logo is mostly light so it's visible on white
        visible_lum = []
        for y in range(h):
            for x in range(w):
                if out_pixels[x, y][3] == 255:
                    r, g, b = out_pixels[x, y][0], out_pixels[x, y][1], out_pixels[x, y][2]
                    visible_lum.append((r + g + b) / 3)
        if visible_lum and sum(visible_lum) / len(visible_lum) > 170:
            for y in range(h):
                for x in range(w):
                    if out_pixels[x, y][3] == 255:
                        r, g, b, a = out_pixels[x, y]
                        out_pixels[x, y] = (255 - r, 255 - g, 255 - b, 255)
        # 4) Light alpha smoothing to preserve crisp edges
        alpha = out.getchannel("A")
        out.putalpha(alpha.filter(ImageFilter.GaussianBlur(radius=0.5)))
        buf = BytesIO()
        out.save(buf, format="PNG", optimize=True)
        return buf.getvalue()
    except Exception:
        return None


def logo_to_thumbnail_base64(image_bytes: Optional[bytes], size: int = 256) -> Optional[str]:
    """
    Resize logo (PNG with alpha) to thumbnail, keep transparency. Returns base64 PNG string.
    Use for brand logo so chat shows logo without background.
    """
    if not _PIL_AVAILABLE:
        print("[image_utils] logo_to_thumbnail_base64: PIL not available")
        return None
    if not image_bytes:
        return None
    try:
        img = Image.open(BytesIO(image_bytes))
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        img.thumbnail((size, size), Image.LANCZOS)
        out = BytesIO()
        img.save(out, format="PNG")
        return base64.b64encode(out.getvalue()).decode("ascii")
    except Exception as e:
        print(f"[image_utils] logo_to_thumbnail_base64 failed: {e}")
        return None


def image_bytes_to_thumbnail_base64(
    image_bytes: Optional[bytes],
    size: int = 256,
    output_format: str = "jpeg",
    quality: int = 85,
) -> Optional[str]:
    """
    Resize image to a square thumbnail and return as base64 string.
    output_format: "jpeg" (smaller) or "png" (crisper, no compression artifacts).
    quality: used only when output_format="jpeg". Use 95 for sharper text/edges.
    Returns None if Pillow unavailable or resize fails.
    """
    if not _PIL_AVAILABLE:
        print("[image_utils] image_bytes_to_thumbnail_base64: PIL not available")
        return None
    if not image_bytes:
        return None
    try:
        img = Image.open(BytesIO(image_bytes))
        img = img.convert("RGB")
        img.thumbnail((size, size), Image.LANCZOS)
        out = BytesIO()
        if output_format.lower() == "png":
            img.save(out, format="PNG")
        else:
            img.save(out, format="JPEG", quality=min(100, max(1, quality)))
        return base64.b64encode(out.getvalue()).decode("ascii")
    except Exception as e:
        print(f"[image_utils] image_bytes_to_thumbnail_base64 failed: {e}")
        return None
