# Agent & Architecture Guide for `click` (cliclick & computer-use)

This project contains the **`cliclick`** native macOS automation binary (Objective-C) and the **`computer_use`** Python MCP server / CLI.

---

## Workspace Structure

- `cliclick.m`, `ActionExecutor.m`, `Actions/`: Native Objective-C CLI tool simulating mouse and keyboard events via Quartz Event Services.
- `computer_use/`: Python automation layer providing:
  - `mcp_server.py`: Model Context Protocol (MCP) server exposing tools (`click`, `screenshot`, `type_text`, `press_key`, etc.).
  - `computer.py`: Core system interaction engine wrapping `cliclick` and screencapture.
  - `agent.py`: High-level desktop automation agent.
- `Makefile`: Builds the native `cliclick` binary (`make clean && make`).
- `Test.sh`: Automated test suite for `cliclick` commands.

---

## Build & Testing Rules

1. **Building `cliclick`**:
   ```bash
   make
   ```
   Always verify the newly built binary with `./cliclick -V` before deployment.

2. **Running Tests**:
   ```bash
   ./Test.sh
   pytest tests/
   ```

3. **macOS Coordinates & Retina Logic**:
   - `cliclick` operates on **logical screen points**, NOT physical Retina device pixels.
   - Always verify target window bounds via AppleScript before calculating click coordinates:
     ```bash
     osascript -e 'tell application "System Events" to get bounds of window 1 of (first process whose frontmost is true)'
     ```

---

## Subagents & Roles

- **`cliclick-automator`**: Specialized in testing actions, debugging Quartz events, verifying coordinate translations, and running the `computer-use` MCP server.
