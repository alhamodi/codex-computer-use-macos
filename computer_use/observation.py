"""
Unified Observation Layer for macOS Computer Use.

Encapsulates complete multimodal desktop state:
- Screen geometry & Retina scale.
- Active window & application metadata.
- Accessibility UI element tree (AXUIElement).
- Apple Vision OCR textual detections.
- Grounded Set-of-Marks (SoM) indexed to this observation UUID.
- Perceptual screen hash & freshness tracking (expiration TTL).
"""

from __future__ import annotations
import hashlib
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from computer_use.accessibility import AccessibilityInspector
from computer_use.som import GroundedMarkRegistry, fuse_and_render_som


@dataclass
class ObservedElement:
    element_id: str
    source: str  # "ax", "ocr", "som"
    role: str
    title: str
    bounds: List[int]  # [x, y, w, h] in logical points
    confidence: float = 1.0
    mark_id: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def center(self) -> Tuple[int, int]:
        bx, by, bw, bh = self.bounds
        return (bx + bw // 2, by + bh // 2)


@dataclass
class Observation:
    observation_id: str
    timestamp: float
    ttl_seconds: float
    screen_width: int
    screen_height: int
    scale_factor: float
    active_window: Dict[str, Any]
    active_app: str
    screenshot_base64: str
    screen_hash: str
    elements: List[ObservedElement] = field(default_factory=list)
    ax_tree: Optional[Dict[str, Any]] = None
    ocr_lines: List[Dict[str, Any]] = field(default_factory=list)
    has_som_overlay: bool = False
    warnings: List[str] = field(default_factory=list)

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.timestamp) > self.ttl_seconds

    @property
    def age(self) -> float:
        return time.time() - self.timestamp

    def find_elements(
        self,
        query: str,
        role: Optional[str] = None,
        min_confidence: float = 0.5,
    ) -> List[ObservedElement]:
        """Finds observed elements matching textual query and optional role."""
        q = query.strip().lower()
        matches = []
        for el in self.elements:
            if role and role.lower() not in el.role.lower():
                continue
            title = el.title.lower()
            if q in title or (title and title in q):
                if el.confidence >= min_confidence:
                    matches.append(el)
        return matches


class ObservationManager:
    """Collects and manages fused desktop observations."""

    def __init__(self, computer, ttl_seconds: float = 20.0):
        self.computer = computer
        self.ttl_seconds = ttl_seconds
        self.ax_inspector = AccessibilityInspector()
        self.som_registry = GroundedMarkRegistry.get_instance()
        self._last_observation: Optional[Observation] = None

    def capture_observation(
        self,
        with_som: bool = False,
        with_ocr: bool = True,
        with_ax: bool = True,
        target_width: int = 1280,
    ) -> Observation:
        obs_id = str(uuid.uuid4())
        t0 = time.time()
        warnings = []

        # 1. Screen info
        try:
            s_info = self.computer.screen_info()
            main_s = s_info.get("screens", [{}])[0]
            sw = main_s.get("width", 1440)
            sh = main_s.get("height", 900)
            scale = main_s.get("scale", 2.0)
        except Exception as e:
            sw, sh, scale = 1440, 900, 2.0
            warnings.append(f"Screen info fetch warning: {e}")

        # 2. Active Window & Application
        try:
            act_win = self.computer.active_window()
            active_app = act_win.get("app_name") or act_win.get("name") or "Unknown"
        except Exception as e:
            act_win = {"window_title": "Unknown", "app_name": "Unknown"}
            active_app = "Unknown"
            warnings.append(f"Active window fetch warning: {e}")

        # 3. Screenshot
        shot = self.computer.screenshot(target_width=target_width)
        b64 = shot.get("base64", "")
        screen_hash = hashlib.sha256(b64[:2000].encode()).hexdigest()[:16]

        observed_elements: List[ObservedElement] = []

        # 4. Accessibility Tree
        ax_tree = None
        if with_ax:
            try:
                ax_tree = self.ax_inspector.inspect_active_window(max_elements=100)
                for el in ax_tree.get("elements", []):
                    b = el.get("bounds", {})
                    bw, bh = b.get("w", 0), b.get("h", 0)
                    if bw > 0 and bh > 0:
                        observed_elements.append(
                            ObservedElement(
                                element_id=f"ax-{len(observed_elements)+1}",
                                source="ax",
                                role=el.get("role", "UIElement"),
                                title=el.get("title") or el.get("description") or "",
                                bounds=[b.get("x", 0), b.get("y", 0), bw, bh],
                                confidence=0.95,
                                metadata=el,
                            )
                        )
            except Exception as e:
                warnings.append(f"AX inspection warning: {e}")

        # 5. Vision OCR
        ocr_lines = []
        if with_ocr:
            try:
                ocr_res = self.computer.extract_text(fast=True)
                ocr_lines = ocr_res.get("lines", [])
                for item in ocr_res.get("items", []):
                    bounds = item.get("bounds")
                    if bounds and len(bounds) >= 4:
                        observed_elements.append(
                            ObservedElement(
                                element_id=f"ocr-{len(observed_elements)+1}",
                                source="ocr",
                                role="Text",
                                title=item.get("text", ""),
                                bounds=bounds,
                                confidence=item.get("confidence", 0.8),
                                metadata=item,
                            )
                        )
            except Exception as e:
                warnings.append(f"Vision OCR warning: {e}")

        # 6. Set-of-Marks Overlay (optional)
        has_som = False
        if with_som:
            try:
                som_res = fuse_and_render_som(b64)
                if som_res and "base64" in som_res:
                    b64 = som_res["base64"]
                    has_som = True
                    for m_id, m_meta in som_res.get("marks", {}).items():
                        box = m_meta.get("box") or m_meta.get("bounds")
                        if box:
                            observed_elements.append(
                                ObservedElement(
                                    element_id=f"som-{m_id}",
                                    source="som",
                                    role=m_meta.get("role", "Interactive"),
                                    title=m_meta.get("title") or m_meta.get("text") or "",
                                    bounds=box,
                                    confidence=0.9,
                                    mark_id=m_id,
                                    metadata=m_meta,
                                )
                            )
            except Exception as e:
                warnings.append(f"SoM rendering warning: {e}")

        obs = Observation(
            observation_id=obs_id,
            timestamp=t0,
            ttl_seconds=self.ttl_seconds,
            screen_width=sw,
            screen_height=sh,
            scale_factor=scale,
            active_window=act_win,
            active_app=active_app,
            screenshot_base64=b64,
            screen_hash=screen_hash,
            elements=observed_elements,
            ax_tree=ax_tree,
            ocr_lines=ocr_lines,
            has_som_overlay=has_som,
            warnings=warnings,
        )

        self._last_observation = obs
        return obs

    @property
    def latest_observation(self) -> Optional[Observation]:
        return self._last_observation
