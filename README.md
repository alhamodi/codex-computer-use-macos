# cliclick: Computer Use Edition 🚀

> **Upgraded for Modern AI Agents & Desktop Automation**  
> High-performance macOS computer interaction engine compatible with **OpenAI Codex Operator**, **Anthropic Computer Use**, **Gemini**, and the **Model Context Protocol (MCP)**.

Written in Objective-C and Python, running natively on macOS (with full support for macOS 14 Sonoma & macOS 15 Sequoia Apple Silicon/Intel).

---

## 🌟 What's New in the Computer Use Edition

1. **Humanized Smooth Cursor Motion & Easing (`cubicEaseInOut`)**:
   - Continuous, human-like visible cursor paths at ~120Hz updates instead of instant coordinate teleportation.
   - Configurable move duration in CLI and Python SDK (`move_duration=120ms`).

2. **User Takeover Fail-safe Protection (`-u` / `failsafe`)**:
   - Real-time physical mouse drift monitoring (>35pt).
   - If the user moves their physical mouse during automation, execution aborts instantly with `UserTakeoverError` / `user_takeover`, guaranteeing user sovereignty over the desktop.

3. **Sub-Second Native Apple Vision OCR**:
   - Optimized with `VNRequestTextRecognitionLevelFast` and window ROI cropping, reducing OCR time from 58.5s down to **< 870ms** (67x speedup).

4. **Visual Grounding with Set-of-Marks (SoM)**:
   - Overlays numbered badge pills over detected interactive UI elements.
   - AI models reference marks by index (`som_observe` ➔ `click_mark(3)`) eliminating pixel-guessing hallucinations.

5. **DaVinci Resolve 21 Specialized Profile (`computer_use.profiles.davinci`)**:
   - Deep native automation for Blackmagic Design DaVinci Resolve 21.
   - Instant workspace page switching (`media`, `cut`, `edit`, `fusion`, `color`, `fairlight`, `deliver`) via macOS menu bar API in < 20ms.
   - Non-destructive project manager discovery and card interaction without hardcoded coordinates.

6. **Native Scrolling (`s:coords,dy[,dx]` or `s:dy`)**:
   - Full vertical & horizontal scroll wheel simulation via CoreGraphics.
   - Example: `cliclick s:500,300,-5` (scroll down 5 lines at coordinates 500, 300).
   - Example: `cliclick s:-10` (scroll down 10 lines at current location).

7. **Native Screenshots (`sc:[path]` or `sc:-`)**:
   - Capture display screenshots directly to a PNG file or output as base64 string to stdout.
   - Example: `cliclick sc:/tmp/screen.png`
   - Example: `cliclick sc:-` (outputs base64 PNG string for vision models).

8. **Middle Click (`mc:coords`)**:
   - Emulates middle mouse button (mouse button 2/3) clicks.
   - Example: `cliclick mc:250,400`

9. **Atomic Hotkeys (`hk:modifier+key`)**:
   - Single command to press modifier keys (`cmd`, `shift`, `alt`/`opt`, `ctrl`, `fn`), hit the target key, and release.
   - ANSI keycode fallback ensures reliable hotkeys even when the active macOS keyboard layout is Arabic or non-Latin.
   - Example: `cliclick hk:cmd,c` (Copy)
   - Example: `cliclick hk:cmd+shift+p`
   - Example: `cliclick hk:cmd,space` (Spotlight search)

10. **Display & Screen Info (`si`)**:
    - Returns structured JSON with logical points resolution (e.g. 1440x900), backing scale factor (Retina 2.0x), and physical pixel dimensions (2880x1800).
    - Example: `cliclick si`

11. **Active Window & Frontmost App Info (`wi`)**:
    - Returns frontmost application name, bundle ID, process ID, window title, and window bounds.
    - Example: `cliclick wi`

12. **Structured JSON Mode (`-j <json>` or `-j -`)**:
    - Direct execution of JSON action payloads matching Anthropic Computer Use and OpenAI Codex action schemas.
    - Example:
      ```bash
      cliclick -j '{"action": "left_click", "coordinate": [500, 300]}'
      ```
    - Chained multi-action batching:
      ```bash
      cliclick -j '[{"action": "mouse_move", "coordinate": [200, 200]}, {"action": "cursor_position"}]'
      ```

