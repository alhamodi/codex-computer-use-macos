"""
Semantic Goal Resolution Engine.

Finds and targets UI elements by intent, label, role, or text
using accessibility trees, grounded Set-of-Marks, and Vision OCR
rather than requiring brittle hardcoded coordinates.
"""

from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from computer_use.accessibility import AccessibilityInspector
from computer_use.som import GroundedMarkRegistry


@dataclass
class SemanticTarget:
    """Resolved location and metadata for a semantic target."""
    found: bool
    x: int
    y: int
    width: int = 0
    height: int = 0
    confidence: float = 0.0
    source: str = "none"  # "ax", "ocr", "som"
    label: str = ""
    role: Optional[str] = None
    mark_id: Optional[int] = None
    metadata: Dict[str, Any] = None


class SemanticResolver:
    """
    Multimodal resolver for semantic goals.
    Translates: "Click the Save button" -> exact (x, y) coordinates
    by querying:
    1. macOS Accessibility UI hierarchy (highest accuracy).
    2. Active Grounded Set-of-Marks registry.
    3. Native Vision OCR bounding boxes.
    """

    def __init__(self, computer=None):
        self.computer = computer
        self.ax_inspector = AccessibilityInspector()
        self.som_registry = GroundedMarkRegistry.get_instance()

    def resolve(
        self,
        query: str,
        role: Optional[str] = None,
        target_app: Optional[str] = None,
        prefer_source: str = "ax",
    ) -> SemanticTarget:
        """
        Attempts to resolve a UI target by query string and optional role.
        """
        norm_query = query.strip().lower()

        # Step 1: Query Accessibility Tree (if frontmost or target app specified)
        if prefer_source in ("ax", "any"):
            ax_target = self._search_accessibility(norm_query, role=role, target_app=target_app)
            if ax_target and ax_target.found:
                return ax_target

        # Step 2: Query Active Set-of-Marks Registry
        som_target = self._search_som_registry(norm_query, role=role)
        if som_target and som_target.found:
            return som_target

        # Step 3: Query Vision OCR bounding boxes from current screen
        ocr_target = self._search_ocr(norm_query)
        if ocr_target and ocr_target.found:
            return ocr_target

        return SemanticTarget(
            found=False,
            x=0,
            y=0,
            confidence=0.0,
            source="none",
            label=query,
            role=role,
            metadata={"error": f"Semantic target '{query}' not located on screen."},
        )

    def _search_accessibility(
        self, query: str, role: Optional[str] = None, target_app: Optional[str] = None
    ) -> Optional[SemanticTarget]:
        """Inspects accessibility hierarchy for matches."""
        try:
            tree = self.ax_inspector.inspect_active_window(max_elements=100)
            elements = tree.get("elements", [])

            best_match: Optional[Dict[str, Any]] = None
            highest_score = 0.0

            for el in elements:
                title = str(el.get("title") or "").strip().lower()
                desc = str(el.get("description") or "").strip().lower()
                el_role = str(el.get("role") or "").strip().lower()

                # If role filter specified, ensure compatibility
                if role and role.lower() not in el_role:
                    continue

                # Scoring
                score = 0.0
                if query == title or query == desc:
                    score = 1.0
                elif query in title or query in desc:
                    score = 0.8
                elif any(word in title for word in query.split()):
                    score = 0.5

                if score > highest_score and score >= 0.5:
                    bounds = el.get("bounds", {})
                    if bounds.get("w", 0) > 0 and bounds.get("h", 0) > 0:
                        highest_score = score
                        best_match = el

            if best_match:
                bounds = best_match.get("bounds", {})
                bx = bounds.get("x", 0)
                by = bounds.get("y", 0)
                bw = bounds.get("w", 0)
                bh = bounds.get("h", 0)
                center_x = bx + (bw // 2)
                center_y = by + (bh // 2)

                return SemanticTarget(
                    found=True,
                    x=center_x,
                    y=center_y,
                    width=bw,
                    height=bh,
                    confidence=highest_score,
                    source="ax",
                    label=best_match.get("title") or best_match.get("description") or query,
                    role=best_match.get("role"),
                    metadata=best_match,
                )
        except Exception:
            pass
        return None

    def _search_som_registry(
        self, query: str, role: Optional[str] = None
    ) -> Optional[SemanticTarget]:
        """Searches currently registered Set-of-Marks."""
        try:
            for mark_id, meta in self.som_registry.marks.items():
                title = str(meta.get("title") or meta.get("text") or "").strip().lower()
                m_role = str(meta.get("role") or "").strip().lower()

                if role and role.lower() not in m_role:
                    continue

                if query in title or (title and title in query):
                    box = meta.get("box") or meta.get("bounds")
                    if box and len(box) >= 4:
                        bx, by, bw, bh = box[0], box[1], box[2], box[3]
                        return SemanticTarget(
                            found=True,
                            x=bx + (bw // 2),
                            y=by + (bh // 2),
                            width=bw,
                            height=bh,
                            confidence=0.85,
                            source="som",
                            label=title,
                            role=m_role,
                            mark_id=mark_id,
                            metadata=meta,
                        )
        except Exception:
            pass
        return None

    def _search_ocr(self, query: str) -> Optional[SemanticTarget]:
        """Performs fast Vision OCR and searches for bounding box matches."""
        if not self.computer:
            return None
        try:
            ocr_res = self.computer.extract_text(target_width=1280)
            items = ocr_res.get("items", [])
            for item in items:
                text = str(item.get("text") or "").strip().lower()
                if query in text:
                    bounds = item.get("bounds")
                    if bounds and len(bounds) >= 4:
                        bx, by, bw, bh = bounds[0], bounds[1], bounds[2], bounds[3]
                        return SemanticTarget(
                            found=True,
                            x=bx + (bw // 2),
                            y=by + (bh // 2),
                            width=bw,
                            height=bh,
                            confidence=0.75,
                            source="ocr",
                            label=item.get("text"),
                            role="text",
                            metadata=item,
                        )
        except Exception:
            pass
        return None
