"""
Security Policy and Permission Management Engine for Computer Use Agents.

Implements strict 5-tier action risk classification, scope limits,
prompt-injection boundary isolation, and explicit approval policies.
"""

from __future__ import annotations
import enum
import fnmatch
import logging
import re
from typing import Any, Callable, Dict, List, Optional, Set, Union

logger = logging.getLogger("computer_use.security")


class RiskLevel(enum.IntEnum):
    READ = 1            # Non-invasive observation (screenshot, OCR, active window query, screen size)
    BENIGN = 2          # Reversible local interactions (move mouse, hover, scroll, safe wait)
    WRITE = 3           # Modifying local UI state or files (typing in safe apps, opening windows)
    SENSITIVE = 4       # External communication, posting, credential handling, file uploads
    DESTRUCTIVE = 5     # Shell execution, deleting files, system configuration changes, checkout/payment


class SecurityViolation(RuntimeError):
    """Raised when an action violates security policy or exceeds allowed risk."""
    pass


class ActionDenied(RuntimeError):
    """Raised when a sensitive or destructive action is rejected by policy or human approver."""
    pass


class SecurityPolicy:
    """Configurable security policy determining execution guardrails."""

    def __init__(
        self,
        max_allowed_risk: RiskLevel = RiskLevel.WRITE,
        allowed_applications: Optional[List[str]] = None,
        blocked_applications: Optional[List[str]] = None,
        allowed_urls: Optional[List[str]] = None,
        blocked_urls: Optional[List[str]] = None,
        allow_shell_execution: bool = False,
        allow_destructive_actions: bool = False,
        require_approval_above: RiskLevel = RiskLevel.SENSITIVE,
        approval_callback: Optional[Callable[[Dict[str, Any], RiskLevel], bool]] = None,
        max_steps_per_session: int = 100,
        disallowed_commands_regex: Optional[List[str]] = None,
    ):
        self.max_allowed_risk = max_allowed_risk
        self.allowed_applications = allowed_applications  # None means any unless blocked
        self.blocked_applications = blocked_applications or [
            "1Password", "Keychain Access", "Bitwarden", "System Settings",
            "Terminal", "iTerm2", "Console"
        ]
        self.allowed_urls = allowed_urls  # None means any unless blocked
        self.blocked_urls = blocked_urls or [
            "*paypal.com*", "*stripe.com*", "*checkout*", "*bank*", "*apple.com/shop*"
        ]
        self.allow_shell_execution = allow_shell_execution
        self.allow_destructive_actions = allow_destructive_actions
        self.require_approval_above = require_approval_above
        self.approval_callback = approval_callback
        self.max_steps_per_session = max_steps_per_session
        self.disallowed_commands_regex = disallowed_commands_regex or [
            r"rm\s+-rf", r":\(\)\s*\{", r"mkfs", r"dd\s+if=", r"chmod\s+-R\s+777",
            r"curl.*\|\s*sh", r"wget.*\|\s*sh", r"killall\s+-9"
        ]

    def is_app_allowed(self, app_name: str) -> bool:
        if not app_name:
            return True
        app_clean = app_name.strip()
        for blocked in self.blocked_applications:
            if fnmatch.fnmatch(app_clean.lower(), blocked.lower()):
                return False
        if self.allowed_applications is not None:
            return any(fnmatch.fnmatch(app_clean.lower(), a.lower()) for a in self.allowed_applications)
        return True

    def is_url_allowed(self, url: str) -> bool:
        if not url:
            return True
        for blocked in self.blocked_urls:
            if fnmatch.fnmatch(url.lower(), blocked.lower()):
                return False
        if self.allowed_urls is not None:
            return any(fnmatch.fnmatch(url.lower(), a.lower()) for a in self.allowed_urls)
        return True

    def is_command_safe(self, command: str) -> bool:
        if not self.allow_shell_execution:
            return False
        for pattern in self.disallowed_commands_regex:
            if re.search(pattern, command, re.IGNORECASE):
                return False
        return True


