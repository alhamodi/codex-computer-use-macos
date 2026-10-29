"""
Task Orchestrator & State Machine for Autonomous Computer Use.

Provides:
- Explicit execution state machine (CREATED, PLANNING, RUNNING, WAITING, VERIFYING, AWAITING_APPROVAL, RECOVERING, COMPLETED, FAILED, CANCELLED).
- Closed-loop feedback: tool results, observations, and verifications are fed back to LLM.
- Budget, resource, and timeout enforcement.
- Sanitized audit logging (secrets redacted).
- Stagnation & deadlock recovery engine.
"""

from __future__ import annotations
import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from computer_use.audit import AuditLogger
from computer_use.budget import BudgetExceededError, BudgetTracker, TaskBudget
from computer_use.computer import Computer
from computer_use.models.base import ModelDecision, ModelProvider, ModelUsage, ToolCallRequest
from computer_use.observation import Observation, ObservationManager
from computer_use.schema import OPENAI_COMPUTER_TOOL
from computer_use.security import RiskLevel, SecurityPolicyGuard
from computer_use.semantic import SemanticResolver
from computer_use.verification import ActionVerifier, VerificationState


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
    verification_state: str = "pending"
    verification_evidence: Optional[str] = None
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
    verification_passed_count: int = 0
    verification_uncertain_count: int = 0


