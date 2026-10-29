"""
Computer Use macOS Controller.

Provides native computer interaction for AI agents (OpenAI Codex, Anthropic Computer Use, etc.).
Wraps the high-performance native cliclick binary with support for:
- Screen: screenshots, active window capture, Apple Vision OCR, screen resolution & Retina scaling
- Mouse & Keyboard: click, move, drag, type, unicode typing, hotkeys, scroll
- Window Management: listing windows, focusing apps/windows, running programs, window text
- Clipboard: read & write macOS clipboard
- Browser: Safari & Google Chrome automation (get URL, tab title, navigate, search, read page)
- UI Automation: text finding and clicking via Apple Vision OCR bounding boxes
"""

from __future__ import annotations
import base64
import io
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from computer_use.security import ActionGuard, RiskLevel, SecurityPolicy, SecurityViolation
from computer_use.session import ComputerSession, SessionManager, SessionState
from computer_use.accessibility import AccessibilityInspector
from computer_use.verification import ActionVerifier, VerificationResult, VerificationState
from computer_use.browser import BrowserController


def _clean_osascript_output(output: str) -> str:
    """Filter out Cocoa persistence logs from osascript."""
    lines = []
    for line in output.splitlines():
        if "ApplePersistence=" in line:
            continue
        lines.append(line)
    return "\n".join(lines).strip()


class UserTakeoverError(RuntimeError):
    """Raised when the user physically touches or moves the mouse during Computer Use automation."""
    def __init__(self, message: str = "User takeover detected: mouse cursor was moved physically.", remaining_actions: Optional[List[Dict[str, Any]]] = None):
        super().__init__(message)
        self.remaining_actions = remaining_actions or []


