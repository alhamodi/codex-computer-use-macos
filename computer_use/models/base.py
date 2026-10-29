"""
Base interfaces and data structures for provider-agnostic model adapters.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ProviderType(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    MOCK = "mock"


@dataclass
class ToolCallRequest:
    """Represents a structured tool execution request from any LLM."""
    call_id: str
    tool_name: str
    arguments: Dict[str, Any]


@dataclass
class ModelUsage:
    """Tracks token consumption and estimated cost."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0

    def add(self, other: "ModelUsage") -> None:
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        self.total_tokens += other.total_tokens
        self.estimated_cost_usd += other.estimated_cost_usd


@dataclass
class ModelDecision:
    """Standardized response from any model provider."""
    text_content: Optional[str] = None
    tool_calls: List[ToolCallRequest] = field(default_factory=list)
    raw_response: Any = None
    usage: ModelUsage = field(default_factory=ModelUsage)
    finish_reason: Optional[str] = None

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


@dataclass
class ProviderCapabilities:
    """Declares what a provider/model can do."""
    name: str
    supports_vision: bool = True
    supports_computer_use: bool = True
    supports_tool_calling: bool = True
    cost_per_1k_input_tokens: float = 0.005
    cost_per_1k_output_tokens: float = 0.015
    context_window_tokens: int = 128000


class ModelProvider(ABC):
    """Abstract base class for all Computer Use model adapters."""

    def __init__(self, model_name: str, api_key: Optional[str] = None, **kwargs):
        self.model_name = model_name
        self.api_key = api_key
        self.config = kwargs
        self.cumulative_usage = ModelUsage()

    @property
    @abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        """Returns the capabilities of this provider/model configuration."""
        pass

    @abstractmethod
    def generate_decision(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
    ) -> ModelDecision:
        """Synchronously ask the model for the next decision or tool call."""
        pass

    def estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculates cost based on token counts and declared provider rates."""
        caps = self.capabilities
        in_cost = (prompt_tokens / 1000.0) * caps.cost_per_1k_input_tokens
        out_cost = (completion_tokens / 1000.0) * caps.cost_per_1k_output_tokens
        return round(in_cost + out_cost, 6)