class TaskOrchestrator:
    """
    Central Coordinator managing the state machine, model reasoning loop,
    security policy checks, stagnation avoidance, budget enforcement,
    and closed-loop multi-step verification.
    """

    def __init__(
        self,
        model_provider: ModelProvider,
        computer: Optional[Computer] = None,
        budget: Optional[TaskBudget] = None,
        max_steps: int = 25,
        approval_callback: Optional[Callable[[str, Dict[str, Any]], bool]] = None,
    ):
        self.provider = model_provider
        self.computer = computer or Computer()
        self.security_guard = SecurityPolicyGuard.get_instance()
        self.verifier = ActionVerifier(self.computer)
        self.semantic_resolver = SemanticResolver(self.computer)
        self.obs_manager = ObservationManager(self.computer)

        self.budget = budget or TaskBudget(max_steps=max_steps)
        self.budget_tracker = BudgetTracker(budget=self.budget)
        self.approval_callback = approval_callback

        self.task_id = str(uuid.uuid4())
        self.session_id = str(uuid.uuid4())
        self.audit_logger = AuditLogger(task_id=self.task_id, session_id=self.session_id)

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
        self.audit_logger.record(
            step_id=len(self.steps),
            event="state_transition",
            parameters={"from": prev_state.value, "to": new_state.value},
        )

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
        Executes a high-level goal through closed-loop state machine.
        """
        self.goal = goal
        self.set_state(TaskState.PLANNING)
        start_time = time.time()

        system_prompt = (
            "You are an expert autonomous Computer Use Agent running on macOS.\n"
            "Your objective is to accomplish the user's goal safely, cleanly, and reliably.\n"
            "Operational doctrine:\n"
            "1. Inspect the visual observation and active application state each turn.\n"
            "2. When interacting with UI controls, prefer semantic names or verified marks over raw coordinates.\n"
            "3. After an action is executed, analyze the feedback message before issuing next commands.\n"
            "4. When the goal is completed, output a concise concluding summary without calling any more tools."
        )

        messages: List[Dict[str, Any]] = [
            {"role": "user", "content": [{"type": "text", "text": f"Goal: {goal}"}]}
        ]

        step_counter = 0

        while True:
            step_counter += 1

            # Budget Check
            try:
                self.budget_tracker.check_limits()
            except BudgetExceededError as err:
                self.set_state(TaskState.FAILED)
                self.metrics.total_latency_seconds = time.time() - start_time
                self.metrics.total_steps = step_counter
                return {
                    "success": False,
                    "state": self.current_state.value,
                    "error": str(err),
                    "metrics": self.metrics,
                    "log": self.execution_log,
                }

            self.set_state(TaskState.RUNNING)

            # 1. Capture Unified Observation
            obs = self.obs_manager.capture_observation(target_width=1280, with_ocr=True, with_ax=True)
            screen_b64 = obs.screenshot_base64
            screen_hash = obs.screen_hash

            # Vision input message
            messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{screen_b64}", "detail": "low"},
                    },
                    {
                        "type": "text",
                        "text": f"Observation [App: {obs.active_app} | Window: {obs.active_window.get('window_title', '')}]. Step {step_counter}.",
                    },
                ],
            })

            # 2. Invoke Model Provider
            t_model_start = time.time()
            try:
                decision = self.provider.generate_decision(
                    messages=messages,
                    tools=[OPENAI_COMPUTER_TOOL],
                    system_prompt=system_prompt,
                )
            except Exception as model_err:
                self.set_state(TaskState.FAILED)
                return {
                    "success": False,
                    "state": self.current_state.value,
                    "error": f"Model Provider failed: {model_err}",
                    "metrics": self.metrics,
                }

            self.metrics.model_usage.add(decision.usage)
            self.budget_tracker.record_model_call(decision.usage.estimated_cost_usd)

            # 3. Model Finishes without tool calls
            if not decision.has_tool_calls:
                self.set_state(TaskState.VERIFYING)
                final_summary = decision.text_content or "Goal finished."

                # Verify Final Window/State if context dictates
                v_state = "success"
                if context and "expected_window" in context:
                    v_res = self.verifier.verify_window_title(context["expected_window"], timeout=2.0)
                    v_state = v_res.state.value

                self.set_state(TaskState.COMPLETED)
                self.metrics.total_latency_seconds = time.time() - start_time
                self.metrics.total_steps = step_counter
                return {
                    "success": (v_state == "success"),
                    "state": self.current_state.value,
                    "verification": v_state,
                    "summary": final_summary,
                    "metrics": self.metrics,
                    "log": self.execution_log,
                }

            # 4. Dispatch Tool Calls
            for tool_call in decision.tool_calls:
                args = tool_call.arguments
                action = args.get("action")
                coord = args.get("coordinate", [])
                text = args.get("text", "")
                sig = f"{action}:{coord}:{text}"

                # Stagnation & Deadlock Evaluation
                if self.check_stagnation(sig, screen_hash):
                    self.set_state(TaskState.RECOVERING)
                    self.metrics.recovery_attempts += 1
                    try:
                        self.budget_tracker.record_recovery()
                    except BudgetExceededError as b_err:
                        self.set_state(TaskState.FAILED)
                        return {"success": False, "state": self.current_state.value, "error": str(b_err), "metrics": self.metrics}

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.call_id,
                        "content": json.dumps({
                            "status": "stagnation_detected",
                            "message": "Action produced no visible desktop change. Dismiss active overlays or select an alternative target.",
                        }),
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
                            "error": f"Action '{action}' was denied by human security approval.",
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

                exec_result = {}
                try:
                    exec_result = self._dispatch_action(action, args)
                    step_obj.result = exec_result
                    step_obj.state = TaskState.COMPLETED
                    step_obj.verification_state = "executed"
                    self.metrics.successful_steps += 1
                except Exception as exc:
                    step_obj.error = str(exc)
                    step_obj.state = TaskState.FAILED
                    step_obj.verification_state = "error"
                    self.metrics.failed_steps += 1
                    exec_result = {"error": str(exc)}

                exec_duration = (time.time() - t_exec_start) * 1000.0
                step_obj.execution_time_ms = exec_duration
                self.steps.append(step_obj)
                self.budget_tracker.record_step()

                # Audit Log
                self.audit_logger.record(
                    step_id=step_counter,
                    event="action_execution",
                    tool_name="computer",
                    action_type=action,
                    target_app=obs.active_app,
                    parameters=args,
                    result=exec_result,
                    verification_state=step_obj.verification_state,
                    duration_ms=exec_duration,
                )

                # Feed Execution Result Back to the Model Context (Closed-Loop)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.call_id,
                    "content": json.dumps(exec_result),
                })

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
