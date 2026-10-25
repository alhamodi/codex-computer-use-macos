---
name: computer-use-macos
description: Control local macOS applications through Computer Use for tasks that require inspecting or operating app UI, taking screenshots, Apple Vision OCR text extraction, mouse and keyboard automation, window management, and Safari/Chrome browser operations.
---

# macOS Computer Use

Control and automate macOS desktop applications directly from Codex, Claude, ChatGPT, or Antigravity using native macOS system APIs and high-performance event simulation.

## Prerequisites & Permissions

macOS requires two privacy permissions:
1. **Accessibility**: Needed to click, type, scroll, and manage windows.
   - Go to `System Settings > Privacy & Security > Accessibility` and enable the containing app (Codex, Terminal, iTerm, Antigravity, or Cursor).
2. **Screen Recording**: Needed to take screenshots and perform Apple Vision OCR.
   - Go to `System Settings > Privacy & Security > Screen Recording` and enable the containing app.

---

## Tool Reference

### 1. Screen & Vision
- `observe_screen`: **(Recommended first step)** One-shot multimodal observation. Returns downscaled screenshot base64 + active window metadata + cursor position + display dimensions in 1 turn.
- `screenshot`: Capture full display screenshot as base64 PNG or save to file.
- `screenshot_active_window`: Capture screenshot cropped to only the focused window.
- `extract_text`: Run Apple Vision OCR over the screen. Returns all text lines with exact `(center_x, center_y)` coordinates and bounding boxes.
- `extract_text_active_window`: Run Apple Vision OCR only on the active window.
- `get_screen_size`: Get logical points (e.g. 1440x900) and physical Retina pixels (2880x1800).
- `get_cursor_position`: Get current mouse cursor `(x, y)` in points.

### 2. Mouse and Keyboard
- `click(x, y, button="left")`: Click at `(x, y)` points. Supports `button="left"`, `"right"`, or `"middle"`.
- `move_mouse(x, y)`: Move pointer to `(x, y)`.
- `drag_mouse(start_x, start_y, end_x, end_y)`: Click and drag between points.
- `type_text(text)`: Type standard text into the focused field.
- `type_unicode(text)`: Paste unicode or emoji text via clipboard to preserve special characters.
- `press_key(key)`: Hit special keys: `return`, `space`, `escape`, `tab`, `delete`, `fwd-delete`, `arrow-down`, `arrow-up`, `arrow-left`, `arrow-right`, `f1`-`f16`, `home`, `end`.
- `hotkey(keys)`: Execute keyboard shortcut (e.g. `['cmd', 'c']`, `['cmd', 'v']`, `['cmd', 'shift', 'p']`, `['cmd', 'space']`).
- `scroll(delta_y, delta_x=0)`: Scroll mouse wheel. `delta_y < 0` scrolls down, `delta_y > 0` scrolls up.

### 3. Window Management
- `list_windows`: List all open on-screen windows with owner application name, process ID, title, and bounds.
- `focus_window(app_name=None, pid=None)`: Bring an application or window to the foreground.
- `open_app(app_name)`: Launch or activate an application (e.g. `open_app("Safari")`, `open_app("Notes")`).
- `run_program(command)`: Execute a shell command in the terminal.
- `get_window_text`: Extract readable text from the focused window.

### 4. Clipboard
- `get_clipboard`: Read current text from macOS clipboard.
- `set_clipboard(text)`: Copy text to macOS clipboard.

### 5. Browser Automation (Safari & Google Chrome)
- `safari_get_url` / `chrome_get_url`: Get URL of the active browser tab.
- `safari_get_tab_title` / `chrome_get_tab_title`: Get title of active tab.
- `safari_navigate(url)` / `chrome_navigate(url)`: Open a URL in the active tab.
- `safari_search(query)` / `chrome_search(query)`: Search Google in the browser.
- `safari_read_page` / `chrome_read_page`: Read inner text of active web page.

### 6. UI Automation, Smart Polling & Visual Grounding
- `find_and_click_element(text, active_window_only=False)`: Search for an on-screen button or label using Apple Vision OCR and click its exact center automatically.
- `som_observe(active_window_only=False, save_path=None)`: Capture screenshot and overlay Set-of-Marks (numbered badges on detected UI elements) for reliable grounding by vision models without pixel hallucination.
- `click_mark(mark_id, marks)`: Click a numbered UI element mark identified from `som_observe`.
- `human_click(x, y, hover_ms=150, hold_ms=80)`: Realistic 3-phase click: smooth movement, hover dwell (fires React/DOM pointerover), and hold duration before mouse up.
- `hover(x, y, duration_ms=200)`: Hover over an element to trigger CSS `:hover` or JavaScript dropdowns.
- `wait_until_condition(condition, target, timeout=30)`: Smart state polling (`text_appears`, `text_disappears`, `window_title_contains`) instead of brittle static delays.
- `handle_file_dialog(file_path)`: Guaranteed macOS file chooser dialog automation via `Cmd+Shift+G` sheet and unicode path injection.
- `verify_action_result(success_keywords, blocker_keywords)`: Automated verification of actions (e.g. upload complete, terms blocker detected, error banner found).

### 7. DaVinci Resolve 21 Automation
- `davinci_status`: Get operational status (is running, active project name, window bounds, project manager state).
- `davinci_switch_page(page)`: Switch instantly to any workspace page: `media`, `cut`, `edit`, `fusion`, `color`, `fairlight`, `deliver`.
- `davinci_project_manager(action)`: Control Project Manager: `open`, `close`, or `list` projects with coordinates.
- `davinci_open_project(project_name)`: Open project by name smoothly with double-click and state verification.
- `davinci_timeline_action(action)`: Run timeline controls: `play_pause`, `fit_timeline`, `split_clip`, `zoom_in`, `zoom_out`, `toggle_snapping`, `save_project`, `import_media`.

### 8. Safety & Humanized Cursor Motion
- **Visible Smooth Cursor**: All mouse movements use humanized `cubicEaseInOut` curves across ~120Hz frames so the user sees exactly where the cursor is going.
- **User Takeover Fail-safe**: If the user moves the physical mouse during automation (drift > 35pt), the engine halts immediately with `UserTakeoverError` / `user_takeover`, protecting user control.

### 9. Utility
- `computer`: Standard multimodal Computer Use tool matching Anthropic/OpenAI schema.
- `batch_actions(actions)`: Execute a batch of actions sequentially without re-spawning processes.
- `wait(ms)`: Pause for specified milliseconds.

---

## Best Practices & Workflows

1. **Start with `observe_screen` or `extract_text`**:
   - `observe_screen` gives you visual context and current active window info.
   - `extract_text` lets you see exact text strings with their coordinates, removing any coordinate guessing!

2. **Ensure Target App is Focused**:
   - Before typing or clicking in an app, call `focus_window(app_name="...")` or `open_app("...")` to ensure it receives input.

3. **Use `find_and_click_element` for Buttons**:
   - Instead of estimating pixel coordinates from a screenshot, `find_and_click_element("Submit")` finds the button via native Apple Vision OCR and clicks it with sub-pixel accuracy.

4. **Retina Point vs Pixel Coordinates**:
   - Coordinates in `click` and `move_mouse` use **macOS points** (e.g. 1440x900 on Retina displays), not physical pixels. All coordinates returned by `extract_text`, `observe_screen`, and `get_screen_size` are already normalized to macOS points.
