"""
Multi-Modal Visual Grounding and Freshness-Tracked Set-of-Marks (SoM).

Provides:
- Generation-tracked Mark Registry with UUIDs and expiration TTL.
- Fusion of Apple Vision OCR and native macOS Accessibility UI elements.
- Rejection of stale marks (prevents executing actions on outdated screenshots).
- High-contrast visual rendering with pill tags and bounding boxes.
"""

from __future__ import annotations
import base64
import io
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


class MarkNotFoundError(RuntimeError):
    """Raised when an agent attempts to click or interact with an unknown mark ID."""
    pass


class StaleObservationError(RuntimeError):
    """Raised when an agent attempts to execute an action on an expired observation."""
    pass


class GroundedMarkRegistry:
    """Manages ground-truth element marks, tracking creation time and screen UUIDs."""

    def __init__(self, ttl_seconds: float = 30.0):
        self.registry_id: str = str(uuid.uuid4())
        self.created_at: float = time.time()
        self.ttl_seconds: float = ttl_seconds
        self.marks: Dict[int, Dict[str, Any]] = {}
        self.screen_width: int = 1440
        self.screen_height: int = 900
        self.scale_ratio: float = 2.0

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > self.ttl_seconds

    @property
    def age(self) -> float:
        return time.time() - self.created_at

    def register(self, mark_id: int, element_data: Dict[str, Any]) -> None:
        self.marks[mark_id] = element_data

    def get_mark(self, mark_id: Union[int, str], enforce_freshness: bool = True) -> Dict[str, Any]:
        if enforce_freshness and self.is_expired:
            raise StaleObservationError(
                f"Observation registry {self.registry_id} has expired (age: {self.age:.1f}s, TTL: {self.ttl_seconds}s). "
                "The screen state may have changed; a fresh observation must be captured before interacting."
            )
        try:
            m_id = int(mark_id)
        except ValueError:
            raise MarkNotFoundError(f"Invalid non-integer mark ID '{mark_id}'.")

        if m_id not in self.marks:
            available = list(self.marks.keys())[:15]
            raise MarkNotFoundError(
                f"Mark #{m_id} not found in active registry {self.registry_id}. "
                f"Available marks (sample): {available} (Total: {len(self.marks)})"
            )
        return self.marks[m_id]

    def to_summary(self) -> Dict[str, Any]:
        return {
            "registry_id": self.registry_id,
            "created_at": self.created_at,
            "age_seconds": round(self.age, 2),
            "ttl_seconds": self.ttl_seconds,
            "is_expired": self.is_expired,
            "element_count": len(self.marks),
            "marks": self.marks,
        }


