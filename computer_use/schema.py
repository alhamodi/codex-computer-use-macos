"""
Tool definitions and schemas for AI Agents (Anthropic, OpenAI / Codex, Gemini).
"""

ANTHROPIC_COMPUTER_TOOL = {
    "name": "computer",
    "type": "computer_20241022",
    "display_width_px": 1440,
    "display_height_px": 900,
    "display_number": 1
}

OPENAI_COMPUTER_TOOL = {
    "type": "function",
    "function": {
        "name": "computer",
        "description": "Control the macOS computer: take screenshots, move and click the mouse, type text, trigger keyboard shortcuts, and scroll.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "The action to perform.",
                    "enum": [
                        "screenshot",
                        "left_click",
                        "right_click",
                        "middle_click",
                        "double_click",
                        "triple_click",
                        "mouse_move",
                        "mouse_down",
                        "mouse_up",
                        "left_click_drag",
                        "type",
                        "key",
                        "hotkey",
                        "scroll",
                        "cursor_position",
                        "screen_info",
                        "window_info",
                        "wait"
                    ]
                },
                "coordinate": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "The (x, y) coordinates for mouse actions in screen points."
                },
                "text": {
                    "type": "string",
                    "description": "The text to type, or key name for 'key' action (e.g. 'Return', 'Tab', 'Escape', 'space')."
                },
                "keys": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Modifier and key combination for 'hotkey' action (e.g. ['cmd', 'c'], ['cmd', 'shift', 'p'])."
                },
                "delta_y": {
                    "type": "integer",
                    "description": "Vertical scroll amount. Negative values scroll down, positive values scroll up."
                },
                "delta_x": {
                    "type": "integer",
                    "description": "Horizontal scroll amount. Positive values scroll right, negative values scroll left."
                },
                "ms": {
                    "type": "integer",
                    "description": "Milliseconds to wait for the 'wait' action."
                }
            },
            "required": ["action"]
        }
    }
}

GEMINI_COMPUTER_TOOL = {
    "function_declarations": [
        {
            "name": "computer",
            "description": "Control the macOS computer: take screenshots, move and click the mouse, type text, trigger keyboard shortcuts, and scroll.",
            "parameters": OPENAI_COMPUTER_TOOL["function"]["parameters"]
        }
    ]
}
