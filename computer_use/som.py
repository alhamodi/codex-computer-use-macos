"""
Set-of-Marks (SoM) Visual Grounding Utility for macOS Computer Use.

Inspired by Microsoft OmniParser and Set-of-Mark Prompting.
Overlays distinct numbered badges onto detected UI text and interactive bounding boxes.
This allows Vision-Language Models (VLM) to reliably refer to UI elements by index (e.g. "click #4")
instead of guessing raw pixel coordinates.
"""

from __future__ import annotations
import base64
import io
import os
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


def create_som_overlay(
    image: Union[str, Image.Image],
    ocr_results: Dict[str, Any],
    scale_factor: float = 1.0,
    outline_color: str = "#E63946",
    badge_bg: str = "#E63946",
    badge_text_color: str = "#FFFFFF",
) -> Tuple[Image.Image, Dict[int, Dict[str, Any]]]:
    """
    Generate a Set-of-Marks annotated image and mark registry.

    Args:
        image: Path to image file or PIL Image instance.
        ocr_results: Dict output from `Computer.extract_text()` containing 'lines'.
        scale_factor: Retina scale factor (e.g., 2.0 if screenshot is 2x logical points).
        outline_color: Color for bounding box outlines.
        badge_bg: Background color for mark badges.
        badge_text_color: Text color for the mark badge numbers.

    Returns:
        (annotated_pil_image, mark_registry)
        where mark_registry is: { mark_id: { "text": ..., "center_x": ..., "center_y": ..., "box": ... } }
    """
    if not PIL_AVAILABLE:
        raise ImportError("PIL (Pillow) is required for Set-of-Marks generation.")

    if isinstance(image, str):
        img = Image.open(image).convert("RGBA")
    else:
        img = image.copy().convert("RGBA")

    overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)

    # Try loading default or built-in font
    font = None
    font_size = max(11, int(12 * scale_factor))
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
    except Exception:
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None

    mark_registry: Dict[int, Dict[str, Any]] = {}
    lines = ocr_results.get("lines", [])

    mark_id = 1
    for line in lines:
        text = line.get("text", "").strip()
        box = line.get("box")
        if not box or not text:
            continue

        # Extract box coordinates (logical points)
        bx = box.get("x", 0)
        by = box.get("y", 0)
        bw = box.get("width", 0)
        bh = box.get("height", 0)
        cx = box.get("center_x", bx + bw / 2)
        cy = box.get("center_y", by + bh / 2)

        # Scale to pixel coordinates for drawing
        px0 = int(bx * scale_factor)
        py0 = int(by * scale_factor)
        px1 = int((bx + bw) * scale_factor)
        py1 = int((by + bh) * scale_factor)

        # Draw light bounding box
        draw.rectangle([px0, py0, px1, py1], outline=outline_color, width=max(1, int(1.5 * scale_factor)))

        # Badge dimensions
        badge_text = str(mark_id)
        padding_x = int(4 * scale_factor)
        padding_y = int(2 * scale_factor)

        if font and hasattr(font, "getbbox"):
            bbox = font.getbbox(badge_text)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
        else:
            tw = len(badge_text) * 8
            th = 12

        badge_w = tw + padding_x * 2
        badge_h = th + padding_y * 2

        # Position badge at top-left corner of the box
        badge_x0 = max(0, px0)
        badge_y0 = max(0, py0 - badge_h)
        badge_x1 = badge_x0 + badge_w
        badge_y1 = badge_y0 + badge_h

        # Draw badge background
        draw.rounded_rectangle([badge_x0, badge_y0, badge_x1, badge_y1], radius=int(3 * scale_factor), fill=badge_bg)

        # Draw badge text
        text_x = badge_x0 + padding_x
        text_y = badge_y0 + padding_y
        draw.text((text_x, text_y), badge_text, fill=badge_text_color, font=font)

        # Register mark with logical coordinates (for direct clicking)
        mark_registry[mark_id] = {
            "id": mark_id,
            "text": text,
            "center_x": cx,
            "center_y": cy,
            "box": box,
        }
        mark_id += 1

    # Composite overlay onto base image
    combined = Image.alpha_composite(img, overlay).convert("RGB")
    return combined, mark_registry


def image_to_base64(image: Image.Image, format: str = "PNG") -> str:
    """Convert a PIL Image to a base64 encoded string."""
    buf = io.BytesIO()
    image.save(buf, format=format)
    return base64.b64encode(buf.getvalue()).decode("utf-8")
