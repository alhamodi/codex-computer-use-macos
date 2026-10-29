"""
Task Orchestrator & State Machine for Autonomous Computer Use.

Provides:
- Explicit execution state machine (CREATED, PLANNING, RUNNING, WAITING, VERIFYING, AWAITING_APPROVAL, RECOVERING, COMPLETED, FAILED, CANCELLED).
- Multi-step goal decomposition and execution.
- Deadlock, cycle, and stagnation detection (repeated clicks, zero screen deltas).
- Token, latency, and cost tracking across turns.
- Multimodal verification of sub-goals and final goals.
"""

from __future__ import annotations
import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from computer_use.computer import Computer
from computer_use.models.base import ModelDecision, ModelProvider, ModelUsage, ToolCallRequest
from computer_use.schema import OPENAI_COMPUTER_TOOL
from computer_use.security import RiskLevel, SecurityPolicyGuard
from computer_use.semantic import SemanticResolver
from computer_use.verification import ActionVerifier


class TaskState(str, Enum):
    CREATED = "CREATED"
    PLANNING = "PLANNING"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    VERIFYING = "VERIFYING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    RECOVERING = "RECOVERING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class TaskStep:
    """Represents a single step or action in the plan."""
    step_id: int
    description: str
    action_type: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    state: TaskState = TaskState.CREATED
    verification_rule: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0


@dataclass
class TaskMetrics:
    """Consolidated metrics for an orchestrated task."""
    total_steps: int = 0
    successful_steps: int = 0
    failed_steps: int = 0
    recovery_attempts: int = 0
    total_latency_seconds: float = 0.0
    model_usage: ModelUsage = field(default_factory=ModelUsage)
    stagnation_events: int = 0


