"""
Unit & Integration Tests for macOS Computer Use using standard library unittest.
"""

import base64
import json
import os
import pathlib
import tempfile
import unittest

from computer_use.computer import Computer
from computer_use.mcp_server import MCPServer
from computer_use.schema import OPENAI_COMPUTER_TOOL, ANTHROPIC_COMPUTER_TOOL


class TestComputerUse(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.computer = Computer()

    def test_computer_init(self):
        self.assertTrue(os.path.exists(self.computer.binary_path))
        self.assertTrue(os.access(self.computer.binary_path, os.X_OK))

    def test_screen_info(self):
        info = self.computer.screen_info()
        self.assertIn("screens", info)
        screens = info["screens"]
        self.assertGreaterEqual(len(screens), 1)
        main = screens[0]
        self.assertGreater(main["width"], 0)
        self.assertGreater(main["height"], 0)
        self.assertGreaterEqual(main["scale"], 1.0)
        self.assertGreater(main["pixel_width"], 0)
        self.assertGreater(main["pixel_height"], 0)

    def test_active_window(self):
        win = self.computer.active_window()
        self.assertIn("application", win)
        self.assertIn("pid", win)
        self.assertGreater(win["pid"], 0)
        if "bounds" in win:
            self.assertGreater(win["bounds"]["width"], 0)
            self.assertGreater(win["bounds"]["height"], 0)

    def test_cursor_position(self):
        x, y = self.computer.cursor_position()
        self.assertIsInstance(x, int)
        self.assertIsInstance(y, int)

    def test_screenshot_base64(self):
        res = self.computer.screenshot(target_width=800)
        self.assertIn("base64", res)
        self.assertGreater(len(res["base64"]), 100)
        self.assertEqual(res["width"], 800)
        self.assertGreater(res["height"], 0)
        self.assertGreater(res["scale_ratio"], 0)
        
        raw = base64.b64decode(res["base64"])
        self.assertTrue(raw.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_screenshot_file(self):
        with tempfile.TemporaryDirectory() as td:
            out_file = str(pathlib.Path(td) / "shot.png")
            res = self.computer.screenshot(save_path=out_file)
            self.assertTrue(os.path.exists(out_file))
            self.assertGreater(os.path.getsize(out_file), 0)

    def test_screenshot_active_window(self):
        res = self.computer.screenshot_active_window()
        self.assertIn("base64", res)
        self.assertGreater(len(res["base64"]), 50)

    def test_observe_screen(self):
        obs = self.computer.observe_screen(target_width=1000)
        self.assertIn("screenshot", obs)
        self.assertIn("image_size", obs)
        self.assertIn("screen_size", obs)
        self.assertIn("active_window", obs)
        self.assertIn("cursor", obs)

    def test_list_windows(self):
        wins = self.computer.list_windows()
        self.assertIsInstance(wins, list)
        self.assertGreaterEqual(len(wins), 1)
        self.assertIn("application", wins[0])
        self.assertIn("pid", wins[0])

    def test_extract_text_ocr(self):
        ocr = self.computer.extract_text()
        self.assertIn("text", ocr)
        self.assertIn("lines", ocr)
        self.assertIsInstance(ocr["lines"], list)
        if len(ocr["lines"]) > 0:
            first = ocr["lines"][0]
            self.assertIn("text", first)
            self.assertIn("box", first)
            self.assertIn("center_x", first["box"])

    def test_clipboard_operations(self):
        test_str = "computer-use-macos-clipboard-test-12345"
        self.computer.set_clipboard(test_str)
        read_back = self.computer.get_clipboard()
        self.assertIn(test_str, read_back)

    def test_json_execution_single(self):
        res = self.computer.execute_json({"action": "cursor_position"})
        self.assertEqual(res.get("status"), "success")
        self.assertIn("output", res)

    def test_json_execution_batch(self):
        actions = [
            {"action": "mouse_move", "coordinate": [200, 200]},
            {"action": "cursor_position"}
        ]
        res = self.computer.execute_json(actions)
        self.assertEqual(res.get("status"), "success")
        self.assertEqual(res.get("output"), "200,200")

    def test_invalid_action(self):
        with self.assertRaises(RuntimeError):
            self.computer.execute_json({"action": "invalid_nonexistent_action"})

    def test_mcp_server_full_catalog(self):
        server = MCPServer()
        tools = server.list_tools()
        tool_names = [t["name"] for t in tools]
        
        expected_tools = [
            "computer", "screenshot", "screenshot_active_window", "observe_screen",
            "get_screen_size", "get_cursor_position", "extract_text", "extract_text_active_window",
            "click", "move_mouse", "drag_mouse", "type_text", "type_unicode",
            "press_key", "hotkey", "scroll", "list_windows", "focus_window",
            "open_app", "run_program", "get_window_text", "get_clipboard",
            "set_clipboard", "chrome_get_url", "chrome_get_tab_title", "chrome_navigate",
            "chrome_search", "chrome_read_page", "safari_get_url", "safari_get_tab_title",
            "safari_navigate", "safari_search", "safari_read_page",
            "send_text_to_window", "send_keys_to_window", "find_and_click_element",
            "batch_actions", "wait",
            "davinci_status", "davinci_switch_page", "davinci_project_manager",
            "davinci_open_project", "davinci_timeline_action",
            "som_observe", "click_mark",
            "human_click", "hover", "wait_until_condition", "handle_file_dialog", "verify_action_result",
            "accessibility_inspect", "create_session", "get_session_status", "cancel_session", "verify_file_output"
        ]
        
        for expected in expected_tools:
            self.assertIn(expected, tool_names, f"Tool {expected} missing from MCP server")

    def test_mcp_server_call_tools(self):
        server = MCPServer()
        
        # Test screen size
        res = server.call_tool("get_screen_size", {})
        self.assertEqual(len(res), 1)
        self.assertIn("screens", res[0]["text"])
        
        # Test cursor position
        res_cur = server.call_tool("get_cursor_position", {})
        self.assertIn("x", res_cur[0]["text"])

        # Test list windows
        res_win = server.call_tool("list_windows", {})
        self.assertEqual(len(res_win), 1)

    def test_user_takeover_and_easing_options(self):
        from computer_use.computer import UserTakeoverError
        c = Computer(smooth_cursor=True, move_duration=50, failsafe=True)
        self.assertTrue(c.smooth_cursor)
        self.assertEqual(c.move_duration, 50)
        self.assertTrue(c.failsafe)
        # Test cursor_position passes through execute_json with failsafe
        res = c.execute_json({"action": "cursor_position"})
        self.assertEqual(res.get("status"), "success")

    def test_som_creation(self):
        from PIL import Image
        from computer_use.som import create_som_overlay
        mock_img = Image.new("RGB", (800, 600), color=(50, 50, 50))
        mock_ocr = {
            "text": "File Edit Window",
            "lines": [
                {"text": "File", "box": {"x": 10, "y": 10, "width": 40, "height": 20, "center_x": 30, "center_y": 20}},
                {"text": "Edit", "box": {"x": 60, "y": 10, "width": 40, "height": 20, "center_x": 80, "center_y": 20}},
            ]
        }
        overlay_img, marks = create_som_overlay(mock_img, mock_ocr, scale_factor=1.0)
        self.assertEqual(len(marks), 2)
        self.assertEqual(marks[1]["text"], "File")
        self.assertEqual(marks[2]["text"], "Edit")
        self.assertEqual(overlay_img.size, (800, 600))

    def test_davinci_profile_methods(self):
        from computer_use.profiles.davinci import DaVinciResolveProfile
        profile = DaVinciResolveProfile(self.computer)
        status = profile.get_status()
        self.assertIn("running", status)
        self.assertIsInstance(profile.PAGES, dict)
        self.assertIn("edit", profile.PAGES)
        self.assertIn("deliver", profile.PAGES)

    def test_human_click_and_hover(self):
        # Hover
        res_hover = self.computer.hover(150, 150, duration_ms=20)
        self.assertEqual(res_hover.get("status"), "success")

        # Human click
        res_click = self.computer.human_click(150, 150, hover_ms=20, hold_ms=20)
        self.assertEqual(res_click.get("status"), "success")

    def test_wait_until_condition_window_title(self):
        # Current active window should match its own title substring quickly
        win = self.computer.active_window()
        title = win.get("title", "")
        if title:
            sub = title[:3]
            res = self.computer.wait_until_condition(
                condition="window_title_contains",
                target=sub,
                timeout=3.0,
                poll_interval=0.2
            )
            self.assertTrue(res.get("success"))

    def test_handle_file_dialog_nonexistent(self):
        res = self.computer.handle_file_dialog("/nonexistent_folder/nonexistent_file_xyz123.mp4")
        self.assertFalse(res.get("success"))
        self.assertIn("error", res)

    def test_verify_action_result_blocker(self):
        # Test detection of blockers
        from unittest.mock import patch
        mock_ocr = {
            "lines": [
                {"text": "Upload failed. File format not supported."},
                {"text": "Please try again."}
            ]
        }
        with patch.object(self.computer, "extract_text", return_value=mock_ocr):
            res = self.computer.verify_action_result(
                success_keywords=["shared", "published"],
                blocker_keywords=["failed", "error", "not supported"],
                timeout=1.0
            )
            self.assertEqual(res.get("status"), "blocked")
            self.assertIn("failed", res.get("blockers", []))

    # --- New Phase 1-5 Architectural & Security Tests ---

    def test_security_policy_enforcement(self):
        from computer_use.security import SecurityPolicy, ActionGuard, SecurityViolation, RiskLevel
        # Policy blocking shell execution
        strict_policy = SecurityPolicy(
            max_allowed_risk=RiskLevel.WRITE,
            allow_shell_execution=False,
            blocked_applications=["Console", "System Settings"]
        )
        guard = ActionGuard(strict_policy)
        
        # Safe read should pass
        guard.authorize("get_screen_size", {})
        
        # Shell execution should be blocked
        with self.assertRaises(SecurityViolation):
            guard.authorize("run_program", {"command": "echo test"})
            
        # Target blocked app should be blocked
        with self.assertRaises(SecurityViolation):
            guard.authorize("focus_window", {"app_name": "System Settings"})

    def test_session_lifecycle_and_cancellation(self):
        from computer_use.session import SessionManager, SessionState
        sm = SessionManager()
        sess = sm.create_session(target_app="Safari", goal="Test export workflow", max_steps=5)
        self.assertEqual(sess.state, SessionState.RUNNING)
        self.assertTrue(sess.is_active)
        
        # Record steps
        sess.record_step("click", {"x": 100, "y": 100}, {"status": "ok"})
        self.assertEqual(sess.steps_executed, 1)
        
        # Cancel session
        sm.cancel_active_session(reason="User stopped task")
        self.assertEqual(sess.state, SessionState.CANCELLED)
        self.assertTrue(sess.is_cancelled)

    def test_grounded_som_stale_rejection(self):
        from computer_use.som import GroundedMarkRegistry, StaleObservationError
        reg = GroundedMarkRegistry(ttl_seconds=0.05) # 50ms TTL
        reg.register(1, {"id": 1, "center_x": 200, "center_y": 300, "title": "Submit"})
        
        # Immediate read succeeds
        m = reg.get_mark(1, enforce_freshness=False)
        self.assertEqual(m["center_x"], 200)
        
        # Wait for expiration
        import time
        time.sleep(0.06)
        self.assertTrue(reg.is_expired)
        with self.assertRaises(StaleObservationError):
            reg.get_mark(1, enforce_freshness=True)

    def test_action_verifier_file(self):
        import tempfile
        with tempfile.NamedTemporaryFile(delete=True) as tmp:
            tmp.write(b"Hello DaVinci Export Render")
            tmp.flush()
            res = self.computer.verifier.verify_file_generated(tmp.name, min_bytes=5, timeout=1.0)
            self.assertEqual(res.state.value, "success")
            self.assertGreaterEqual(res.details.get("size_bytes", 0), 5)


if __name__ == "__main__":
    unittest.main()
