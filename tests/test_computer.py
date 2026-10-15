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
            "batch_actions", "wait"
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


if __name__ == "__main__":
    unittest.main()