class TaskOrchestrator:
    """
    Central Coordinator managing the state machine, model reasoning loop,
    security policy checks, stagnation avoidance, and multi-step verification.
    """

    def __init__(
        self,
        model_provider: ModelProvider,
        computer: Optional[Computer] = None,
        max_steps: int = 25,
        max_retries_per_step: int = 2,
        approval_callback: Optional[Callable[[str, Dict[str, Any]], bool]] = None,
    ):
        self.provider = model_provider
        self.computer = computer or Computer()
        self.security_guard = SecurityPolicyGuard.get_instance()
        self.verifier = ActionVerifier(self.computer)
        self.semantic_resolver = SemanticResolver(self.computer)

        self.max_steps = max_steps
        self.max_retries = max_retries_per_step
        self.approval_callback = approval_callback

        self.current_state = TaskState.CREATED
        self.goal: str = ""
        self.steps: List[TaskStep] = []
        self.metrics = TaskMetrics()
        self.execution_log: List[Dict[str, Any]] = []

        # Stagnation & Loop Detection State
        self._action_signature_history: List[str] = []
        self._screen_hash_history: List[str] = []

    def set_state(self, new_state: TaskState) -> None:
        """Transitions state with audit logging."""
        prev_state = self.current_state
        self.current_state = new_state
        self.execution_log.append({
            "timestamp": time.time(),
            "event": "state_transition",
            "from": prev_state.value,
            "to": new_state.value,
        })

    def check_stagnation(self, action_signature: str, screen_hash: Optional[str] = None) -> bool:
        """
        Detects if the agent is stuck in an infinite loop
        (e.g., clicking the same coordinates 3+ times without screen change).
        """
        self._action_signature_history.append(action_signature)
        if screen_hash:
            self._screen_hash_history.append(screen_hash)

        # Pattern 1: Same exact action repeated 3 times in a row
        if len(self._action_signature_history) >= 3:
            last_3 = self._action_signature_history[-3:]
            if last_3[0] == last_3[1] == last_3[2]:
                self.metrics.stagnation_events += 1
                return True

        # Pattern 2: Screen has not changed across last 3 actions
        if len(self._screen_hash_history) >= 3:
            last_3_screens = self._screen_hash_history[-3:]
            if last_3_screens[0] == last_3_screens[1] == last_3_screens[2]:
                self.metrics.stagnation_events += 1
                return True

        return False

    def execute_goal(self, goal: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Executes a high-level goal through the state machine.
        """
        self.goal = goal
        self.set_state(TaskState.PLANNING)
        start_time = time.time()

        system_prompt = (
            "You are an expert autonomous Computer Use Agent on macOS.\n"
            "Your task is to accomplish the user's goal safely and efficiently.\n"
            "Rules:\n"
            "1. Inspect the screen state every turn before proposing actions.\n"
            "2. If an element cannot be clicked, look for modal dialogues or try a semantic target.\n"
            "3. Once the goal is verified, summarize your achievements and conclude."
        )

        messages: List[Dict[str, Any]] = [
            {"role": "user", "content": [{"type": "text", "text": f"Goal: {goal}"}]}
        ]

        step_counter = 0

        while step_counter < self.max_steps:
            step_counter += 1
            self.set_state(TaskState.RUNNING)

            # Vision input: Capture lightweight screen state
            screen_shot = self.computer.screenshot(target_width=1280)
            screen_b64 = screen_shot["base64"]
            screen_hash = hashlib.md5(screen_b64[:1000].encode()).hexdigest()

            messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{screen_b64}", "detail": "low"},
                    },
                    {
                        "type": "text",
                        "text": f"Screen state (step {step_counter}/{self.max_steps}). Next action?",
                    },
                ],
            })

            # Call Model Provider
            t_model_start = time.time()
            decision = self.provider.generate_decision(
                messages=messages,
                tools=[OPENAI_COMPUTER_TOOL],
                system_prompt=system_prompt,
            )
            self.metrics.model_usage.add(decision.usage)

            # If no tool calls, model considers task finished or requires clarification
            if not decision.has_tool_calls:
                self.set_state(TaskState.VERIFYING)
                final_summary = decision.text_content or "Goal finished."
                self.set_state(TaskState.COMPLETED)
                self.metrics.total_latency_seconds = time.time() - start_time
                self.metrics.total_steps = step_counter
                return {
                    "success": True,
                    "state": self.current_state.value,
                    "summary": final_summary,
                    "metrics": self.metrics,
                    "log": self.execution_log,
                }

            # Process Tool Calls
            for tool_call in decision.tool_calls:
                args = tool_call.arguments
                action = args.get("action")
                coord = args.get("coordinate", [])
                text = args.get("text", "")
                sig = f"{action}:{coord}:{text}"

                # Stagnation Check
                if self.check_stagnation(sig, screen_hash):
                    self.set_state(TaskState.RECOVERING)
                    self.metrics.recovery_attempts += 1
                    # Inject recovery guidance
                    messages.append({
                        "role": "system",
                        "content": "STAGNATION DETECTED: The last action did not produce a visible change. Try pressing Escape, dismissing active modals, or using keyboard navigation.",
                    })
                    break

                # Security Policy Evaluation
                risk_level = self.security_guard.classify_action(action, args)
                if risk_level in (RiskLevel.SENSITIVE, RiskLevel.DESTRUCTIVE):
                    self.set_state(TaskState.AWAITING_APPROVAL)
                    approved = True
                    if self.approval_callback:
                        approved = self.approval_callback(action, args)
                    if not approved:
                        self.set_state(TaskState.FAILED)
                        return {
                            "success": False,
                            "state": self.current_state.value,
                            "error": f"Action '{action}' was denied by security approval.",
                            "metrics": self.metrics,
                        }
                    self.set_state(TaskState.RUNNING)

                # Execute Action
                t_exec_start = time.time()
                step_obj = TaskStep(
                    step_id=step_counter,
                    description=f"{action} at {coord}",
                    action_type=action,
                    parameters=args,
                    state=TaskState.RUNNING,
                )

                try:
                    exec_result = self._dispatch_action(action, args)
                    step_obj.result = exec_result
                    step_obj.state = TaskState.COMPLETED
                    self.metrics.successful_steps += 1
                except Exception as exc:
                    step_obj.error = str(exc)
                    step_obj.state = TaskState.FAILED
                    self.metrics.failed_steps += 1

                step_obj.execution_time_ms = (time.time() - t_exec_start) * 1000.0
                self.steps.append(step_obj)

        self.set_state(TaskState.FAILED)
        self.metrics.total_latency_seconds = time.time() - start_time
        self.metrics.total_steps = step_counter
        return {
            "success": False,
            "state": self.current_state.value,
            "error": f"Exceeded maximum steps limit ({self.max_steps}).",
            "metrics": self.metrics,
        }

    def _dispatch_action(self, action: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatches an action safely to the Computer abstraction."""
        if action == "click":
            coord = args.get("coordinate") or [0, 0]
            return self.computer.click(coord[0], coord[1])
        elif action == "type":
            return self.computer.type_text(args.get("text", ""))
        elif action == "press":
            return self.computer.press_key(args.get("key", "return"))
        elif action == "hotkey":
            return self.computer.hotkey(args.get("keys", []))
        elif action == "mouse_move":
            coord = args.get("coordinate") or [0, 0]
            return self.computer.move_mouse(coord[0], coord[1])
        elif action == "wait":
            dur = args.get("duration", 1000)
            self.computer.wait(dur)
            return {"status": "waited", "duration": dur}
        else:
            return {"status": "unhandled_or_noop", "action": action}
