"""
OpenAI Model Provider adapter for Computer Use and Responses API.
Supports GPT-4o, GPT-4o-mini, and computer use with token tracking & cost estimation.
"""

from __future__ import annotations
import json
import os
from typing import Any, Dict, List, Optional

from computer_use.models.base import (
    ModelDecision,
    ModelProvider,
    ModelUsage,
    ProviderCapabilities,
    ToolCallRequest,
)


class OpenAIModelProvider(ModelProvider):
    """
    Adapter for OpenAI Chat Completions & Computer Use tools.
    Handles authentication, schema adaptation, token accounting, and cost tracking.
    """

    MODEL_RATES = {
        "gpt-4o": {"input": 0.005, "output": 0.015},
        "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
        "gpt-4-turbo": {"input": 0.01, "output": 0.03},
        "o1-preview": {"input": 0.015, "output": 0.06},
        "o3-mini": {"input": 0.0011, "output": 0.0044},
    }

    def __init__(
        self,
        model_name: str = "gpt-4o",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        organization: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(model_name=model_name, api_key=api_key, **kwargs)
        resolved_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._api_key = resolved_key
        self._base_url = base_url or os.environ.get("OPENAI_BASE_URL")
        self._organization = organization
        self._client = None

    def _get_client(self):
        if self._client is None:
            if not self._api_key:
                raise ValueError(
                    "OpenAI API key missing. Set OPENAI_API_KEY environment variable or pass api_key."
                )
            try:
                from openai import OpenAI
            except ImportError as err:
                raise ImportError(
                    "openai package is required for OpenAIModelProvider. Install with: pip install openai"
                ) from err

            self._client = OpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
                organization=self._organization,
            )
        return self._client

    @property
    def capabilities(self) -> ProviderCapabilities:
        rates = self.MODEL_RATES.get(
            self.model_name, {"input": 0.005, "output": 0.015}
        )
        return ProviderCapabilities(
            name=f"openai-{self.model_name}",
            supports_vision=True,
            supports_computer_use=True,
            supports_tool_calling=True,
            cost_per_1k_input_tokens=rates["input"],
            cost_per_1k_output_tokens=rates["output"],
            context_window_tokens=128000,
        )

    def generate_decision(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
    ) -> ModelDecision:
        client = self._get_client()

        formatted_messages = []
        if system_prompt:
            formatted_messages.append({"role": "system", "content": system_prompt})
        formatted_messages.extend(messages)

        request_kwargs: Dict[str, Any] = {
            "model": self.model_name,
            "messages": formatted_messages,
            "temperature": temperature,
        }

        if tools:
            request_kwargs["tools"] = tools
            request_kwargs["tool_choice"] = "auto"

        response = client.chat.completions.create(**request_kwargs)
        choice = response.choices[0]
        msg = choice.message

        tool_calls: List[ToolCallRequest] = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                call_id = tc.id
                fn_name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments)
                except Exception:
                    args = {"raw": tc.function.arguments}
                tool_calls.append(ToolCallRequest(call_id=call_id, tool_name=fn_name, arguments=args))

        # Usage & Cost accounting
        p_tokens = getattr(response.usage, "prompt_tokens", 0) if response.usage else 0
        c_tokens = getattr(response.usage, "completion_tokens", 0) if response.usage else 0
        t_tokens = getattr(response.usage, "total_tokens", 0) if response.usage else (p_tokens + c_tokens)
        cost = self.estimate_cost(p_tokens, c_tokens)

        usage = ModelUsage(
            prompt_tokens=p_tokens,
            completion_tokens=c_tokens,
            total_tokens=t_tokens,
            estimated_cost_usd=cost,
        )
        self.cumulative_usage.add(usage)

        return ModelDecision(
            text_content=msg.content,
            tool_calls=tool_calls,
            raw_response=response,
            usage=usage,
            finish_reason=choice.finish_reason,
        )
