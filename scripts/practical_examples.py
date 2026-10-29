"""
Practical End-to-End Workflow Examples for macOS Computer Use Platform.
Demonstrates:
- Example 1: Non-invasive UI inspection & Accessibility role discovery.
- Example 2: Form typing & unicode validation without final submission.
- Example 3: File dialog handler with test directory verification.
- Example 4: DaVinci Resolve status discovery and safe page transition check.
- Example 5: Complete lifecycle (Goal -> Scope -> Execution -> Verification).
"""

from __future__ import annotations
import os
import sys
import tempfile
import time
from computer_use.computer import Computer
from computer_use.security import RiskLevel, SecurityPolicy


def example_1_interface_inspection():
    print("\n--- Example 1: Non-Invasive UI & Accessibility Inspection ---")
    c = Computer()
    win = c.active_window()
    print(f"Focused Window: {win.get('application')} - Title: '{win.get('window_title')}'")
    ax_elems = c.accessibility.inspect_frontmost()
    print(f"Discovered {len(ax_elems)} interactive Accessibility elements (sample 3):")
    for elem in ax_elems[:3]:
        print(f" - [{elem['role']}] '{elem['title']}' at ({elem['center_x']}, {elem['center_y']})")


def example_2_safe_data_input():
    print("\n--- Example 2: Safe Data Input & Unicode Validation ---")
    c = Computer()
    test_text = "تجربة إدخال آمنة - Safe Input 123"
    old_clip = c.get_clipboard()
    c.set_clipboard(test_text)
    read_back = c.get_clipboard()
    assert read_back == test_text, "Clipboard mismatch"
    print(f"Unicode string validated cleanly through macOS clipboard: '{read_back}'")
    if old_clip:
        c.set_clipboard(old_clip)


def example_3_file_dialog_verification():
    print("\n--- Example 3: File Selection & Verification ---")
    c = Computer()
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        f.write(b"Computer Use Platform Test File")
        temp_path = f.name

    try:
        vres = c.verifier.verify_file_generated(temp_path, min_bytes=10, timeout=1.0)
        print(f"Verification result: {vres.state.value} | {vres.evidence}")
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def example_4_davinci_resolve_safe_query():
    print("\n--- Example 4: DaVinci Resolve Safe Operational Query ---")
    from computer_use.profiles.davinci import DaVinciResolveProfile
    c = Computer()
    profile = DaVinciResolveProfile(c)
    status = profile.get_status()
    print(f"DaVinci Resolve operational status: Running={status.get('running')}")
    if status.get("running"):
        print(f"Active Project: {status.get('project_name')}")


def example_5_complete_guarded_task():
    print("\n--- Example 5: Complete Guarded Lifecycle Task ---")
    c = Computer()
    session = c.session_manager.create_session(
        target_app="Safari",
        goal="Demonstrate full audit and guarded execution lifecycle",
        max_steps=5
    )
    print(f"Session started: {session.session_id} | State: {session.state.value}")

    # Step 1: Read screen size
    size = c.screen_info()
    session.record_step("get_screen_size", {}, size["screens"][0])

    # Step 2: Verification check
    v = c.verifier.verify_window_title(title_substring="Safari", timeout=1.0)
    session.record_step("verify_window_title", {"title": "Safari"}, v.to_dict())

    session.complete("Lifecycle demonstration finished successfully")
    print(f"Session {session.session_id} ended: {session.state.value} in {session.elapsed_seconds}s across {session.steps_executed} steps.")


if __name__ == "__main__":
    example_1_interface_inspection()
    example_2_safe_data_input()
    example_3_file_dialog_verification()
    example_4_davinci_resolve_safe_query()
    example_5_complete_guarded_task()
