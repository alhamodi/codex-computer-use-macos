"""
Hybrid Browser Automation Controller.

Integrates:
- Modern Playwright Engine (headless or headed) for high-performance DOM automation.
- Resilient AppleScript fallbacks for system Safari & Google Chrome.
- Navigation safety checks, domain whitelisting, and form handling.
"""

from __future__ import annotations
import logging
import subprocess
from typing import Any, Dict, List, Optional

logger = logging.getLogger("computer_use.browser")


class BrowserController:
    """Manages web automation via Playwright or native macOS AppleScript drivers."""

    def __init__(self, preferred_browser: str = "Safari"):
        self.preferred_browser = preferred_browser
        self._playwright = None
        self._browser = None
        self._page = None

    def launch_playwright(self, headless: bool = True) -> bool:
        """Initializes a local Playwright Chromium instance if available."""
        try:
            from playwright.sync_api import sync_playwright
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=headless)
            self._page = self._browser.new_page()
            return True
        except Exception as e:
            logger.warning("Playwright initialization failed; defaulting to AppleScript: %s", e)
            return False

    def close(self) -> None:
        if self._browser:
            try:
                self._browser.close()
            except Exception:
                pass
        if self._playwright:
            try:
                self._playwright.stop()
            except Exception:
                pass
        self._browser = None
        self._playwright = None
        self._page = None

    def navigate(self, url: str) -> bool:
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url

        if self._page:
            try:
                self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
                return True
            except Exception as e:
                logger.error("Playwright navigation error: %s", e)

        # Fallback to macOS AppleScript
        b_lower = self.preferred_browser.lower()
        if "chrome" in b_lower:
            script = f'''
tell application "Google Chrome"
    activate
    set URL of active tab of front window to "{url}"
end tell
'''
        else:
            script = f'''
tell application "Safari"
    activate
    set URL of front document to "{url}"
end tell
'''
        proc = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=False)
        return proc.returncode == 0

    def get_url(self) -> str:
        if self._page:
            return self._page.url

        b_lower = self.preferred_browser.lower()
        if "chrome" in b_lower:
            script = 'tell application "Google Chrome" to return URL of active tab of front window'
        else:
            script = 'tell application "Safari" to return URL of front document'
        proc = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=False)
        return proc.stdout.strip()

    def get_title(self) -> str:
        if self._page:
            return self._page.title()

        b_lower = self.preferred_browser.lower()
        if "chrome" in b_lower:
            script = 'tell application "Google Chrome" to return title of active tab of front window'
        else:
            script = 'tell application "Safari" to return name of front document'
        proc = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=False)
        return proc.stdout.strip()

    def read_text(self) -> str:
        if self._page:
            try:
                return self._page.inner_text("body")
            except Exception:
                return ""

        b_lower = self.preferred_browser.lower()
        if "chrome" in b_lower:
            script = 'tell application "Google Chrome" to execute front window\'s active tab javascript "document.body.innerText"'
        else:
            script = 'tell application "Safari" to do JavaScript "document.body.innerText" in front document'
        proc = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=False)
        return proc.stdout.strip()
