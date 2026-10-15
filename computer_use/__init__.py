"""
Computer Use for macOS.

Native, ultra-fast desktop automation engine and AI agent interface.
Upgraded from cliclick to support Anthropic Computer Use and OpenAI Codex Operator.
"""

from computer_use.computer import Computer
from computer_use.schema import (
    ANTHROPIC_COMPUTER_TOOL,
    OPENAI_COMPUTER_TOOL,
    GEMINI_COMPUTER_TOOL
)

__version__ = "6.0.0"
__all__ = [
    "Computer",
    "ANTHROPIC_COMPUTER_TOOL",
    "OPENAI_COMPUTER_TOOL",
    "GEMINI_COMPUTER_TOOL",
]
