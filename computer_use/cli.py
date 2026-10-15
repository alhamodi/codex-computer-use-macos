"""
Command Line Interface for Computer Use macOS.
"""

from __future__ import annotations
import argparse
import json
import sys
from computer_use.computer import Computer


def main():
    parser = argparse.ArgumentParser(
        prog="computer-use",
        description="macOS Computer Use Automation & AI Agent Interface"
    )
    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")

    # click
    click_p = subparsers.add_parser("click", help="Left click at (x, y)")
    click_p.add_argument("x", type=int, help="X coordinate")
    click_p.add_argument("y", type=int, help="Y coordinate")

    # rclick
    rclick_p = subparsers.add_parser("rclick", help="Right click at (x, y)")
    rclick_p.add_argument("x", type=int, help="X coordinate")
    rclick_p.add_argument("y", type=int, help="Y coordinate")

    # mclick
    mclick_p = subparsers.add_parser("mclick", help="Middle click at (x, y)")
    mclick_p.add_argument("x", type=int, help="X coordinate")
    mclick_p.add_argument("y", type=int, help="Y coordinate")

    # move
    move_p = subparsers.add_parser("move", help="Move cursor to (x, y)")
    move_p.add_argument("x", type=int, help="X coordinate")
    move_p.add_argument("y", type=int, help="Y coordinate")

    # type
    type_p = subparsers.add_parser("type", help="Type text into active app")
    type_p.add_argument("text", help="Text to type")

    # key
    key_p = subparsers.add_parser("key", help="Press key (e.g. return, esc, tab)")
    key_p.add_argument("key_name", help="Name of key")

    # hotkey
    hk_p = subparsers.add_parser("hotkey", help="Trigger hotkey shortcut (e.g. cmd c)")
    hk_p.add_argument("keys", nargs="+", help="Modifiers and key (e.g. cmd shift p)")

    # scroll
    scroll_p = subparsers.add_parser("scroll", help="Scroll mouse wheel")
    scroll_p.add_argument("delta_y", type=int, help="Vertical delta (negative = down, positive = up)")
    scroll_p.add_argument("--delta-x", type=int, default=0, help="Horizontal delta")
    scroll_p.add_argument("--x", type=int, default=None, help="X position")
    scroll_p.add_argument("--y", type=int, default=None, help="Y position")

    # screenshot
    shot_p = subparsers.add_parser("shot", help="Capture screenshot")
    shot_p.add_argument("path", nargs="?", default=None, help="Path to save PNG")
    shot_p.add_argument("--width", type=int, default=None, help="Scale to width")

    # info
    subparsers.add_parser("info", help="Get display and screen resolution info")

    # window
    subparsers.add_parser("window", help="Get frontmost window information")

    # cursor
    subparsers.add_parser("cursor", help="Get current cursor position")

    # mcp
    subparsers.add_parser("mcp", help="Launch Model Context Protocol (MCP) server")

    # agent
    agent_p = subparsers.add_parser("agent", help="Run autonomous vision agent loop")
    agent_p.add_argument("goal", help="Task for the agent to accomplish")
    agent_p.add_argument("--steps", type=int, default=15, help="Maximum steps")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    comp = Computer()

    if args.command == "click":
        comp.click(args.x, args.y)
    elif args.command == "rclick":
        comp.right_click(args.x, args.y)
    elif args.command == "mclick":
        comp.middle_click(args.x, args.y)
    elif args.command == "move":
        comp.move(args.x, args.y)
    elif args.command == "type":
        comp.type(args.text)
    elif args.command == "key":
        comp.key(args.key_name)
    elif args.command == "hotkey":
        comp.hotkey(*args.keys)
    elif args.command == "scroll":
        comp.scroll(x=args.x, y=args.y, delta_y=args.delta_y, delta_x=args.delta_x)
    elif args.command == "shot":
        res = comp.screenshot(save_path=args.path, target_width=args.width)
        if args.path:
            print(f"Screenshot saved to {args.path} ({res['width']}x{res['height']})")
        else:
            print(res["base64"][:100] + "... (truncated)")
    elif args.command == "info":
        print(json.dumps(comp.screen_info(), indent=2))
    elif args.command == "window":
        print(json.dumps(comp.active_window(), indent=2))
    elif args.command == "cursor":
        x, y = comp.cursor_position()
        print(f"Cursor: {x}, {y}")
    elif args.command == "mcp":
        from computer_use.mcp_server import main as mcp_main
        mcp_main()
    elif args.command == "agent":
        from computer_use.agent import run_agent_openai
        run_agent_openai(args.goal, max_steps=args.steps)


if __name__ == "__main__":
    main()
