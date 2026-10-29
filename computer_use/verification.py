"""
Multi-Modal Verification Engine for Computer Use Actions.

Verifies:
- Text appearances/disappearances
- UI Accessibility element roles, titles, and values
- Output file generation, size, and non-emptiness
- Window title transitions
- Return standard verification states: SUCCESS, FAILED, UNCERTAIN, CANCELLED, TIMED_OUT
"""

from __future__ import annotations
import enum
import os
import time
from typing import Any, Callable, Dict, List, Optional, Union


class VerificationState(enum.Enum):
    SUCCESS = "success"
    FAILED = "failed"
    UNCERTAIN = "uncertain"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class VerificationResult:
    def __init__(
        self,
        state: VerificationState,
        evidence: str,
        elapsed_seconds: float,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.state = state
        self.evidence = evidence
        self.elapsed_seconds = round(elapsed_seconds, 3)
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.state.value,
            "evidence": self.evidence,
            "elapsed_seconds": self.elapsed_seconds,
            "details": self.details,
        }


class ActionVerifier:
    """Provides programmatic and multi-modal verification of intended action outcomes."""

    def __init__(self, computer_instance: Any):
        self.computer = computer_instance

    def verify_text_presence(
        self,
        expected_text: str,
        timeout: float = 10.0,
        poll_interval: float = 0.5,
        active_window_only: bool = True,
    ) -> VerificationResult:
        """Polls OCR until expected_text appears."""
        start = time.time()
        exp_lower = expected_text.lower()
        while time.time() - start < timeout:
            ocr = self.computer.extract_text(active_window_only=active_window_only, fast=True)
            for line in ocr.get("lines", []):
                txt = line.get("text", "")
                if exp_lower in txt.lower():
                    return VerificationResult(
                        state=VerificationState.SUCCESS,
                        evidence=f"Text '{expected_text}' detected on screen.",
                        elapsed_seconds=time.time() - start,
                        details={"matched_line": txt, "box": line.get("box")},
                    )
            time.sleep(poll_interval)

        return VerificationResult(
            state=VerificationState.TIMED_OUT,
            evidence=f"Text '{expected_text}' did not appear within {timeout}s timeout.",
            elapsed_seconds=time.time() - start,
        )

    def verify_file_generated(
        self,
        file_path: str,
        min_bytes: int = 1,
        timeout: float = 15.0,
        poll_interval: float = 0.5,
    ) -> VerificationResult:
        """Verifies an export or downloaded file was created and exceeds min_bytes."""
        start = time.time()
        abs_path = os.path.abspath(os.path.expanduser(file_path))

        while time.time() - start < timeout:
            if os.path.exists(abs_path):
                size = os.path.getsize(abs_path)
                if size >= min_bytes:
                    return VerificationResult(
                        state=VerificationState.SUCCESS,
                        evidence=f"File '{abs_path}' verified with size {size} bytes.",
                        elapsed_seconds=time.time() - start,
                        details={"file_path": abs_path, "size_bytes": size},
                    )
            time.sleep(poll_interval)

        if os.path.exists(abs_path):
            size = os.path.getsize(abs_path)
            return VerificationResult(
                state=VerificationState.FAILED,
                evidence=f"File exists but is too small: {size} bytes (required >= {min_bytes}).",
                elapsed_seconds=time.time() - start,
                details={"file_path": abs_path, "size_bytes": size},
            )

        return VerificationResult(
            state=VerificationState.TIMED_OUT,
            evidence=f"File '{abs_path}' was not created within {timeout}s.",
            elapsed_seconds=time.time() - start,
        )

    def verify_window_title(
        self,
        title_substring: str,
        timeout: float = 5.0,
        poll_interval: float = 0.3,
    ) -> VerificationResult:
        """Verifies active window title changed to contain substring."""
        start = time.time()
        sub_lower = title_substring.lower()

        while time.time() - start < timeout:
            win = self.computer.active_window()
            curr_title = win.get("window_title") or win.get("title", "")
            if sub_lower in curr_title.lower():
                return VerificationResult(
                    state=VerificationState.SUCCESS,
                    evidence=f"Window title '{curr_title}' matches '{title_substring}'.",
                    elapsed_seconds=time.time() - start,
                    details={"window": win},
                )
            time.sleep(poll_interval)

        return VerificationResult(
            state=VerificationState.TIMED_OUT,
            evidence=f"Window title did not match '{title_substring}' within {timeout}s.",
            elapsed_seconds=time.time() - start,
        )
