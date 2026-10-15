"""
Autonomous Computer Use Agent Loop.

Orchestrates multimodal vision models (OpenAI, Anthropic, Gemini) with
native macOS Computer Use execution.
"""

from __future__ import annotations
import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

from computer_use.computer import Computer
from computer_use.schema import OPENAI_COMPUTER_TOOL


def run_agent_openai(goal: str, max_steps: int = 15, api_key: Optional[str] = None):
    """Run autonomous loop using OpenAI GPT-4o / Codex with Computer Use."""
    try:
        from openai import OpenAI
    except ImportError:
        print("Please install openai: pip install openai")
        sys.exit(1)

    client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))
    computer = Computer()

    system_prompt = (
        "You are an autonomous computer-use agent running directly on a macOS computer.\n"
        "You can inspect the screen, click, drag, type, press keys, trigger hotkeys, and scroll.\n"
        "Guidelines:\n"
        "1. Every turn, inspect the latest screenshot to understand current state.\n"
        "2. Coordinate space is macOS points (e.g. 1440x900). Use the coordinates shown on screen.\n"
        "3. Once the goal is completed, output a clear summary of what you did without making any more tool calls."
    )

    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": [{"type": "text", "text": f"Goal: {goal}"}]}
    ]

    print(f"\n🚀 Starting Computer Use Agent for goal: '{goal}'")
    step = 0

    while step < max_steps:
        step += 1
        print(f"\n--- [Step {step}/{max_steps}] ---")

        # Take screenshot for vision
        shot = computer.screenshot(target_width=1280)
        shot_b64 = shot["base64"]

        # Append screenshot as vision input
        messages.append({
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{shot_b64}",
                        "detail": "high"
                    }
                },
                {
                    "type": "text",
                    "text": f"Current screen state (scaled to {shot['width']}x{shot['height']}). What is your next action?"
                }
            ]
        })

        print("🧠 Thinking...")
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=[OPENAI_COMPUTER_TOOL],
            tool_choice="auto"
        )

        msg = response.choices[0].message
        messages.append(msg)

        if not msg.tool_calls:
            print(f"\n✅ Goal reached / Agent finished:\n{msg.content}")
            break

        for tool_call in msg.tool_calls:
            call_id = tool_call.id
            fn_name = tool_call.function.name
            args_str = tool_call.function.arguments
            args = json.loads(args_str)

            action = args.get("action")
            coord = args.get("coordinate")
            text = args.get("text")
            print(f"⚡ Action: {action} (coordinate: {coord}, text: {text})")

            # Execute action
            try:
                result = computer.execute_json(args)
                result_str = json.dumps(result)
            except Exception as e:
                result_str = json.dumps({"status": "error", "message": str(e)})

            messages.append({
                "role": "tool",
                "tool_call_id": call_id,
                "content": result_str
            })

        time.sleep(1.0)


def main():
    parser = argparse.ArgumentParser(description="Autonomous Computer Use Agent")
    parser.add_argument("goal", help="The task you want the agent to achieve")
    parser.add_argument("--max-steps", type=int, default=15, help="Maximum number of loop steps")
    args = parser.parse_args()

    run_agent_openai(args.goal, max_steps=args.max_steps)


if __name__ == "__main__":
    main()
