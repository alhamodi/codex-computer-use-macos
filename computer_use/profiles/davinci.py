"""
DaVinci Resolve 21 Application Profile for Computer Use.

Provides deep, domain-aware automation for Blackmagic Design DaVinci Resolve 21 on macOS.
Combines:
- Native macOS Accessibility API & menu bar navigation (fastest, most reliable)
- Fast Apple Vision OCR with ROI window cropping (< 1 second)
- Smooth visible mouse movement (cubicEaseInOut) with user-takeover failsafe
- Non-destructive project & timeline management
"""

from __future__ import annotations
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple, Union

from computer_use.computer import Computer, UserTakeoverError


class DaVinciResolveProfile:
    """Specialized controller for DaVinci Resolve 21."""

    APP_NAME = "DaVinci Resolve"
    BUNDLE_ID = "com.blackmagic-design.DaVinciResolve"

    PAGES = {
        "media": ("shift", "2"),
        "cut": ("shift", "3"),
        "edit": ("shift", "4"),
        "fusion": ("shift", "5"),
        "color": ("shift", "6"),
        "fairlight": ("shift", "7"),
        "deliver": ("shift", "8"),
    }

    def __init__(self, computer: Optional[Computer] = None):
        self.computer = computer or Computer()

    # --- Process & Window Status ---

    def is_running(self) -> bool:
        """Check if DaVinci Resolve is currently running."""
        try:
            proc = subprocess.run(["pgrep", "-x", "Resolve"], capture_output=True, check=False)
            if proc.returncode == 0:
                return True
        except Exception:
            pass

        windows = self.computer.list_windows()
        for w in windows:
            app = w.get("application", "")
            if "resolve" in app.lower():
                return True
        return False

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive status of DaVinci Resolve (running state, project, window info)."""
        running = self.is_running()
        if not running:
            return {"running": False, "status": "DaVinci Resolve is not running"}
        win = self.get_window_info()
        return {
            "running": True,
            "project_name": self.get_active_project_name(),
            "window": win,
            "project_manager_open": self.is_project_manager_open(),
        }

    def focus(self) -> bool:
        """Bring DaVinci Resolve to the foreground."""
        return self.computer.focus_window(app_name=self.APP_NAME)

    def get_window_info(self) -> Dict[str, Any]:
        """Get DaVinci Resolve's window title, PID, and bounds."""
        windows = self.computer.list_windows()
        for w in windows:
            app = w.get("application", "")
            if "resolve" in app.lower():
                return w
        return {}

    def get_active_project_name(self) -> Optional[str]:
        """
        Get the name of the currently open project.
        In DaVinci Resolve, the main window title is the project name.
        """
        win = self.get_window_info()
        title = win.get("title", "")
        # If title is empty or generic, OCR the header
        if title and title != "DaVinci Resolve":
            return title
        
        # Fallback to OCR header
        ocr = self.computer.extract_text(active_window_only=True, fast=True)
        for line in ocr.get("lines", []):
            box = line.get("box", {})
            # Header title is at the top center (y < 40)
            if box.get("center_y", 100) < 30 and box.get("center_x", 0) > 400:
                text = line.get("text", "").strip()
                if text and text != "DaVinci Resolve":
                    return text
        return title or None

    def is_project_manager_open(self) -> bool:
        """Check whether the Project Manager modal is currently displayed."""
        ocr = self.computer.extract_text(active_window_only=True, fast=True)
        lines = [l.get("text", "") for l in ocr.get("lines", [])]
        # Project Manager displays 'Projects', 'New Project', 'Close'
        has_new_proj = any("New Project" in l for l in lines)
        has_close = any(l == "Close" or "Close" in l for l in lines)
        return has_new_proj and has_close

    # --- Project Manager Navigation ---

    def open_project_manager(self, timeout: float = 5.0) -> bool:
        """
        Open the Project Manager modal window via native menu bar or Shift+1.
        Waits until the Project Manager is verified open.
        """
        self.focus()
        time.sleep(0.2)
        if self.is_project_manager_open():
            return True

        # Try native menu bar trigger (fastest and most reliable)
        script = '''
tell application "System Events"
    tell process "DaVinci Resolve"
        click menu item "Project Manager…" of menu 1 of menu bar item "File" of menu bar 1
    end tell
end tell
'''
        subprocess.run(["osascript", "-e", script], capture_output=True, check=False, timeout=5)

        start = time.time()
        while time.time() - start < timeout:
            time.sleep(0.4)
            if self.is_project_manager_open():
                return True

        # Fallback to hotkey Shift+1
        self.computer.hotkey("shift", "1")
        time.sleep(0.8)
        return self.is_project_manager_open()

    def close_project_manager(self, timeout: float = 3.0) -> bool:
        """
        Close the Project Manager modal window and return to workspace.
        """
        self.focus()
        time.sleep(0.2)
        if not self.is_project_manager_open():
            return True

        ocr = self.computer.extract_text(active_window_only=True, fast=True)
        for line in ocr.get("lines", []):
            if line.get("text", "").strip() == "Close":
                box = line.get("box", {})
                cx = box.get("center_x")
                cy = box.get("center_y")
                if cx and cy:
                    self.computer.click(int(cx), int(cy))
                    time.sleep(0.6)
                    if not self.is_project_manager_open():
                        return True

        # Fallback to Escape key
        self.computer.key("esc")
        time.sleep(0.5)
        return not self.is_project_manager_open()

    def list_projects_in_manager(self) -> List[Dict[str, Any]]:
        """
        List all projects visible in the Project Manager with their card center coordinates.
        """
        if not self.is_project_manager_open():
            if not self.open_project_manager():
                return []

        ocr = self.computer.extract_text(active_window_only=True, fast=True)
        projects: List[Dict[str, Any]] = []
        ignored = {"local", "network", "cloud", "projects", "export", "import", "new project", "close", "davinci resolve 21"}

        for line in ocr.get("lines", []):
            text = line.get("text", "").strip()
            text_lower = text.lower()
            box = line.get("box", {})
            cy = box.get("center_y", 0)

            # Skip side panel and bottom button bar
            if cy > 700 or cy < 60:
                continue
            if any(ign in text_lower for ign in ignored):
                continue
            if len(text) < 2:
                continue

            projects.append({
                "name": text,
                "center_x": box.get("center_x"),
                "center_y": box.get("center_y"),
                "box": box
            })
        return projects

    def open_project(self, project_name: str, timeout: float = 10.0) -> bool:
        """
        Open a specific project by name from the Project Manager.
        Animates mouse cursor smoothly, double-clicks the project card,
        and verifies the project has successfully loaded.
        """
        current = self.get_active_project_name()
        if current and current.lower() == project_name.lower():
            return True

        if not self.open_project_manager():
            return False

        projects = self.list_projects_in_manager()
        target = None
        for p in projects:
            if project_name.lower() in p["name"].lower():
                target = p
                break

        if not target:
            return False

        # Double click the project card
        cx = target["center_x"]
        cy = target["center_y"]
        self.computer.double_click(cx, cy)

        # Wait for the project window to open
        start = time.time()
        while time.time() - start < timeout:
            time.sleep(0.5)
            new_title = self.get_active_project_name()
            if new_title and project_name.lower() in new_title.lower():
                return True
            if not self.is_project_manager_open():
                return True
        return False

    # --- Page Switching (Media, Cut, Edit, Color, etc.) ---

    def switch_to_page(self, page_name: str) -> bool:
        """
        Switch to a DaVinci Resolve workspace page:
        'media', 'cut', 'edit', 'fusion', 'color', 'fairlight', 'deliver'
        Uses native menu bar automation for 100% reliability, with shortcut fallback.
        """
        page_key = page_name.strip().lower()
        self.focus()
        time.sleep(0.1)

        # Title-case for menu item
        page_title = page_key.capitalize()
        script = f'''
tell application "System Events"
    tell process "DaVinci Resolve"
        click menu item "{page_title}" of menu 1 of menu item "Switch to Page" of menu 1 of menu bar item "Workspace" of menu bar 1
    end tell
end tell
'''
        proc = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=False)
        if proc.returncode == 0:
            return True

        # Fallback to keyboard shortcut
        if page_key in self.PAGES:
            keys = self.PAGES[page_key]
            self.computer.hotkey(*keys)
            return True

        return False

    # --- Playback & Timeline Controls ---

    def play_pause(self) -> bool:
        """Toggle playback on the timeline (Space)."""
        self.focus()
        self.computer.key("space")
        return True

    def fit_timeline(self) -> bool:
        """Fit entire timeline into the view (Shift+Z)."""
        self.focus()
        self.computer.hotkey("shift", "z")
        return True

    def split_clip(self) -> bool:
        """Razor / split the active clip at the current playhead position (Cmd+B)."""
        self.focus()
        self.computer.hotkey("cmd", "b")
        return True

    def zoom_in_timeline(self) -> bool:
        """Zoom in on the timeline (Cmd+=)."""
        self.focus()
        self.computer.hotkey("cmd", "+")
        return True

    def zoom_out_timeline(self) -> bool:
        """Zoom out on the timeline (Cmd+-)."""
        self.focus()
        self.computer.hotkey("cmd", "-")
        return True

    def toggle_snapping(self) -> bool:
        """Toggle timeline snapping on/off (N)."""
        self.focus()
        self.computer.key("n")
        return True

    def save_project(self) -> bool:
        """Safely save the current project (Cmd+S)."""
        self.focus()
        self.computer.hotkey("cmd", "s")
        return True

    def import_media(self) -> bool:
        """Open the Import Media dialog (Cmd+I)."""
        self.focus()
        self.computer.hotkey("cmd", "i")
        return True
