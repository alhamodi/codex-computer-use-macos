"""
Accessibility (AXUIElement) Engine for macOS Computer Use.

Provides deep structural UI element hierarchy inspection via native System Events
and macOS CoreGraphics / ApplicationServices Accessibility APIs.
Extracts interactive UI elements (buttons, text fields, popups, sliders, check boxes)
with roles, titles, values, exact bounding boxes, and enabled states.
"""

from __future__ import annotations
import json
import logging
import subprocess
from typing import Any, Dict, List, Optional

logger = logging.getLogger("computer_use.accessibility")


class AccessibilityElement:
    """Represents a discovered UI element from the macOS Accessibility Hierarchy."""

    def __init__(
        self,
        element_id: str,
        role: str,
        title: str,
        value: Optional[str],
        bounds: Dict[str, int],
        enabled: bool,
        focused: bool,
        subrole: Optional[str] = None,
        description: Optional[str] = None,
        confidence: float = 1.0,
    ):
        self.element_id = element_id
        self.role = role
        self.title = title
        self.value = value
        self.bounds = bounds
        self.enabled = enabled
        self.focused = focused
        self.subrole = subrole
        self.description = description
        self.confidence = confidence

    @property
    def center_x(self) -> int:
        return self.bounds.get("x", 0) + self.bounds.get("width", 0) // 2

    @property
    def center_y(self) -> int:
        return self.bounds.get("y", 0) + self.bounds.get("height", 0) // 2

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.element_id,
            "role": self.role,
            "subrole": self.subrole,
            "title": self.title,
            "value": self.value,
            "description": self.description,
            "enabled": self.enabled,
            "focused": self.focused,
            "center_x": self.center_x,
            "center_y": self.center_y,
            "bounds": self.bounds,
            "confidence": self.confidence,
            "source": "accessibility",
        }


class AccessibilityInspector:
    """Inspects frontmost or targeted application accessibility trees on macOS."""

    def __init__(self, timeout: float = 4.0):
        self.timeout = timeout

    def inspect_frontmost(self, max_depth: int = 4) -> List[Dict[str, Any]]:
        """
        Inspect the frontmost application's interactive accessibility hierarchy.
        Returns flattened list of interactive elements with logical coordinates.
        """
        script = f'''
tell application "System Events"
    set frontProc to first process whose frontmost is true
    set procName to name of frontProc
    set procPID to unix id of frontProc
    
    set outElements to {{}}
    try
        set win to front window of frontProc
        set {{wx, wy}} to position of win
        set {{ww, wh}} to size of win
        
        -- Collect buttons, text fields, checkboxes, pop up buttons, menus
        set uiElems to (entire contents of win)
        set elemCount to count of uiElems
        if elemCount > 80 then set elemCount to 80 -- Guard against massive DOM trees
        
        set jsonItems to {{}}
        repeat with i from 1 to elemCount
            try
                set anElem to item i of uiElems
                set eRole to role of anElem
                if eRole is in {{"AXButton", "AXTextField", "AXCheckBox", "AXRadioButton", "AXPopUpButton", "AXComboBox", "AXMenuItem", "AXLink", "AXTab", "AXSlider"}} then
                    set eTitle to ""
                    try
                        set eTitle to title of anElem
                    end try
                    if eTitle is "" then
                        try
                            set eTitle to description of anElem
                        end try
                    end if
                    
                    set eVal to ""
                    try
                        set eVal to (value of anElem) as text
                    end try
                    
                    set {{ex, ey}} to position of anElem
                    set {{ew, eh}} to size of anElem
                    set isEnabled to true
                    try
                        set isEnabled to enabled of anElem
                    end try
                    
                    if ew > 0 and eh > 0 then
                        set jsonEntry to "{{\\"role\\":\\"" & eRole & "\\",\\"title\\":\\"" & eTitle & "\\",\\"value\\":\\"" & eVal & "\\",\\"x\\":" & ex & ",\\"y\\":" & ey & ",\\"width\\":" & ew & ",\\"height\\":" & eh & ",\\"enabled\\":" & isEnabled & "}}"
                        copy jsonEntry to end of jsonItems
                    end if
                end if
            end try
        end repeat
        
        set AppleScript's text item delimiters to ","
        return "[" & (jsonItems as text) & "]"
    on error
        return "[]"
    end try
end tell
'''
        try:
            proc = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                check=False,
                timeout=self.timeout
            )
            raw = proc.stdout.strip()
            if not raw or not raw.startswith("["):
                return []
            elements_data = json.loads(raw)
            results = []
            for idx, item in enumerate(elements_data, start=1):
                elem = AccessibilityElement(
                    element_id=f"ax_{idx}",
                    role=item.get("role", "AXUnknown"),
                    title=item.get("title", ""),
                    value=item.get("value"),
                    bounds={
                        "x": int(item.get("x", 0)),
                        "y": int(item.get("y", 0)),
                        "width": int(item.get("width", 0)),
                        "height": int(item.get("height", 0)),
                    },
                    enabled=bool(item.get("enabled", True)),
                    focused=False,
                )
                results.append(elem.to_dict())
            return results
        except Exception as e:
            logger.warning("Accessibility inspection fallback triggered: %s", e)
            return []