class ActionGuard:
    """Enforces security policies before tool or native action dispatch."""

    TOOL_RISK_MAP = {
        # Read operations
        "get_screen_size": RiskLevel.READ,
        "get_cursor_position": RiskLevel.READ,
        "screenshot": RiskLevel.READ,
        "screenshot_active_window": RiskLevel.READ,
        "observe_screen": RiskLevel.READ,
        "extract_text": RiskLevel.READ,
        "extract_text_active_window": RiskLevel.READ,
        "list_windows": RiskLevel.READ,
        "get_window_text": RiskLevel.READ,
        "get_clipboard": RiskLevel.READ,
        "chrome_get_url": RiskLevel.READ,
        "chrome_get_tab_title": RiskLevel.READ,
        "chrome_read_page": RiskLevel.READ,
        "safari_get_url": RiskLevel.READ,
        "safari_get_tab_title": RiskLevel.READ,
        "safari_read_page": RiskLevel.READ,
        "som_observe": RiskLevel.READ,
        "davinci_status": RiskLevel.READ,
        "verify_action_result": RiskLevel.READ,
        "wait_until_condition": RiskLevel.READ,

        # Benign operations
        "move_mouse": RiskLevel.BENIGN,
        "hover": RiskLevel.BENIGN,
        "scroll": RiskLevel.BENIGN,
        "wait": RiskLevel.BENIGN,

        # Write operations
        "click": RiskLevel.WRITE,
        "human_click": RiskLevel.WRITE,
        "click_mark": RiskLevel.WRITE,
        "drag_mouse": RiskLevel.WRITE,
        "type_text": RiskLevel.WRITE,
        "type_unicode": RiskLevel.WRITE,
        "press_key": RiskLevel.WRITE,
        "hotkey": RiskLevel.WRITE,
        "set_clipboard": RiskLevel.WRITE,
        "focus_window": RiskLevel.WRITE,
        "open_app": RiskLevel.WRITE,
        "find_and_click_element": RiskLevel.WRITE,
        "davinci_switch_page": RiskLevel.WRITE,
        "davinci_project_manager": RiskLevel.WRITE,
        "davinci_open_project": RiskLevel.WRITE,
        "davinci_timeline_action": RiskLevel.WRITE,
        "handle_file_dialog": RiskLevel.WRITE,

        # Sensitive operations
        "chrome_navigate": RiskLevel.SENSITIVE,
        "chrome_search": RiskLevel.SENSITIVE,
        "safari_navigate": RiskLevel.SENSITIVE,
        "safari_search": RiskLevel.SENSITIVE,
        "send_text_to_window": RiskLevel.SENSITIVE,
        "send_keys_to_window": RiskLevel.SENSITIVE,
        "batch_actions": RiskLevel.SENSITIVE,
        "computer": RiskLevel.SENSITIVE,

        # Destructive operations
        "run_program": RiskLevel.DESTRUCTIVE,
    }

    def __init__(self, policy: Optional[SecurityPolicy] = None):
        self.policy = policy or SecurityPolicy()

    def classify_action(self, tool_name: str, args: Dict[str, Any]) -> RiskLevel:
        base_risk = self.TOOL_RISK_MAP.get(tool_name, RiskLevel.WRITE)

        # Dynamic escalation based on targets
        if tool_name == "run_program":
            cmd = args.get("command", "")
            if not self.policy.is_command_safe(cmd):
                return RiskLevel.DESTRUCTIVE

        if tool_name in ("safari_navigate", "chrome_navigate"):
            url = args.get("url", "")
            if not self.policy.is_url_allowed(url):
                return RiskLevel.DESTRUCTIVE

        if tool_name in ("focus_window", "open_app", "send_text_to_window"):
            app = args.get("app_name", "")
            if not self.policy.is_app_allowed(app):
                return RiskLevel.DESTRUCTIVE

        return base_risk

    def authorize(self, tool_name: str, args: Dict[str, Any]) -> None:
        """Validates action authorization. Raises SecurityViolation or ActionDenied on failure."""
        risk = self.classify_action(tool_name, args)

        # 1. Target application check
        target_app = args.get("app_name")
        if target_app and not self.policy.is_app_allowed(target_app):
            raise SecurityViolation(
                f"Action '{tool_name}' blocked: Target application '{target_app}' is disallowed by security policy."
            )

        # 2. Target URL check
        target_url = args.get("url")
        if target_url and not self.policy.is_url_allowed(target_url):
            raise SecurityViolation(
                f"Action '{tool_name}' blocked: Target URL '{target_url}' is disallowed by security policy."
            )

        # 3. Shell execution check
        if tool_name == "run_program":
            cmd = args.get("command", "")
            if not self.policy.allow_shell_execution:
                raise SecurityViolation("Shell execution ('run_program') is disabled by security policy.")
            if not self.policy.is_command_safe(cmd):
                raise SecurityViolation(f"Command '{cmd}' contains forbidden shell patterns.")

        # 4. Maximum risk ceiling check
        if risk > self.policy.max_allowed_risk:
            # Check if approval policy allows escalation
            if risk >= self.policy.require_approval_above and self.policy.approval_callback:
                approved = self.policy.approval_callback(args, risk)
                if not approved:
                    raise ActionDenied(f"Action '{tool_name}' (Risk level {risk.name}) was rejected by user approval.")
            else:
                raise SecurityViolation(
                    f"Action '{tool_name}' requires risk level {risk.name}, exceeding current policy limit {self.policy.max_allowed_risk.name}."
                )

        if risk >= self.policy.require_approval_above and self.policy.approval_callback:
            if not self.policy.approval_callback(args, risk):
                raise ActionDenied(f"Action '{tool_name}' rejected by human approver.")

    _global_instance: Optional["ActionGuard"] = None

    @classmethod
    def get_instance(cls) -> "ActionGuard":
        if cls._global_instance is None:
            cls._global_instance = cls()
        return cls._global_instance


SecurityPolicyGuard = ActionGuard