def fuse_and_render_som(
    image: Union[str, Image.Image],
    ocr_results: Optional[Dict[str, Any]] = None,
    ax_elements: Optional[List[Dict[str, Any]]] = None,
    scale_factor: float = 2.0,
    ttl_seconds: float = 30.0,
    outline_color: str = "#E63946",
    badge_bg: str = "#1D3557",
    badge_text_color: str = "#FFFFFF",
) -> Tuple[Image.Image, GroundedMarkRegistry]:
    """
    Fuses Accessibility tree nodes and OCR bounding boxes into a unified grounded registry,
    and draws high-contrast numbered badges onto the image.
    """
    if not PIL_AVAILABLE:
        raise ImportError("PIL (Pillow) is required for Set-of-Marks rendering.")

    if isinstance(image, str):
        img = Image.open(image).convert("RGBA")
    else:
        img = image.copy().convert("RGBA")

    overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)

    font_size = max(11, int(12 * scale_factor))
    font = None
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
    except Exception:
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None

    registry = GroundedMarkRegistry(ttl_seconds=ttl_seconds)
    registry.scale_ratio = scale_factor
    registry.screen_width = int(img.width / scale_factor)
    registry.screen_height = int(img.height / scale_factor)

    mark_id = 1
    seen_centers: Set[Tuple[int, int]] = set()

    # 1. Process Accessibility Elements First (highest semantic value)
    if ax_elements:
        for elem in ax_elements:
            bounds = elem.get("bounds", {})
            bx = bounds.get("x", 0)
            by = bounds.get("y", 0)
            bw = bounds.get("width", 0)
            bh = bounds.get("height", 0)
            cx = elem.get("center_x", bx + bw // 2)
            cy = elem.get("center_y", by + bh // 2)

            if bw <= 4 or bh <= 4:
                continue

            center_key = (cx // 10, cy // 10)
            if center_key in seen_centers:
                continue
            seen_centers.add(center_key)

            # Draw
            px0 = int(bx * scale_factor)
            py0 = int(by * scale_factor)
            px1 = int((bx + bw) * scale_factor)
            py1 = int((by + bh) * scale_factor)

            draw.rectangle([px0, py0, px1, py1], outline=outline_color, width=max(1, int(1.5 * scale_factor)))

            # Badge
            badge_text = str(mark_id)
            pad_x = int(4 * scale_factor)
            pad_y = int(2 * scale_factor)
            tw = len(badge_text) * 8
            th = 12
            if font and hasattr(font, "getbbox"):
                bbox = font.getbbox(badge_text)
                tw = bbox[2] - bbox[0]
                th = bbox[3] - bbox[1]

            badge_w = tw + pad_x * 2
            badge_h = th + pad_y * 2
            b_x0 = max(0, px0)
            b_y0 = max(0, py0 - badge_h)
            b_x1 = b_x0 + badge_w
            b_y1 = b_y0 + badge_h

            draw.rounded_rectangle([b_x0, b_y0, b_x1, b_y1], radius=int(3 * scale_factor), fill=badge_bg)
            draw.text((b_x0 + pad_x, b_y0 + pad_y), badge_text, fill=badge_text_color, font=font)

            registry.register(mark_id, {
                "id": mark_id,
                "type": elem.get("role", "UIElement"),
                "title": elem.get("title", ""),
                "value": elem.get("value"),
                "enabled": elem.get("enabled", True),
                "center_x": cx,
                "center_y": cy,
                "bounds": bounds,
                "source": "accessibility",
                "confidence": 1.0,
            })
            mark_id += 1

    # 2. Complement with OCR text elements
    if ocr_results:
        for line in ocr_results.get("lines", []):
            text = line.get("text", "").strip()
            box = line.get("box", {})
            bx = box.get("x", 0)
            by = box.get("y", 0)
            bw = box.get("width", 0)
            bh = box.get("height", 0)
            cx = box.get("center_x", bx + bw // 2)
            cy = box.get("center_y", by + bh // 2)

            if not text or bw <= 4 or bh <= 4:
                continue

            center_key = (cx // 10, cy // 10)
            if center_key in seen_centers:
                continue
            seen_centers.add(center_key)

            # Draw
            px0 = int(bx * scale_factor)
            py0 = int(by * scale_factor)
            px1 = int((bx + bw) * scale_factor)
            py1 = int((by + bh) * scale_factor)

            draw.rectangle([px0, py0, px1, py1], outline="#457B9D", width=max(1, int(1.2 * scale_factor)))

            # Badge
            badge_text = str(mark_id)
            pad_x = int(4 * scale_factor)
            pad_y = int(2 * scale_factor)
            tw = len(badge_text) * 8
            th = 12
            if font and hasattr(font, "getbbox"):
                bbox = font.getbbox(badge_text)
                tw = bbox[2] - bbox[0]
                th = bbox[3] - bbox[1]

            badge_w = tw + pad_x * 2
            badge_h = th + pad_y * 2
            b_x0 = max(0, px0)
            b_y0 = max(0, py0 - badge_h)
            b_x1 = b_x0 + badge_w
            b_y1 = b_y0 + badge_h

            draw.rounded_rectangle([b_x0, b_y0, b_x1, b_y1], radius=int(3 * scale_factor), fill="#E63946")
            draw.text((b_x0 + pad_x, b_y0 + pad_y), badge_text, fill="#FFFFFF", font=font)

            registry.register(mark_id, {
                "id": mark_id,
                "type": "Text",
                "title": text,
                "text": text,
                "value": None,
                "enabled": True,
                "center_x": cx,
                "center_y": cy,
                "bounds": box,
                "box": box,
                "source": "ocr",
                "confidence": line.get("confidence", 0.95),
            })
            mark_id += 1

    combined = Image.alpha_composite(img, overlay).convert("RGB")
    return combined, registry


def create_som_overlay(
    image: Union[str, Image.Image],
    ocr_results: Optional[Dict[str, Any]] = None,
    scale_factor: float = 2.0,
    outline_color: str = "#E63946",
    badge_bg: str = "#1D3557",
    badge_text_color: str = "#FFFFFF",
) -> Tuple[Image.Image, Dict[int, Dict[str, Any]]]:
    """Backward compatibility wrapper for legacy callers."""
    annotated_img, registry = fuse_and_render_som(
        image=image,
        ocr_results=ocr_results,
        ax_elements=None,
        scale_factor=scale_factor,
        outline_color=outline_color,
        badge_bg=badge_bg,
        badge_text_color=badge_text_color,
    )
    return annotated_img, registry.marks


def image_to_base64(image: Image.Image, format: str = "PNG") -> str:
    buf = io.BytesIO()
    image.save(buf, format=format)
    return base64.b64encode(buf.getvalue()).decode("utf-8")

