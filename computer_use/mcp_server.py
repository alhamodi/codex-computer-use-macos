"""
Model Context Protocol (MCP) Stdio Server for macOS Computer Use.

Provides full parity with codex-computer-use-windows adapted natively for macOS.
"""

from __future__ import annotations
import json
import sys
import traceback
from typing import Any, Dict, List

from computer_use.computer import Computer
from computer_use.schema import OPENAI_COMPUTER_TOOL


class MCPServer:
    def __init__(self):
        self.computer = Computer()

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            # Universal Tool
            {
                "name": "computer",
                "description": "Primary multimodal computer use tool: execute mouse, keyboard, hotkey, scroll, or screenshot actions.",
                "inputSchema": OPENAI_COMPUTER_TOOL["function"]["parameters"]
            },
            # Screen Category
            {
                "name": "screenshot",
                "description": "Capture screenshot of the full display. Returns base64 PNG image.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "target_width": {"type": "integer", "description": "Optional width to scale image (e.g. 1024 or 1280)"},
                        "save_path": {"type": "string", "description": "Optional path to save PNG file"}
                    }
                }
            },
            {
                "name": "screenshot_active_window",
                "description": "Capture screenshot of only the focused frontmost window.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "save_path": {"type": "string", "description": "Optional path to save PNG file"}
                    }
                }
            },
            {
                "name": "observe_screen",
                "description": "One-shot observation: returns screenshot image + active window info + cursor pos + display size in 1 turn.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "target_width": {"type": "integer", "default": 1280, "description": "Width for vision image"}
                    }
                }
            },
            {
                "name": "get_screen_size",
                "description": "Get screen resolution (points), Retina scale factor, and pixel dimensions.",
                "inputSchema": {"type": "object", "properties": {}}
            },
            {
                "name": "get_cursor_position",
                "description": "Get current mouse cursor position (x, y) in macOS points.",
                "inputSchema": {"type": "object", "properties": {}}
            },
            {
                "name": "extract_text",
                "description": "Extract on-screen text and bounding box coordinates using Apple Vision OCR.",
                "inputSchema": {"type": "object", "properties": {}}
            },
            {
                "name": "extract_text_active_window",
                "description": "Extract text and bounding box coordinates from only the active window using Apple Vision OCR.",
                "inputSchema": {"type": "object", "properties": {}}
            },
            # Mouse and Keyboard Category
            {
                "name": "click",
                "description": "Click at specified (x, y) coordinates on screen.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "x": {"type": "integer", "description": "X coordinate in points"},
                        "y": {"type": "integer", "description": "Y coordinate in points"},
                        "button": {"type": "string", "enum": ["left", "right", "middle"], "default": "left"}
                    },
                    "required": ["x", "y"]
                }
            },
            {
                "name": "move_mouse",
                "description": "Move mouse pointer to (x, y) coordinates.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "x": {"type": "integer", "description": "X coordinate in points"},
                        "y": {"type": "integer", "description": "Y coordinate in points"}
                    },
                    "required": ["x", "y"]
                }
            },
            {
                "name": "drag_mouse",
                "description": "Click and drag mouse from (start_x, start_y) to (end_x, end_y).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "start_x": {"type": "integer"},
                        "start_y": {"type": "integer"},
                        "end_x": {"type": "integer"},
                        "end_y": {"type": "integer"}
                    },
                    "required": ["start_x", "start_y", "end_x", "end_y"]
                }
            },
            {
                "name": "type_text",
                "description": "Type text into the frontmost application.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Text to type"}
                    },
                    "required": ["text"]
                }
            },
            {
                "name": "type_unicode",
                "description": "Type unicode or complex emoji text into active app using clipboard paste.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Text with emoji or unicode"}
                    },
                    "required": ["text"]
                }
            },
            {
                "name": "press_key",
                "description": "Press a key by name (return, space, escape, tab, delete, arrow-down, etc.).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string", "description": "Key identifier"}
                    },
                    "required": ["key"]
                }
            },
            {
                "name": "hotkey",
                "description": "Trigger a keyboard shortcut (e.g. ['cmd', 'c'], ['cmd', 'shift', 'p']).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "keys": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Modifiers and key"
                        }
                    },
                    "required": ["keys"]
                }
            },
            {
                "name": "scroll",
                "description": "Scroll mouse wheel. delta_y < 0 scrolls down, delta_y > 0 scrolls up.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "delta_y": {"type": "integer", "description": "Vertical scroll delta"},
                        "delta_x": {"type": "integer", "default": 0, "description": "Horizontal scroll delta"},
                        "x": {"type": "integer", "description": "Optional X position"},
                        "y": {"type": "integer", "description": "Optional Y position"}
                    },
                    "required": ["delta_y"]
                }
            },
            # Window Category
            {
                "name": "list_windows",
                "description": "List all open application windows on macOS with title, owner app, PID, and bounds.",
                "inputSchema": {"type": "object", "properties": {}}
            },
            {
                "name": "focus_window",
                "description": "Bring an application window to the foreground by app name or PID.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "app_name": {"type": "string", "description": "Name of app (e.g. Safari, Notes, Terminal)"},
                        "pid": {"type": "integer", "description": "Process ID"}
                    }
                }
            },
            {
                "name": "open_app",
                "description": "Launch or activate a macOS application by name.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "app_name": {"type": "string", "description": "Name of app (e.g. 'Safari', 'Notes', 'Visual Studio Code')"}
                    },
                    "required": ["app_name"]
                }
            },
            {
                "name": "run_program",
                "description": "Run a shell program/command in the terminal.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "Command string to run"}
                    },
                    "required": ["command"]
                }
            },
            {
                "name": "get_window_text",
                "description": "Extract all readable text from the frontmost active window.",
                "inputSchema": {"type": "object", "properties": {}}
            },
            # Clipboard Category
            {
                "name": "get_clipboard",
                "description": "Read text from the macOS system clipboard.",
                "inputSchema": {"type": "object", "properties": {}}
            },
            {
                "name": "set_clipboard",
                "description": "Write text to the macOS system clipboard.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Text to copy"}
                    },
                    "required": ["text"]
                }
            },
            # Browser Category (Safari & Chrome)
            {
                "name": "chrome_get_url",
                "description": "Get URL of active tab in Google Chrome.",
                "inputSchema": {"type": "object", "properties": {}}
            },
            {
                "name": "chrome_get_tab_title",
                "description": "Get title of active tab in Google Chrome.",
                "inputSchema": {"type": "object", "properties": {}}
            },
            {
                "name": "chrome_navigate",
                "description": "Navigate Google Chrome's active tab to a URL.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "Destination URL"}
                    },
                    "required": ["url"]
                }
            },
            {
                "name": "chrome_search",
                "description": "Search Google in Google Chrome.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "chrome_read_page",
                "description": "Get text content of active tab in Google Chrome.",
                "inputSchema": {"type": "object", "properties": {}}
            },
            {
                "name": "safari_get_url",
                "description": "Get URL of active tab in Safari.",
                "inputSchema": {"type": "object", "properties": {}}
            },
            {
                "name": "safari_get_tab_title",
                "description": "Get title of active tab in Safari.",
                "inputSchema": {"type": "object", "properties": {}}
            },
            {
                "name": "safari_navigate",
                "description": "Navigate Safari's active tab to a URL.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "Destination URL"}
                    },
                    "required": ["url"]
                }
            },
            {
                "name": "safari_search",
                "description": "Search Google in Safari.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "safari_read_page",
                "description": "Get text content of active tab in Safari.",
                "inputSchema": {"type": "object", "properties": {}}
            },
            # Chat and Messaging Category
            {
                "name": "send_text_to_window",
                "description": "Focus an application window, type/paste text, and optionally press Enter.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "app_name": {"type": "string", "description": "Name of app to target"},
                        "text": {"type": "string", "description": "Message text"},
                        "press_enter": {"type": "boolean", "default": True}
                    },
                    "required": ["app_name", "text"]
                }
            },
            {
                "name": "send_keys_to_window",
                "description": "Focus an application window and send key combination.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "app_name": {"type": "string", "description": "Name of app to target"},
                        "keys": {"type": "array", "items": {"type": "string"}, "description": "Keys (e.g. ['cmd', 'c'])"}
                    },
                    "required": ["app_name", "keys"]
                }
            },
            # UI Automation Category
            {
                "name": "find_and_click_element",
                "description": "Find an element by its text label using Apple Vision OCR and click its center.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Text on the button or element to click"},
                        "active_window_only": {"type": "boolean", "default": False}
                    },
                    "required": ["text"]
                }
            },
            # Utility Category
            {
                "name": "batch_actions",
                "description": "Execute a list of computer use actions sequentially.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "actions": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "List of action objects"
                        }
                    },
                    "required": ["actions"]
                }
            },
            {
                "name": "wait",
                "description": "Pause execution for milliseconds.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "ms": {"type": "integer", "description": "Milliseconds to pause"}
                    },
                    "required": ["ms"]
                }
            }
        ]

    def call_tool(self, name: str, args: Dict[str, Any]) -> List[Dict[str, Any]]:
        # Universal tool
        if name == "computer":
            action = args.get("action")
            if action == "screenshot":
                shot = self.computer.screenshot()
                return [
                    {"type": "image", "data": shot["base64"], "mimeType": "image/png"},
                    {"type": "text", "text": json.dumps({
                        "width": shot["width"],
                        "height": shot["height"],
                        "screen_width": shot["screen_width"],
                        "screen_height": shot["screen_height"],
                        "scale_ratio": shot["scale_ratio"]
                    }, indent=2)}
                ]
            else:
                res = self.computer.execute_json(args)
                return [{"type": "text", "text": json.dumps(res, indent=2)}]

        # Screen Category
        elif name == "screenshot":
            shot = self.computer.screenshot(target_width=args.get("target_width"), save_path=args.get("save_path"))
            return [
                {"type": "image", "data": shot["base64"], "mimeType": "image/png"},
                {"type": "text", "text": json.dumps({
                    "width": shot["width"],
                    "height": shot["height"],
                    "scale_ratio": shot["scale_ratio"],
                    "path": shot.get("path")
                }, indent=2)}
            ]

        elif name == "screenshot_active_window":
            shot = self.computer.screenshot_active_window(save_path=args.get("save_path"))
            return [
                {"type": "image", "data": shot["base64"], "mimeType": "image/png"},
                {"type": "text", "text": json.dumps({"status": "success", "path": shot.get("path")})}
            ]

        elif name == "observe_screen":
            obs = self.computer.observe_screen(target_width=args.get("target_width", 1280))
            return [
                {"type": "image", "data": obs["screenshot"], "mimeType": "image/png"},
                {"type": "text", "text": json.dumps({
                    "image_size": obs["image_size"],
                    "screen_size": obs["screen_size"],
                    "scale_ratio": obs["scale_ratio"],
                    "active_window": obs["active_window"],
                    "cursor": obs["cursor"]
                }, indent=2)}
            ]

        elif name == "get_screen_size":
            info = self.computer.screen_info()
            return [{"type": "text", "text": json.dumps(info, indent=2)}]

        elif name == "get_cursor_position":
            x, y = self.computer.cursor_position()
            return [{"type": "text", "text": json.dumps({"x": x, "y": y})}]

        elif name == "extract_text":
            res = self.computer.extract_text(active_window_only=False)
            return [{"type": "text", "text": json.dumps(res, indent=2)}]

        elif name == "extract_text_active_window":
            res = self.computer.extract_text(active_window_only=True)
            return [{"type": "text", "text": json.dumps(res, indent=2)}]

        # Mouse & Keyboard Category
        elif name == "click":
            res = self.computer.click(x=args["x"], y=args["y"], button=args.get("button", "left"))
            return [{"type": "text", "text": json.dumps(res, indent=2)}]

        elif name == "move_mouse":
            res = self.computer.move(x=args["x"], y=args["y"])
            return [{"type": "text", "text": json.dumps(res, indent=2)}]

        elif name == "drag_mouse":
            res = self.computer.drag(args["start_x"], args["start_y"], args["end_x"], args["end_y"])
            return [{"type": "text", "text": json.dumps(res, indent=2)}]

        elif name == "type_text":
            res = self.computer.type(args["text"])
            return [{"type": "text", "text": json.dumps(res, indent=2)}]

        elif name == "type_unicode":
            res = self.computer.type_unicode(args["text"])
            return [{"type": "text", "text": json.dumps(res, indent=2)}]

        elif name == "press_key":
            res = self.computer.key(args["key"])
            return [{"type": "text", "text": json.dumps(res, indent=2)}]

        elif name == "hotkey":
            res = self.computer.hotkey(*args["keys"])
            return [{"type": "text", "text": json.dumps(res, indent=2)}]

        elif name == "scroll":
            res = self.computer.scroll(
                delta_y=args["delta_y"],
                delta_x=args.get("delta_x", 0),
                x=args.get("x"),
                y=args.get("y")
            )
            return [{"type": "text", "text": json.dumps(res, indent=2)}]

        # Window Category
        elif name == "list_windows":
            wins = self.computer.list_windows()
            return [{"type": "text", "text": json.dumps(wins, indent=2)}]

        elif name == "focus_window":
            success = self.computer.focus_window(app_name=args.get("app_name"), pid=args.get("pid"))
            return [{"type": "text", "text": json.dumps({"success": success})}]

        elif name == "open_app":
            success = self.computer.open_app(args["app_name"])
            return [{"type": "text", "text": json.dumps({"success": success})}]

        elif name == "run_program":
            res = self.computer.run_program(args["command"])
            return [{"type": "text", "text": json.dumps(res, indent=2)}]

        elif name == "get_window_text":
            text = self.computer.get_window_text()
            return [{"type": "text", "text": text}]

        # Clipboard Category
        elif name == "get_clipboard":
            text = self.computer.get_clipboard()
            return [{"type": "text", "text": text}]

        elif name == "set_clipboard":
            self.computer.set_clipboard(args["text"])
            return [{"type": "text", "text": json.dumps({"success": True})}]

        # Browser Category
        elif name == "chrome_get_url":
            return [{"type": "text", "text": self.computer.browser_get_url(browser="Google Chrome")}]
        elif name == "chrome_get_tab_title":
            return [{"type": "text", "text": self.computer.browser_get_tab_title(browser="Google Chrome")}]
        elif name == "chrome_navigate":
            ok = self.computer.browser_navigate(args["url"], browser="Google Chrome")
            return [{"type": "text", "text": json.dumps({"success": ok})}]
        elif name == "chrome_search":
            ok = self.computer.browser_search(args["query"], browser="Google Chrome")
            return [{"type": "text", "text": json.dumps({"success": ok})}]
        elif name == "chrome_read_page":
            return [{"type": "text", "text": self.computer.browser_read_page(browser="Google Chrome")}]

        elif name == "safari_get_url":
            return [{"type": "text", "text": self.computer.browser_get_url(browser="Safari")}]
        elif name == "safari_get_tab_title":
            return [{"type": "text", "text": self.computer.browser_get_tab_title(browser="Safari")}]
        elif name == "safari_navigate":
            ok = self.computer.browser_navigate(args["url"], browser="Safari")
            return [{"type": "text", "text": json.dumps({"success": ok})}]
        elif name == "safari_search":
            ok = self.computer.browser_search(args["query"], browser="Safari")
            return [{"type": "text", "text": json.dumps({"success": ok})}]
        elif name == "safari_read_page":
            return [{"type": "text", "text": self.computer.browser_read_page(browser="Safari")}]

        # Chat and Messaging Category
        elif name == "send_text_to_window":
            ok = self.computer.send_text_to_window(
                args["app_name"],
                args["text"],
                press_enter=args.get("press_enter", True)
            )
            return [{"type": "text", "text": json.dumps({"success": ok})}]

        elif name == "send_keys_to_window":
            ok = self.computer.send_keys_to_window(args["app_name"], *args["keys"])
            return [{"type": "text", "text": json.dumps({"success": ok})}]

        # UI Automation Category
        elif name == "find_and_click_element":
            ok = self.computer.find_and_click_element(
                args["text"],
                active_window_only=args.get("active_window_only", False)
            )
            return [{"type": "text", "text": json.dumps({"clicked": ok})}]

        # Utility Category
        elif name == "batch_actions":
            res = self.computer.batch_actions(args["actions"])
            return [{"type": "text", "text": json.dumps(res, indent=2)}]

        elif name == "wait":
            res = self.computer.wait(args["ms"])
            return [{"type": "text", "text": json.dumps(res, indent=2)}]

        else:
            raise ValueError(f"Unknown tool: {name}")

    def run(self):
        """Run MCP stdio JSON-RPC loop."""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            try:
                req = json.loads(line)
            except json.JSONDecodeError:
                continue

            msg_id = req.get("id")
            method = req.get("method")
            params = req.get("params", {})

            if method == "initialize":
                resp = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "serverInfo": {
                            "name": "codex-computer-use-macos",
                            "version": "1.0.0"
                        },
                        "capabilities": {
                            "tools": {}
                        }
                    }
                }
                self._send(resp)

            elif method == "notifications/initialized":
                pass

            elif method == "tools/list":
                resp = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "tools": self.list_tools()
                    }
                }
                self._send(resp)

            elif method == "tools/call":
                tool_name = params.get("name")
                tool_args = params.get("arguments", {})
                try:
                    content = self.call_tool(tool_name, tool_args)
                    resp = {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {
                            "content": content,
                            "isError": False
                        }
                    }
                except Exception as e:
                    resp = {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {
                            "content": [{"type": "text", "text": f"Error: {str(e)}"}],
                            "isError": True
                        }
                    }
                self._send(resp)

            elif method == "ping":
                self._send({"jsonrpc": "2.0", "id": msg_id, "result": {}})

            else:
                if msg_id is not None:
                    self._send({
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "error": {
                            "code": -32601,
                            "message": f"Method not found: {method}"
                        }
                    })

    def _send(self, data: Dict[str, Any]):
        out = json.dumps(data)
        sys.stdout.write(out + "\n")
        sys.stdout.flush()


def main():
    server = MCPServer()
    server.run()


if __name__ == "__main__":
    main()
