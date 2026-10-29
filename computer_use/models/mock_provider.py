"""
Deterministic mock model provider for unit tests, offline benchmarking,
and end-to-end task orchestration verification.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from computer_use.models.base import (
    ModelDecision,
    ModelProvider,
    ModelUsage,
    ProviderCapabilities,
    ToolCallRequest,
)


class MockModelProvider(ModelProvider):
    """
    Mock LLM provider that yields pre-configured decisions or simulates
    a multi-step sequence of tool calls ending with a completion message.
    """

    def __init__(
        self,
        scripted_decisions: Optional[List[ModelDecision]] = None,
        model_name: str = "mock-computer-use",
        **kwargs,
    ):
        super().__init__(model_name=model_name, **kwargs)
        self.scripted_decisions = list(scripted_decisions or [])
        self.call_history: List[List[Dict[str, Any]]] = []
        self._current_index = 0

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            name="mock",
            supports_vision=True,
            supports_computer_use=True,
            supports_tool_calling=True,
            cost_per_1k_input_tokens=0.0,
            cost_per_1k_output_tokens=0.0,
            context_window_tokens=200000,
        )

    def add_decision(self, decision: ModelDecision) -> None:
        self.scripted_decisions.append(decision)

    def generate_decision(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
    ) -> ModelDecision:
        self.call_history.append(messages)

        if self._current_index < len(self.scripted_decisions):
            decision = self.scripted_decisions[self._current_index]
            self._current_index += 1
        else:
            # Default completion decision when script runs out
            decision = ModelDecision(
                text_content="Goal accomplished based on mock execution.",
                tool_calls=[],
                usage=ModelUsage(prompt_tokens=150, completion_tokens=30, total_tokens=180, estimated_cost_usd=0.0),
                finish_reason="stop",
            )

        self.cumulative_usage.add(decision.usage)
        return decision
