"""
Session & Lifecycle Manager for Computer Use Execution.

Tracks:
- Deterministic session IDs and step counts.
- Execution states: CREATED, RUNNING, WAITING, AWAITING_APPROVAL, COMPLETED, FAILED, CANCELLED.
- Per-session action history and audit logging.
- Cancellation flags and resource cleanup.
"""

from __future__ import annotations
import enum
import time
import uuid
from typing import Any, Dict, List, Optional


class SessionState(enum.Enum):
    CREATED = "created"
    RUNNING = "running"
    WAITING = "waiting"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ComputerSession:
    """Encapsulates a managed agent interaction session."""

    def __init__(
        self,
        session_id: Optional[str] = None,
        target_app: Optional[str] = None,
        goal: Optional[str] = None,
        max_steps: int = 100,
        timeout_seconds: float = 300.0,
    ):
        self.session_id: str = session_id or str(uuid.uuid4())
        self.target_app: Optional[str] = target_app
        self.goal: Optional[str] = goal
        self.max_steps: int = max_steps
        self.timeout_seconds: float = timeout_seconds

        self.state: SessionState = SessionState.CREATED
        self.created_at: float = time.time()
        self.started_at: Optional[float] = None
        self.ended_at: Optional[float] = None
        self.steps_executed: int = 0
        self.action_history: List[Dict[str, Any]] = []
        self._is_cancelled: bool = False
        self.stop_reason: Optional[str] = None

    @property
    def is_active(self) -> bool:
        return self.state in (SessionState.RUNNING, SessionState.WAITING, SessionState.AWAITING_APPROVAL)

    @property
    def is_cancelled(self) -> bool:
        return self._is_cancelled

    @property
    def elapsed_seconds(self) -> float:
        start = self.started_at or self.created_at
        end = self.ended_at or time.time()
        return round(end - start, 2)

    def start(self) -> None:
        self.state = SessionState.RUNNING
        self.started_at = time.time()

    def cancel(self, reason: str = "User/Agent requested cancellation") -> None:
        self._is_cancelled = True
        self.state = SessionState.CANCELLED
        self.stop_reason = reason
        self.ended_at = time.time()

    def complete(self, reason: str = "Goal accomplished") -> None:
        self.state = SessionState.COMPLETED
        self.stop_reason = reason
        self.ended_at = time.time()

    def fail(self, error_message: str) -> None:
        self.state = SessionState.FAILED
        self.stop_reason = error_message
        self.ended_at = time.time()

    def record_step(self, tool_name: str, args: Dict[str, Any], result: Any, status: str = "success") -> None:
        self.steps_executed += 1
        entry = {
            "step": self.steps_executed,
            "timestamp": time.time(),
            "tool": tool_name,
            "args": args,
            "result_summary": str(result)[:300],
            "status": status,
        }
        self.action_history.append(entry)

        if self.steps_executed >= self.max_steps:
            self.fail(f"Session exceeded maximum step limit ({self.max_steps} steps).")

        if (time.time() - (self.started_at or self.created_at)) > self.timeout_seconds:
            self.fail(f"Session exceeded timeout ({self.timeout_seconds}s).")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "state": self.state.value,
            "target_app": self.target_app,
            "goal": self.goal,
            "steps_executed": self.steps_executed,
            "max_steps": self.max_steps,
            "elapsed_seconds": self.elapsed_seconds,
            "is_cancelled": self._is_cancelled,
            "stop_reason": self.stop_reason,
            "history_length": len(self.action_history),
        }


class SessionManager:
    """Registry maintaining active and historical agent sessions."""

    def __init__(self):
        self._sessions: Dict[str, ComputerSession] = {}
        self._active_session_id: Optional[str] = None

    def create_session(
        self,
        target_app: Optional[str] = None,
        goal: Optional[str] = None,
        max_steps: int = 100,
        timeout_seconds: float = 300.0,
    ) -> ComputerSession:
        session = ComputerSession(
            target_app=target_app,
            goal=goal,
            max_steps=max_steps,
            timeout_seconds=timeout_seconds,
        )
        session.start()
        self._sessions[session.session_id] = session
        self._active_session_id = session.session_id
        return session

    def get_session(self, session_id: Optional[str] = None) -> Optional[ComputerSession]:
        sid = session_id or self._active_session_id
        return self._sessions.get(sid) if sid else None

    def cancel_active_session(self, reason: str = "Immediate cancellation requested") -> Optional[ComputerSession]:
        session = self.get_session()
        if session:
            session.cancel(reason)
        return session
