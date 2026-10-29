"""
Budget and Resource Governance for Computer Use Tasks.

Controls:
- Max financial budget in USD.
- Max model call invocations.
- Max plan execution steps.
- Total task wall-clock timeout.
- Max error recovery attempts.
"""

from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Optional


class BudgetExceededError(RuntimeError):
    """Raised when an operation breaches declared task budget limits."""
    pass


@dataclass
class TaskBudget:
    """Configurable resource limits for an autonomous task."""
    max_cost_usd: float = 1.00          # Maximum estimated budget in USD
    max_model_calls: int = 30           # Maximum LLM API queries
    max_steps: int = 25                 # Maximum actions executed
    max_duration_seconds: float = 300.0 # 5 minutes maximum timeout
    max_recovery_retries: int = 3       # Max stagnation/error recoveries


@dataclass
class BudgetTracker:
    """Tracks cumulative usage against declared budget."""
    budget: TaskBudget
    start_time: float = field(default_factory=time.time)
    current_cost_usd: float = 0.0
    model_calls_count: int = 0
    steps_count: int = 0
    recovery_count: int = 0

    @property
    def elapsed_seconds(self) -> float:
        return time.time() - self.start_time

    def check_limits(self) -> None:
        """Verifies no resource threshold has been violated."""
        if self.elapsed_seconds > self.budget.max_duration_seconds:
            raise BudgetExceededError(
                f"Task timed out: Elapsed {self.elapsed_seconds:.1f}s exceeded limit of {self.budget.max_duration_seconds}s."
            )

        if self.current_cost_usd > self.budget.max_cost_usd:
            raise BudgetExceededError(
                f"Cost limit reached: ${self.current_cost_usd:.4f} exceeded budget of ${self.budget.max_cost_usd:.4f}."
            )

        if self.model_calls_count >= self.budget.max_model_calls:
            raise BudgetExceededError(
                f"Model calls cap reached: {self.model_calls_count} >= max {self.budget.max_model_calls}."
            )

        if self.steps_count >= self.budget.max_steps:
            raise BudgetExceededError(
                f"Step limit reached: {self.steps_count} >= max {self.budget.max_steps}."
            )

        if self.recovery_count >= self.budget.max_recovery_retries:
            raise BudgetExceededError(
                f"Max recovery retries exhausted: {self.recovery_count} >= {self.budget.max_recovery_retries}."
            )

    def record_model_call(self, cost_usd: float) -> None:
        self.model_calls_count += 1
        self.current_cost_usd += cost_usd
        self.check_limits()

    def record_step(self) -> None:
        self.steps_count += 1
        self.check_limits()

    def record_recovery(self) -> None:
        self.recovery_count += 1
        self.check_limits()