class Computer:
    """Core controller for macOS desktop automation and AI agent computer use."""

    def __init__(
        self,
        binary_path: Optional[str] = None,
        smooth_cursor: bool = True,
        move_duration: int = 120,
        failsafe: bool = True,
        on_user_takeover: str = "raise",
        security_policy: Optional[SecurityPolicy] = None,
    ):
        if binary_path and os.path.exists(binary_path):
            self.binary_path = os.path.abspath(binary_path)
        else:
            project_root = Path(__file__).resolve().parent.parent
            local_bin = project_root / "cliclick"
            if local_bin.exists():
                self.binary_path = str(local_bin)
            else:
                found = shutil.which("cliclick")
                if found:
                    self.binary_path = found
                else:
                    raise FileNotFoundError(
                        "cliclick binary not found. Please run 'make' in the project directory."
                    )
        
        self.smooth_cursor = smooth_cursor
        self.move_duration = move_duration
        self.failsafe = failsafe
        self.on_user_takeover = on_user_takeover
        self._cached_screen_info: Optional[Dict[str, Any]] = None

        # Core Enterprise & Security Extensions
        self.guard = ActionGuard(policy=security_policy or SecurityPolicy())
        self.session_manager = SessionManager()
        self.accessibility = AccessibilityInspector()
        self.verifier = ActionVerifier(self)
        self.browser = BrowserController()
        self._active_som_registry: Optional[Any] = None

    def execute_json(self, payload: Union[Dict[str, Any], List[Dict[str, Any]]], timeout: int = 30) -> Dict[str, Any]:
        """Execute one or more Computer Use actions via JSON mode."""
        if isinstance(payload, list):
            body = {
                "actions": payload,
                "failsafe": self.failsafe,
                "move_duration": self.move_duration if self.smooth_cursor else 0,
            }
        elif isinstance(payload, dict) and "actions" in payload:
            body = dict(payload)
            if "failsafe" not in body:
                body["failsafe"] = self.failsafe
            if "move_duration" not in body and self.smooth_cursor:
                body["move_duration"] = self.move_duration
        elif isinstance(payload, dict):
            body = {
                "actions": [payload],
                "failsafe": self.failsafe,
                "move_duration": self.move_duration if self.smooth_cursor else 0,
            }
            for k in ("easing", "wait_ms"):
                if k in payload:
                    body[k] = payload[k]
        else:
            body = payload

        json_str = json.dumps(body)
        try:
            proc = subprocess.run(
                [self.binary_path, "-j", "-"],
                input=json_str,
                text=True,
                capture_output=True,
                check=False,
                timeout=timeout
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Computer execution timed out after {timeout} seconds")

        if proc.returncode != 0:
            error_msg = proc.stderr.strip() or proc.stdout.strip() or f"Process exited with code {proc.returncode}"
            err_dict: Dict[str, Any] = {}
            try:
                err_dict = json.loads(proc.stdout)
                if "error" in err_dict:
                    error_msg = err_dict["error"]
            except Exception:
                pass

            if err_dict.get("status") == "interrupted" or err_dict.get("reason") == "user_takeover":
                if self.on_user_takeover == "prompt":
                    print("\n⚠️ [Computer Use Failsafe] User takeover detected: Mouse was moved physically.")
                    print("Options: [1] Continue execution | [2] Abort automation")
                    try:
                        choice = input("Enter choice [1/2] (default 2): ").strip()
                    except (EOFError, KeyboardInterrupt):
                        choice = "2"
                    if choice == "1":
                        return {"status": "resumed_by_user", "message": "User chose to continue"}
                raise UserTakeoverError(error_msg)

            raise RuntimeError(f"Computer execution error: {error_msg}")

        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError:
            return {"status": "success", "raw_output": proc.stdout.strip()}

    def execute_command(self, *commands: str, timeout: int = 30) -> str:
        """Execute raw cliclick action commands."""
        args = [self.binary_path] + list(commands)
        try:
            proc = subprocess.run(args, capture_output=True, text=True, check=False, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Cliclick command timed out after {timeout} seconds")
        if proc.returncode != 0:
            raise RuntimeError(f"Cliclick command failed: {proc.stderr.strip()}")
        return proc.stdout.strip()

    # --- Screen Category ---

    def screen_info(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Get resolution, scale factor (Retina), and pixel dimensions for all displays."""
        if self._cached_screen_info is None or force_refresh:
            res = self.execute_json({"action": "screen_info"})
            self._cached_screen_info = res.get("data", {})
        return self._cached_screen_info

    def get_main_screen(self) -> Dict[str, Any]:
        """Get information for the primary display."""
        info = self.screen_info()
        screens = info.get("screens", [])
        for screen in screens:
            if screen.get("is_main"):
                return screen
        return screens[0] if screens else {"width": 1440, "height": 900, "scale": 2.0}

    def cursor_position(self) -> Tuple[int, int]:
        """Get current mouse cursor position (x, y) in macOS point coordinates."""
        res = self.execute_json({"action": "cursor_position"})
        out = res.get("output", "")
        parts = out.split(",")
        if len(parts) == 2:
            return int(parts[0]), int(parts[1])
        return 0, 0

    def screenshot(
        self,
        save_path: Optional[str] = None,
        target_width: Optional[int] = None
    ) -> Dict[str, Any]:
        """Capture screenshot of the main display."""
        main_scr = self.get_main_screen()
        screen_pt_w = main_scr.get("width", 1440)
        screen_pt_h = main_scr.get("height", 900)

        if save_path:
            abs_save = str(Path(save_path).resolve())
            self.execute_json({"action": "screenshot", "path": abs_save})
            with open(abs_save, "rb") as f:
                raw_bytes = f.read()
        else:
            res = self.execute_json({"action": "screenshot"})
            b64_str = res.get("output", "").strip()
            raw_bytes = base64.b64decode(b64_str)

        if HAS_PIL:
            img = Image.open(io.BytesIO(raw_bytes))
            orig_w, orig_h = img.size

            if target_width and target_width < orig_w:
                ratio = target_width / float(orig_w)
                target_height = int(orig_h * ratio)
                img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                raw_bytes = buf.getvalue()
                if save_path:
                    img.save(save_path)
                img_w, img_h = target_width, target_height
            else:
                img_w, img_h = orig_w, orig_h

            scale_ratio = img_w / float(screen_pt_w)
        else:
            img_w = main_scr.get("pixel_width", 2880)
            img_h = main_scr.get("pixel_height", 1800)
            scale_ratio = float(main_scr.get("scale", 2.0))

        b64_output = base64.b64encode(raw_bytes).decode("ascii")
        return {
            "base64": b64_output,
            "width": img_w,
            "height": img_h,
            "screen_width": screen_pt_w,
            "screen_height": screen_pt_h,
            "scale_ratio": scale_ratio,
            "path": save_path
        }

    def screenshot_active_window(self, save_path: Optional[str] = None) -> Dict[str, Any]:
        """Capture screenshot of only the focused frontmost window."""
        if save_path:
            abs_save = str(Path(save_path).resolve())
            self.execute_json({"action": "screenshot_active_window", "path": abs_save})
            with open(abs_save, "rb") as f:
                raw_bytes = f.read()
        else:
            res = self.execute_json({"action": "screenshot_active_window"})
            b64_str = res.get("output", "").strip()
            raw_bytes = base64.b64decode(b64_str)

        b64_output = base64.b64encode(raw_bytes).decode("ascii")
        return {"base64": b64_output, "path": save_path}

    def observe_screen(self, target_width: int = 1280) -> Dict[str, Any]:
        """
        Multimodal observation of current desktop state in a single call.
        Returns screenshot, active window info, cursor position, and screen resolution.
        """
        shot = self.screenshot(target_width=target_width)
        win = self.active_window()
        cur_x, cur_y = self.cursor_position()
        return {
            "screenshot": shot["base64"],
            "image_size": [shot["width"], shot["height"]],
            "screen_size": [shot["screen_width"], shot["screen_height"]],
            "scale_ratio": shot["scale_ratio"],
            "active_window": win,
            "cursor": [cur_x, cur_y]
        }

    def extract_text(self, active_window_only: bool = False, fast: bool = True, timeout: int = 60) -> Dict[str, Any]:
        """
        Extract text and bounding boxes using Apple's native Vision framework OCR.
        Uses fast mode by default for sub-second recognition, or fast=False for deep model.
        Returns full text and structured lines with coordinates for clicking.
        """
        act = "extract_text_active_window" if active_window_only else "extract_text"
        res = self.execute_json({"action": act, "fast": fast}, timeout=timeout)
        return res.get("data", {})

    # --- Mouse and Keyboard Category ---

    def click(self, x: Optional[int] = None, y: Optional[int] = None, button: str = "left") -> Dict[str, Any]:
        """Click mouse button (left, right, or middle)."""
        act = f"{button}_click" if button in ("left", "right", "middle") else "left_click"
        payload: Dict[str, Any] = {"action": act}
        if x is not None and y is not None:
            payload["coordinate"] = [x, y]
        return self.execute_json(payload)

    def hover(self, x: int, y: int, duration_ms: int = 200) -> Dict[str, Any]:
        """
        Move smoothly to (x, y) and hover there for duration_ms to trigger
        browser/UI pointerover, mouseenter, and CSS hover states.
        """
        batch = [
            {"action": "mouse_move", "coordinate": [x, y]},
            {"action": "wait", "ms": duration_ms}
        ]
        return self.batch_actions(batch)

    def human_click(
        self,
        x: int,
        y: int,
        hover_ms: int = 150,
        hold_ms: int = 80
    ) -> Dict[str, Any]:
        """
        Execute a realistic 3-phase human click:
        1. Smooth cursor movement with cubic easing to (x, y)
        2. Dwell/hover for hover_ms (triggers React/DOM pointerover, mouseenter, CSS hover)
        3. Mouse down -> wait hold_ms -> mouse up
        """
        batch = [
            {"action": "mouse_move", "coordinate": [x, y]},
            {"action": "wait", "ms": hover_ms},
            {"action": "mouse_down", "coordinate": [x, y]},
            {"action": "wait", "ms": hold_ms},
            {"action": "mouse_up", "coordinate": [x, y]}
        ]
        return self.batch_actions(batch)

    def move(self, x: int, y: int) -> Dict[str, Any]:
        """Move mouse cursor to (x, y)."""
        return self.execute_json({"action": "mouse_move", "coordinate": [x, y]})

    def right_click(self, x: Optional[int] = None, y: Optional[int] = None) -> Dict[str, Any]:
        return self.click(x, y, button="right")

    def middle_click(self, x: Optional[int] = None, y: Optional[int] = None) -> Dict[str, Any]:
        return self.click(x, y, button="middle")

    def double_click(self, x: Optional[int] = None, y: Optional[int] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"action": "double_click"}
        if x is not None and y is not None:
            payload["coordinate"] = [x, y]
        return self.execute_json(payload)

    def triple_click(self, x: Optional[int] = None, y: Optional[int] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"action": "triple_click"}
        if x is not None and y is not None:
            payload["coordinate"] = [x, y]
        return self.execute_json(payload)

    def mouse_down(self, x: Optional[int] = None, y: Optional[int] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"action": "mouse_down"}
        if x is not None and y is not None:
            payload["coordinate"] = [x, y]
        return self.execute_json(payload)

    def mouse_up(self, x: Optional[int] = None, y: Optional[int] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"action": "mouse_up"}
        if x is not None and y is not None:
            payload["coordinate"] = [x, y]
        return self.execute_json(payload)

    def drag(self, start_x: int, start_y: int, end_x: int, end_y: int) -> Dict[str, Any]:
        return self.execute_json({
            "action": "drag",
            "from": [start_x, start_y],
            "to": [end_x, end_y]
        })

    def scroll(
        self,
        delta_y: int = 0,
        delta_x: int = 0,
        x: Optional[int] = None,
        y: Optional[int] = None
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"action": "scroll", "delta_y": delta_y, "delta_x": delta_x}
        if x is not None and y is not None:
            payload["coordinate"] = [x, y]
        return self.execute_json(payload)

    def type(self, text: str) -> Dict[str, Any]:
        """Type text into active app. Auto-falls back to unicode paste for Arabic/Unicode."""
        if not text.isascii():
            return self.type_unicode(text)
        return self.execute_json({"action": "type", "text": text})

    def type_unicode(self, text: str) -> Dict[str, Any]:
        """Paste unicode text via clipboard, preserving user's existing clipboard contents."""
        old_clip = self.get_clipboard()
        try:
            self.set_clipboard(text)
            res = self.hotkey("cmd", "v")
            return res
        finally:
            if old_clip:
                try:
                    self.set_clipboard(old_clip)
                except Exception:
                    pass

    def key(self, key_name: str) -> Dict[str, Any]:
        """Press special key (e.g. return, tab, esc, space, arrow-down)."""
        return self.execute_json({"action": "key", "text": key_name})

    def hotkey(self, *keys: str) -> Dict[str, Any]:
        """Trigger key shortcut (e.g. hotkey('cmd', 'c'), hotkey('cmd', 'shift', 'p'))."""
        return self.execute_json({"action": "hotkey", "keys": list(keys)})

    # --- Window Management Category ---

    def list_windows(self) -> List[Dict[str, Any]]:
        """List all on-screen application windows with PID, owner app, title, and bounds."""
        res = self.execute_json({"action": "list_windows"})
        return res.get("data", [])

    def active_window(self) -> Dict[str, Any]:
        """Get frontmost application name, bundle ID, PID, window title, and bounds."""
        res = self.execute_json({"action": "window_info"})
        return res.get("data", {})

    def focus_window(self, app_name: Optional[str] = None, pid: Optional[int] = None) -> bool:
        """Bring application window to the foreground using native Cocoa APIs."""
        payload: Dict[str, Any] = {"action": "focus_window"}
        if pid:
            payload["pid"] = pid
        elif app_name:
            payload["app_name"] = app_name
        else:
            return False
        try:
            res = self.execute_json(payload)
            return res.get("status") == "success"
        except Exception:
            return False

    def open_app(self, app_name: str, timeout: int = 15) -> bool:
        """Launch or activate application by name."""
        if self.focus_window(app_name=app_name):
            return True
        try:
            res = subprocess.run(["open", "-a", app_name], capture_output=True, check=False, timeout=timeout)
            return res.returncode == 0
        except subprocess.TimeoutExpired:
            return False

    def run_program(self, command: str, timeout: int = 30) -> Dict[str, Any]:
        """Run terminal command with timeout."""
        try:
            proc = subprocess.run(command, shell=True, capture_output=True, text=True, check=False, timeout=timeout)
            return {
                "exit_code": proc.returncode,
                "stdout": proc.stdout.strip(),
                "stderr": proc.stderr.strip()
            }
        except subprocess.TimeoutExpired:
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Command timed out after {timeout} seconds"
            }

    def get_window_text(self) -> str:
        """Extract text from active frontmost window via OCR."""
        ocr_res = self.extract_text(active_window_only=True)
        return ocr_res.get("text", "")

    # --- Clipboard Category ---

    def get_clipboard(self, timeout: int = 5) -> str:
        """Read macOS clipboard contents."""
        try:
            proc = subprocess.run(["pbpaste"], capture_output=True, text=True, check=False, timeout=timeout)
            return proc.stdout
        except (subprocess.TimeoutExpired, Exception):
            return ""

    def set_clipboard(self, text: str, timeout: int = 5) -> None:
        """Copy text to macOS clipboard."""
        try:
            subprocess.run(["pbcopy"], input=text, text=True, check=False, timeout=timeout)
        except Exception:
            pass

    # --- Browser Category (Safari & Google Chrome) ---

    def browser_get_url(self, browser: str = "Safari", timeout: int = 10) -> str:
        """Get URL of active tab in browser."""
        b_lower = browser.lower()
        if "chrome" in b_lower:
            script = 'tell application "Google Chrome" to return URL of active tab of front window'
        else:
            script = 'tell application "Safari" to return URL of front document'
        try:
            proc = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=False, timeout=timeout)
            return _clean_osascript_output(proc.stdout)
        except Exception:
            return ""

    def browser_get_tab_title(self, browser: str = "Safari", timeout: int = 10) -> str:
        """Get tab title of active tab in browser."""
        b_lower = browser.lower()
        if "chrome" in b_lower:
            script = 'tell application "Google Chrome" to return title of active tab of front window'
        else:
            script = 'tell application "Safari" to return name of front document'
        try:
            proc = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=False, timeout=timeout)
            return _clean_osascript_output(proc.stdout)
        except Exception:
            return ""

    def browser_navigate(self, url: str, browser: str = "Safari", timeout: int = 15) -> bool:
        """Navigate active tab to a URL."""
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url
        b_lower = browser.lower()
        clean_url = url.replace("\\", "").replace('"', "%22")
        if "chrome" in b_lower:
            script = f'tell application "Google Chrome" to set URL of active tab of front window to "{clean_url}"'
        else:
            script = f'tell application "Safari" to set URL of front document to "{clean_url}"'
        try:
            proc = subprocess.run(["osascript", "-e", script], capture_output=True, check=False, timeout=timeout)
            return proc.returncode == 0
        except Exception:
            return False

    def browser_search(self, query: str, browser: str = "Safari") -> bool:
        """Search query in Google in the browser."""
        from urllib.parse import quote_plus
        url = f"https://www.google.com/search?q={quote_plus(query)}"
        return self.browser_navigate(url, browser=browser)

    def browser_read_page(self, browser: str = "Safari", timeout: int = 15) -> str:
        """Extract inner text from active webpage."""
        b_lower = browser.lower()
        if "chrome" in b_lower:
            script = 'tell application "Google Chrome" to return execute front window\'s active tab javascript "document.body.innerText"'
        else:
            script = 'tell application "Safari" to return do JavaScript "document.body.innerText" in front document'
        try:
            proc = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=False, timeout=timeout)
            return _clean_osascript_output(proc.stdout)
        except Exception:
            return ""

    # --- Chat and Messaging Category ---

    def send_text_to_window(self, app_name: str, text: str, press_enter: bool = True) -> bool:
        """Focus an app, paste message text, and optionally hit Return."""
        if not self.focus_window(app_name=app_name):
            return False
        self.type_unicode(text)
        if press_enter:
            self.key("return")
        return True

    def send_keys_to_window(self, app_name: str, *keys: str) -> bool:
        """Focus an app and send hotkey shortcut."""
        if not self.focus_window(app_name=app_name):
            return False
        self.hotkey(*keys)
        return True

    # --- UI Automation Category ---

    def find_and_click_element(self, text: str, active_window_only: bool = False) -> bool:
        """
        Search for element containing specified text using Apple Vision OCR and click its center.
        """
        ocr_res = self.extract_text(active_window_only=active_window_only)
        lines = ocr_res.get("lines", [])
        text_lower = text.lower()
        for line in lines:
            line_text = line.get("text", "").lower()
            if text_lower in line_text:
                box = line.get("box", {})
                cx = box.get("center_x")
                cy = box.get("center_y")
                if cx is not None and cy is not None:
                    self.click(int(cx), int(cy))
                    return True
        return False

    def som_observe(
        self,
        active_window_only: bool = False,
        save_path: Optional[str] = None,
        include_accessibility: bool = True,
        ttl_seconds: float = 30.0,
    ) -> Dict[str, Any]:
        """
        Capture screen and generate a multi-modal Set-of-Marks (SoM) observation.
        Fuses Apple Vision OCR and native macOS Accessibility nodes into a unified grounded registry,
        tracked by session freshness TTL to prevent stale-mark hallucinations.
        """
        from computer_use.som import fuse_and_render_som, image_to_base64
        from PIL import Image
        import io

        if active_window_only:
            shot = self.screenshot_active_window()
        else:
            shot = self.screenshot()

        raw_bytes = base64.b64decode(shot["base64"])
        pil_img = Image.open(io.BytesIO(raw_bytes))

        ocr_res = self.extract_text(active_window_only=active_window_only, fast=True)
        ax_elements = self.accessibility.inspect_frontmost() if include_accessibility else []
        scale_ratio = shot.get("scale_ratio", 2.0)

        annotated_img, registry = fuse_and_render_som(
            image=pil_img,
            ocr_results=ocr_res,
            ax_elements=ax_elements,
            scale_factor=scale_ratio,
            ttl_seconds=ttl_seconds,
        )

        self._active_som_registry = registry
        b64 = image_to_base64(annotated_img)
        if save_path:
            annotated_img.save(save_path)

        return {
            "registry_id": registry.registry_id,
            "created_at": registry.created_at,
            "ttl_seconds": registry.ttl_seconds,
            "image_path": save_path,
            "base64": b64,
            "width": annotated_img.width,
            "height": annotated_img.height,
            "scale_ratio": scale_ratio,
            "marks": registry.marks,
            "count": len(registry.marks),
        }

    def click_mark(
        self,
        mark_id: int,
        marks_registry: Optional[Dict[Union[int, str], Dict[str, Any]]] = None,
        enforce_freshness: bool = True,
    ) -> bool:
        """
        Click the center of a mark by its numeric ID.
        Validates against the active grounded registry to reject stale marks.
        """
        target = None
        if self._active_som_registry:
            target = self._active_som_registry.get_mark(mark_id, enforce_freshness=enforce_freshness)
        elif marks_registry:
            target = marks_registry.get(mark_id) or marks_registry.get(str(mark_id))

        if not target:
            return False
        cx = target.get("center_x")
        cy = target.get("center_y")
        if cx is not None and cy is not None:
            self.human_click(int(cx), int(cy))
            return True
        return False

    # --- Smart Automation, State Polling & Workflow Verification ---

    def wait_until_condition(
        self,
        condition: str,
        target: str,
        timeout: float = 30.0,
        poll_interval: float = 0.8,
        active_window_only: bool = False
    ) -> Dict[str, Any]:
        """
        Intelligent state polling engine: replaces brittle static sleeps by waiting
        for a specific UI condition to be satisfied.

        Supported conditions:
        - 'text_appears': waits until target text is visible on screen/active window.
        - 'text_disappears': waits until target text (e.g. 'Uploading', 'Processing') is gone.
        - 'window_title_contains': waits until active window title contains target substring.
        """
        start = time.time()
        target_lower = target.lower()

        while time.time() - start < timeout:
            if condition == "text_appears":
                ocr = self.extract_text(active_window_only=active_window_only, fast=True)
                lines = [l.get("text", "") for l in ocr.get("lines", [])]
                for line in lines:
                    if target_lower in line.lower():
                        return {
                            "success": True,
                            "condition": condition,
                            "target": target,
                            "matched_text": line,
                            "elapsed_seconds": round(time.time() - start, 2)
                        }

            elif condition == "text_disappears":
                ocr = self.extract_text(active_window_only=active_window_only, fast=True)
                lines = [l.get("text", "") for l in ocr.get("lines", [])]
                found = any(target_lower in line.lower() for line in lines)
                if not found:
                    return {
                        "success": True,
                        "condition": condition,
                        "target": target,
                        "elapsed_seconds": round(time.time() - start, 2)
                    }

            elif condition == "window_title_contains":
                win = self.active_window()
                title = win.get("title", "")
                if target_lower in title.lower():
                    return {
                        "success": True,
                        "condition": condition,
                        "target": target,
                        "window_title": title,
                        "elapsed_seconds": round(time.time() - start, 2)
                    }

            else:
                raise ValueError(f"Unsupported condition: {condition}")

            time.sleep(poll_interval)

        return {
            "success": False,
            "error": "timeout",
            "condition": condition,
            "target": target,
            "timeout_seconds": timeout,
            "elapsed_seconds": round(time.time() - start, 2)
        }

    def handle_file_dialog(self, file_path: str, timeout: float = 10.0) -> Dict[str, Any]:
        """
        Automates macOS Open/Save file chooser dialogs:
        Sends Cmd+Shift+G ('Go to folder'), enters file path cleanly without loss,
        confirms navigation, and triggers confirmation.
        """
        import os
        abs_path = os.path.abspath(os.path.expanduser(file_path))
        if not os.path.exists(abs_path):
            return {"success": False, "error": f"File does not exist: {abs_path}"}

        # Press Cmd+Shift+G to trigger the 'Go to the folder:' sheet in Finder dialog
        self.hotkey("cmd", "shift", "g")
        time.sleep(0.6)

        # Type full path via clipboard paste to prevent keyboard layout/character corruption
        self.type_unicode(abs_path)
        time.sleep(0.3)

        # Press Return to go to the file in the dialog
        self.key("return")
        time.sleep(0.6)

        # Press Return again to confirm selection (Open)
        self.key("return")
        time.sleep(0.5)

        return {
            "success": True,
            "file_path": abs_path,
            "message": "File path submitted to macOS file dialog"
        }

    def verify_action_result(
        self,
        success_keywords: List[str],
        blocker_keywords: Optional[List[str]] = None,
        timeout: float = 15.0,
        active_window_only: bool = False
    ) -> Dict[str, Any]:
        """
        Post-action verification with diagnostic guardrails:
        Continuously polls for success indicators while watching for known blocker keywords
        (e.g., terms agreement checkbox, copyright warnings, CAPTCHA, upload failures).
        """
        blockers = blocker_keywords or [
            "agree", "terms", "copyright", "failed", "error", "too large",
            "format not supported", "captcha", "try again", "invalid"
        ]
        start = time.time()

        while time.time() - start < timeout:
            ocr = self.extract_text(active_window_only=active_window_only, fast=True)
            lines = [l.get("text", "") for l in ocr.get("lines", [])]
            full_text = " ".join(lines).lower()

            # Check for blockers first
            detected_blockers = [b for b in blockers if b.lower() in full_text]
            if detected_blockers:
                return {
                    "status": "blocked",
                    "blockers": detected_blockers,
                    "visible_lines": lines[:10],
                    "elapsed_seconds": round(time.time() - start, 2)
                }

            # Check for success
            for s in success_keywords:
                if s.lower() in full_text:
                    return {
                        "status": "success",
                        "matched_success": s,
                        "elapsed_seconds": round(time.time() - start, 2)
                    }

            time.sleep(1.0)

        return {
            "status": "unverified",
            "message": "Neither success nor blocker indicators detected before timeout",
            "elapsed_seconds": round(time.time() - start, 2)
        }

    # --- Utility Category ---

    def batch_actions(self, actions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Execute a list of actions sequentially."""
        return self.execute_json(actions)

    def wait(self, milliseconds: int) -> Dict[str, Any]:
        """Pause execution for milliseconds."""
        return self.execute_json({"action": "wait", "ms": milliseconds})
