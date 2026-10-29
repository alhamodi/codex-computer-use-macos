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
        self._davinci = None

    @property
    def davinci(self):
        if self._davinci is None:
            from computer_use.profiles.davinci import DaVinciResolveProfile
            self._davinci = DaVinciResolveProfile(self.computer)
        return self._davinci

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
            },
            # DaVinci Resolve 21 Category
            {
                "name": "davinci_status",
                "description": "Get operational status of DaVinci Resolve (running state, active project name, window bounds, project manager visibility).",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "davinci_switch_page",
                "description": "Switch to a DaVinci Resolve workspace page (media, cut, edit, fusion, color, fairlight, deliver) using native macOS menu automation.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "page": {
                            "type": "string",
                            "enum": ["media", "cut", "edit", "fusion", "color", "fairlight", "deliver"],
                            "description": "The workspace page to switch to"
                        }
                    },
                    "required": ["page"]
                }
            },
            {
                "name": "davinci_project_manager",
                "description": "Control DaVinci Resolve Project Manager (open, close, or list visible projects).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["open", "close", "list"],
                            "description": "Action to perform on Project Manager"
                        }
                    },
                    "required": ["action"]
                }
            },
            {
                "name": "davinci_open_project",
                "description": "Open a specific project by name from the DaVinci Resolve Project Manager.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project_name": {
                            "type": "string",
                            "description": "Name of the project to open"
                        }
                    },
                    "required": ["project_name"]
                }
            },
            {
                "name": "davinci_timeline_action",
                "description": "Execute timeline actions in DaVinci Resolve: play_pause, fit_timeline, split_clip, zoom_in, zoom_out, toggle_snapping, save_project, import_media.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": [
                                "play_pause",
                                "fit_timeline",
                                "split_clip",
                                "zoom_in",
                                "zoom_out",
                                "toggle_snapping",
                                "save_project",
                                "import_media"
                            ],
                            "description": "The timeline action to perform"
                        }
                    },
                    "required": ["action"]
                }
            },
            # Visual Grounding / Set-of-Marks (SoM)
            {
                "name": "som_observe",
                "description": "Capture screen and overlay Set-of-Marks (numbered badges on detected UI elements) for reliable grounding by vision models.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "active_window_only": {"type": "boolean", "description": "Only capture frontmost window", "default": False},
                        "save_path": {"type": "string", "description": "Optional file path to save annotated PNG"}
                    }
                }
            },
            {
                "name": "click_mark",
                "description": "Click a numbered UI element mark identified from som_observe.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "mark_id": {"type": "integer", "description": "Numeric badge ID of mark to click"},
                        "marks": {"type": "object", "description": "Marks registry dictionary returned from som_observe"}
                    },
                    "required": ["mark_id", "marks"]
                }
            },
            # Smart Automation & Humanized Interaction
            {
                "name": "human_click",
                "description": "Execute a realistic 3-phase human click: smooth cursor movement with easing, hover dwell (triggers React/DOM pointerover), and hold duration before release.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "x": {"type": "integer", "description": "X coordinate in screen points"},
                        "y": {"type": "integer", "description": "Y coordinate in screen points"},
                        "hover_ms": {"type": "integer", "description": "Hover dwell time in ms before pressing", "default": 150},
                        "hold_ms": {"type": "integer", "description": "Hold duration in ms before releasing", "default": 80}
                    },
                    "required": ["x", "y"]
                }
            },
            {
                "name": "hover",
                "description": "Move cursor to (x, y) and hover there for duration_ms to trigger CSS/DOM hover and pointerover events.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "x": {"type": "integer", "description": "X coordinate in screen points"},
                        "y": {"type": "integer", "description": "Y coordinate in screen points"},
                        "duration_ms": {"type": "integer", "description": "Hover duration in ms", "default": 200}
                    },
                    "required": ["x", "y"]
                }
            },
            {
                "name": "wait_until_condition",
                "description": "Intelligent state polling engine: wait for text_appears, text_disappears, or window_title_contains instead of brittle sleeps.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "condition": {
                            "type": "string",
                            "enum": ["text_appears", "text_disappears", "window_title_contains"],
                            "description": "Condition type to wait for"
                        },
                        "target": {"type": "string", "description": "Target text or substring"},
                        "timeout": {"type": "number", "description": "Max timeout in seconds", "default": 30.0},
                        "poll_interval": {"type": "number", "description": "Seconds between checks", "default": 0.8},
                        "active_window_only": {"type": "boolean", "description": "Limit OCR search to active window", "default": False}
                    },
                    "required": ["condition", "target"]
                }
            },
            {
                "name": "handle_file_dialog",
                "description": "Automate macOS Open/Save file chooser sheet (Cmd+Shift+G, input path, confirm).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Absolute or home-relative path of file to select"},
                        "timeout": {"type": "number", "description": "Max timeout in seconds", "default": 10.0}
                    },
                    "required": ["file_path"]
                }
            },
            {
                "name": "verify_action_result",
                "description": "Verify action outcome by watching for success indicators while watching for blocker keywords (terms agreement, copyright warnings, errors).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "success_keywords": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of keywords indicating success (e.g. ['shared', 'published'])"
                        },
                        "blocker_keywords": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of keywords indicating blockers (e.g. ['agree', 'terms', 'error'])"
                        },
                        "timeout": {"type": "number", "description": "Max timeout in seconds", "default": 15.0}
                    },
                    "required": ["success_keywords"]
                }
            },
            # Enterprise & Safety Category
            {
                "name": "accessibility_inspect",
                "description": "Inspect macOS native Accessibility UI hierarchy (buttons, fields, checkboxes) with roles, bounds, and states.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "max_depth": {"type": "integer", "description": "Maximum tree traversal depth", "default": 4}
                    }
                }
            },
            {
                "name": "create_session",
                "description": "Create an isolated execution session with step limits and timeout tracking.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "target_app": {"type": "string", "description": "Target macOS application name"},
                        "goal": {"type": "string", "description": "Goal or description of the task"},
                        "max_steps": {"type": "integer", "description": "Maximum allowed steps", "default": 100},
                        "timeout_seconds": {"type": "number", "description": "Session timeout in seconds", "default": 300.0}
                    }
                }
            },
            {
                "name": "get_session_status",
                "description": "Get status, elapsed time, and history length of the active or specified session.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string", "description": "Optional session UUID"}
                    }
                }
            },
            {
                "name": "cancel_session",
                "description": "Immediately cancel the active session and halt all execution.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "reason": {"type": "string", "description": "Reason for cancellation", "default": "User cancellation requested"}
                    }
                }
            },
            {
                "name": "verify_file_output",
                "description": "Verify an export or downloaded file exists and meets minimum byte size requirements.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "File path to verify"},
                        "min_bytes": {"type": "integer", "description": "Minimum expected file size in bytes", "default": 1},
                        "timeout": {"type": "number", "description": "Timeout in seconds", "default": 15.0}
                    },
                    "required": ["file_path"]
                }
            }
        ]

    def call_tool(self, name: str, args: Dict[str, Any]) -> List[Dict[str, Any]]:
        # 1. Authorize action against Security Policy
        self.computer.guard.authorize(name, args)

        # 2. Record step in active session if present
        active_sess = self.computer.session_manager.get_session()
        if active_sess and active_sess.is_cancelled:
            raise RuntimeError(f"Session {active_sess.session_id} is cancelled: {active_sess.stop_reason}")

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

        # DaVinci Resolve Category
        elif name == "davinci_status":
            res = self.davinci.get_status()
            return [{"type": "text", "text": json.dumps(res, indent=2)}]

        elif name == "davinci_switch_page":
            ok = self.davinci.switch_to_page(args["page"])
            return [{"type": "text", "text": json.dumps({"page": args["page"], "success": ok}, indent=2)}]

        elif name == "davinci_project_manager":
            action = args["action"]
            if action == "open":
                ok = self.davinci.open_project_manager()
                return [{"type": "text", "text": json.dumps({"action": "open", "success": ok}, indent=2)}]
            elif action == "close":
                ok = self.davinci.close_project_manager()
                return [{"type": "text", "text": json.dumps({"action": "close", "success": ok}, indent=2)}]
            elif action == "list":
                projects = self.davinci.list_projects_in_manager()
                return [{"type": "text", "text": json.dumps({"projects": projects, "count": len(projects)}, indent=2)}]
            else:
                raise ValueError(f"Unknown project manager action: {action}")

        elif name == "davinci_open_project":
            ok = self.davinci.open_project(args["project_name"])
            return [{"type": "text", "text": json.dumps({"project_name": args["project_name"], "success": ok}, indent=2)}]

        elif name == "davinci_timeline_action":
            action = args["action"]
            method_map = {
                "play_pause": self.davinci.play_pause,
                "fit_timeline": self.davinci.fit_timeline,
                "split_clip": self.davinci.split_clip,
                "zoom_in": self.davinci.zoom_in_timeline,
                "zoom_out": self.davinci.zoom_out_timeline,
                "toggle_snapping": self.davinci.toggle_snapping,
                "save_project": self.davinci.save_project,
                "import_media": self.davinci.import_media,
            }
            if action in method_map:
                ok = method_map[action]()
                return [{"type": "text", "text": json.dumps({"action": action, "success": ok}, indent=2)}]
            else:
                raise ValueError(f"Unknown timeline action: {action}")

        # Set-of-Marks (SoM) Category
        elif name == "som_observe":
            res = self.computer.som_observe(
                active_window_only=args.get("active_window_only", False),
                save_path=args.get("save_path")
            )
            return [
                {"type": "image", "data": res["base64"], "mimeType": "image/png"},
                {"type": "text", "text": json.dumps({
                    "count": res["count"],
                    "marks": res["marks"],
                    "path": res.get("image_path")
                }, indent=2)}
            ]

        elif name == "click_mark":
            ok = self.computer.click_mark(args["mark_id"], args["marks"])
            return [{"type": "text", "text": json.dumps({"clicked": ok})}]

        # Smart Automation Handlers
        elif name == "human_click":
            res = self.computer.human_click(
                x=args["x"],
                y=args["y"],
                hover_ms=args.get("hover_ms", 150),
                hold_ms=args.get("hold_ms", 80)
            )
            return [{"type": "text", "text": json.dumps(res, indent=2)}]

        elif name == "hover":
            res = self.computer.hover(
                x=args["x"],
                y=args["y"],
                duration_ms=args.get("duration_ms", 200)
            )
            return [{"type": "text", "text": json.dumps(res, indent=2)}]

        elif name == "wait_until_condition":
            res = self.computer.wait_until_condition(
                condition=args["condition"],
                target=args["target"],
                timeout=args.get("timeout", 30.0),
                poll_interval=args.get("poll_interval", 0.8),
                active_window_only=args.get("active_window_only", False)
            )
            return [{"type": "text", "text": json.dumps(res, indent=2)}]

        elif name == "handle_file_dialog":
            res = self.computer.handle_file_dialog(
                file_path=args["file_path"],
                timeout=args.get("timeout", 10.0)
            )
            return [{"type": "text", "text": json.dumps(res, indent=2)}]

        elif name == "verify_action_result":
            res = self.computer.verify_action_result(
                success_keywords=args["success_keywords"],
                blocker_keywords=args.get("blocker_keywords"),
                timeout=args.get("timeout", 15.0)
            )
            return [{"type": "text", "text": json.dumps(res, indent=2)}]

        # Enterprise, Session & Verification Handlers
        elif name == "accessibility_inspect":
            elements = self.computer.accessibility.inspect_frontmost(max_depth=args.get("max_depth", 4))
            return [{"type": "text", "text": json.dumps({"count": len(elements), "elements": elements}, indent=2)}]

        elif name == "create_session":
            sess = self.computer.session_manager.create_session(
                target_app=args.get("target_app"),
                goal=args.get("goal"),
                max_steps=args.get("max_steps", 100),
                timeout_seconds=args.get("timeout_seconds", 300.0)
            )
            return [{"type": "text", "text": json.dumps(sess.to_dict(), indent=2)}]

        elif name == "get_session_status":
            sess = self.computer.session_manager.get_session(args.get("session_id"))
            if not sess:
                return [{"type": "text", "text": json.dumps({"error": "No active session found"}, indent=2)}]
            return [{"type": "text", "text": json.dumps(sess.to_dict(), indent=2)}]

        elif name == "cancel_session":
            sess = self.computer.session_manager.cancel_active_session(reason=args.get("reason", "Cancelled by user"))
            if not sess:
                return [{"type": "text", "text": json.dumps({"status": "no_active_session"}, indent=2)}]
            return [{"type": "text", "text": json.dumps(sess.to_dict(), indent=2)}]

        elif name == "verify_file_output":
            vres = self.computer.verifier.verify_file_generated(
                file_path=args["file_path"],
                min_bytes=args.get("min_bytes", 1),
                timeout=args.get("timeout", 15.0)
            )
            return [{"type": "text", "text": json.dumps(vres.to_dict(), indent=2)}]

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