13. **Python Computer Use SDK (`computer_use`)**:
    - High-level Python controller (`Computer()`) with automatic Retina coordinate translation, PIL image resizing for vision models, Set-of-Marks, and batch execution.

14. **Model Context Protocol (MCP) Server (45 Tools)**:
    - Built-in stdio MCP server for immediate connection to Claude Desktop, Antigravity, Cursor, Codex, OpenCode, and any MCP client.

15. **Autonomous Vision Agent Loop (`computer-use agent "task"`)**:
    - Complete agent loop that captures screenshots, prompts an LLM with vision, and executes computer actions step-by-step.

---

## 🛠️ Installation & Building

### 1. Build the Native CLI
```bash
make
```
This generates the `./cliclick` executable in the project folder.

To install globally:
```bash
sudo make install
```

### 2. Install the Python Package
```bash
pip install -e .
```

### 3. Grant Accessibility Permissions
macOS requires Accessibility permissions for input emulation:
- Open **System Settings ➔ Privacy & Security ➔ Accessibility**.
- Enable the checkbox for **Terminal** (or iTerm2 / VS Code / Cursor).
- Screen Recording permissions are also required for screenshots (**Privacy & Security ➔ Screen Recording**).

---

## 📖 CLI Usage

### Traditional Command Syntax
```bash
# Click at x=500, y=300
./cliclick c:500,300

# Right click
./cliclick rc:500,300

# Middle click
./cliclick mc:500,300

# Scroll down 5 lines at position 500,300
./cliclick s:500,300,-5

# Press Cmd+C
./cliclick hk:cmd,c

# Type text
./cliclick t:"Hello world"

# Save screenshot to PNG
./cliclick sc:/tmp/screenshot.png

# Query screen and window info
./cliclick si
./cliclick wi
```

### JSON Mode (Agent Interface)
```bash
# Execute single action
./cliclick -j '{"action": "screenshot", "path": "/tmp/screen.png"}'

# Execute from stdin
echo '{"action": "window_info"}' | ./cliclick -j -
```

---

## 🐍 Python SDK (`computer_use`)

```python
from computer_use import Computer

computer = Computer()

# 1. Inspect display and window
screen = computer.get_main_screen()
print(f"Screen: {screen['width']}x{screen['height']} points (Scale: {screen['scale']})")

win = computer.active_window()
print(f"Active app: {win['application']} - Title: {win['window_title']}")

# 2. Take a screenshot formatted for Vision LLMs
shot = computer.screenshot(target_width=1280)
# shot['base64'] is ready for OpenAI/Claude/Gemini vision APIs!

# 3. Mouse actions
computer.move(500, 300)
computer.click(500, 300)
computer.right_click(500, 300)
computer.middle_click(500, 300)
computer.scroll(delta_y=-5)  # Scroll down

# 4. Keyboard actions
computer.type("Hello from Computer Use!")
computer.hotkey("cmd", "c")
computer.key("return")
```

---

## 🤖 Model Context Protocol (MCP) Server

You can connect this tool directly to **Claude Desktop**, **Antigravity**, **Cursor**, or any MCP client:

### Add to MCP Settings (`mcp.json` / Claude Desktop config):
```json
{
  "mcpServers": {
    "macos-computer-use": {
      "command": "python3",
      "args": ["-m", "computer_use.mcp_server"],
      "cwd": "/path/to/click"
    }
  }
}
```

Exposed MCP Tools:
- `computer`: Standard multimodal computer use tool matching OpenAI Codex / Anthropic specs.
- `screenshot`: Take display screenshots with optional downscaling.
- `click`: Click at coordinates (left, right, middle).
- `type_text`: Type text into frontmost application.
- `scroll`: Vertical and horizontal scrolling.
- `get_active_window`: Inspect focused window title, application name, PID, and bounds.
- `get_screen_info`: Inspect display dimensions and scale factors.

---

## 🚀 Autonomous Vision Agent Loop

Run an AI agent directly from your terminal:
```bash
export OPENAI_API_KEY="your-key-here"
computer-use agent "Open Notes app and write a reminder to buy groceries"
```

---

## 🧪 Running Tests

```bash
# Run native CLI bash test suite
./Test.sh ./cliclick

# Run Python integration & unit test suite
python3 -m pytest tests/ -v
```

---

## 📄 License
BSD 3-Clause License. See [LICENSE](file:///Users/abdulrahmansalimalhamodi/Desktop/click/LICENSE).
