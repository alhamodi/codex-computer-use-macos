"""
Real-world validation task runner for macOS Computer Use Platform.

Implements safe, verifiable scenarios:
1. Scenario A: Live Desktop Observation & Freshness Invalidation.
2. Scenario B: Local Text File Writing, Reading & Hash Verification.
3. Scenario C: Cross-App Clipboard Data Pipe.
4. Scenario D: Non-Destructive DaVinci Resolve Process & Timeline Inspection.
"""

from __future__ import annotations
import hashlib
import os
import shutil
import tempfile
import time
from typing import Any, Dict, List, Optional

from computer_use.computer import Computer
from computer_use.observation import ObservationManager
from computer_use.verification import ActionVerifier


class RealWorldValidator:
    """Runs controlled, non-destructive validation tasks on the active macOS environment."""

    def __init__(self, computer: Optional[Computer] = None):
        self.computer = computer or Computer()
        self.obs_manager = ObservationManager(self.computer)
        self.verifier = ActionVerifier(self.computer)
        self.test_dir = tempfile.mkdtemp(prefix="computer_use_val_")

    def cleanup(self) -> None:
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def run_scenario_a_observation(self) -> Dict[str, Any]:
        """
        Scenario A: Live Desktop Observation & Freshness Invalidation.
        - Captures real desktop geometry, frontmost app, and OCR.
        - Tests TTL expiration check.
        """
        t0 = time.time()
        obs = self.obs_manager.capture_observation(target_width=1280, with_ocr=True, with_ax=False)
        dur = time.time() - t0

        evidence = {
            "screen": f"{obs.screen_width}x{obs.screen_height} @ {obs.scale_factor}x",
            "active_app": obs.active_app,
            "active_window": obs.active_window.get("window_title", ""),
            "ocr_lines": len(obs.ocr_lines),
            "screen_hash": obs.screen_hash,
            "observation_id": obs.observation_id,
        }

        # Check freshness logic
        assert not obs.is_expired, "Fresh observation should not be expired"

        return {
            "scenario": "Scenario A: Live Desktop Observation",
            "status": "PASSED",
            "duration_seconds": round(dur, 3),
            "evidence": evidence,
        }

    def run_scenario_b_file_task(self) -> Dict[str, Any]:
        """
        Scenario B: Local Text File Creation, Content Verification & SHA-256 Check.
        - Non-destructive: operates strictly inside isolated temp directory.
        """
        t0 = time.time()
        test_file = os.path.join(self.test_dir, "validation_note.txt")
        test_content = f"Computer Use Autonomous Verification - {time.time()}\nStatus: SUCCESS"

        # 1. Write file
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(test_content)

        # 2. Verify with ActionVerifier
        v_res = self.verifier.verify_file_generated(test_file, min_bytes=10, timeout=3.0)

        # 3. Read back & hash verify
        with open(test_file, "r", encoding="utf-8") as f:
            read_back = f.read()

        file_hash = hashlib.sha256(read_back.encode()).hexdigest()
        assert read_back == test_content

        return {
            "scenario": "Scenario B: File Generation & Content Verification",
            "status": "PASSED" if v_res.state.value == "success" else "FAILED",
            "duration_seconds": round(time.time() - t0, 3),
            "evidence": {
                "file_path": test_file,
                "file_size": len(read_back),
                "sha256": file_hash[:16],
                "verifier_state": v_res.state.value,
            },
        }

    def run_scenario_c_clipboard_pipe(self) -> Dict[str, Any]:
        """
        Scenario C: Clipboard Data Pipe Verification.
        - Safely writes unique token to macOS clipboard, reads it back via native Quartz/CoreGraphics.
        """
        t0 = time.time()
        token = f"cu_token_{int(time.time())}"
        self.computer.set_clipboard(token)
        time.sleep(0.1)
        retrieved = self.computer.get_clipboard()

        passed = (retrieved.strip() == token)
        return {
            "scenario": "Scenario C: Clipboard Pipe Verification",
            "status": "PASSED" if passed else "FAILED",
            "duration_seconds": round(time.time() - t0, 3),
            "evidence": {
                "injected_token": token,
                "retrieved_token": retrieved.strip(),
                "matched": passed,
            },
        }

    def run_scenario_d_davinci_status(self) -> Dict[str, Any]:
        """
        Scenario D: DaVinci Resolve Process & Project Status Check.
        - Non-invasive: checks running process and API readiness without triggering renders.
        """
        t0 = time.time()
        from computer_use.profiles.davinci import DaVinciResolveProfile
        davinci = DaVinciResolveProfile(self.computer)
        status = davinci.get_status()

        return {
            "scenario": "Scenario D: DaVinci Resolve Non-Invasive Status",
            "status": "PASSED" if status.get("is_running") else "BLOCKED_ENVIRONMENT",
            "duration_seconds": round(time.time() - t0, 3),
            "evidence": {
                "is_running": status.get("is_running", False),
                "note": "DaVinci is running" if status.get("is_running") else "DaVinci Resolve app is not running on host (expected if closed)",
            },
        }

    def run_all(self) -> List[Dict[str, Any]]:
        results = []
        results.append(self.run_scenario_a_observation())
        results.append(self.run_scenario_b_file_task())
        results.append(self.run_scenario_c_clipboard_pipe())
        results.append(self.run_scenario_d_davinci_status())
        return results
