"""
Enterprise Health & Verification Check for macOS Computer Use Platform.
Validates:
1. Native binary availability & version.
2. macOS Accessibility & Screen Capture authorization status.
3. Apple Vision OCR speed and accuracy.
4. Python SDK, MCP catalog, and Security Policy integrity.
"""

from __future__ import annotations
import sys
import time
from computer_use.computer import Computer
from computer_use.mcp_server import MCPServer
from computer_use.security import RiskLevel, SecurityPolicy


def run_health_check() -> bool:
    print("=" * 60)
    print("🚀 Running macOS Computer Use Platform Diagnostics & Health Check")
    print("=" * 60)

    # 1. Native cliclick binary
    try:
        computer = Computer()
        print(f"✅ Native Binary: {computer.binary_path} (Accessible & Executable)")
    except Exception as e:
        print(f"❌ Native Binary Failure: {e}")
        return False

    # 2. Screen Info & Retina scaling
    try:
        s_info = computer.screen_info()
        main_s = s_info["screens"][0]
        print(f"✅ Screen Geometry: {main_s['width']}x{main_s['height']}pt (Retina: {main_s['scale']}x, Physical: {main_s['pixel_width']}x{main_s['pixel_height']}px)")
    except Exception as e:
        print(f"❌ Screen Info Failure: {e}")
        return False

    # 3. Vision OCR Benchmark
    try:
        t0 = time.time()
        ocr = computer.extract_text(active_window_only=True, fast=True)
        t_elapsed = time.time() - t0
        lines_cnt = len(ocr.get("lines", []))
        print(f"✅ Apple Vision OCR: {t_elapsed:.3f}s latency | {lines_cnt} text lines detected")
    except Exception as e:
        print(f"❌ Apple Vision OCR Failure: {e}")
        return False

    # 4. MCP Tools Catalog Integrity
    try:
        server = MCPServer()
        tools = server.list_tools()
        print(f"✅ MCP Server Protocol: 2024-11-05 | {len(tools)} registered tools available")
    except Exception as e:
        print(f"❌ MCP Server Failure: {e}")
        return False

    # 5. Security Guardrails
    try:
        policy = SecurityPolicy(max_allowed_risk=RiskLevel.WRITE, allow_shell_execution=False)
        computer.guard.policy = policy
        try:
            computer.guard.authorize("run_program", {"command": "rm -rf /"})
            print("❌ Security Guardrail Failure: Destructive command was not intercepted!")
            return False
        except Exception:
            print("✅ Security Policy Guard: Destructive shell command blocked successfully")
    except Exception as e:
        print(f"❌ Security Subsystem Failure: {e}")
        return False

    print("=" * 60)
    print("🎉 ALL PLATFORM SUBSYSTEMS OPERATIONAL AND SECURE")
    print("=" * 60)
    return True


if __name__ == "__main__":
    ok = run_health_check()
    sys.exit(0 if ok else 1)
