"""
Comprehensive Audit Logger and Structured Diagnostics for Computer Use Agents.

Logs:
- task_id, session_id, step_id.
- Timestamps, duration, and latency.
- Sanitized tool inputs & results (secrets and credentials redacted).
- Verification state and evidentiary details.
- Budget, token, and cost tracking.
"""

from __future__ import annotations
import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


SECRET_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9]{20,}", re.IGNORECASE),
    re.compile(r"bearer\s+[a-zA-Z0-9_\-\.]{20,}", re.IGNORECASE),
    re.compile(r"password\s*[:=]\s*[^\s]+", re.IGNORECASE),
    re.compile(r"token\s*[:=]\s*[^\s]+", re.IGNORECASE),
    re.compile(r"key\s*[:=]\s*[^\s]+", re.IGNORECASE),
]


def redact_secrets(data: Any) -> Any:
    """Recursively redacts API keys, tokens, and passwords from log data."""
    if isinstance(data, str):
        redacted = data
        for pat in SECRET_PATTERNS:
            redacted = pat.sub("[REDACTED_SECRET]", redacted)
        return redacted
    elif isinstance(data, dict):
        new_d = {}
        for k, v in data.items():
            if any(term in k.lower() for term in ("password", "secret", "api_key", "token", "auth")):
                new_d[k] = "[REDACTED_SECRET]"
            else:
                new_d[k] = redact_secrets(v)
        return new_d
    elif isinstance(data, list):
        return [redact_secrets(item) for item in data]
    return data


@dataclass
class AuditEntry:
    timestamp: float
    task_id: str
    session_id: str
    step_id: int
    event: str
    tool_name: Optional[str] = None
    action_type: Optional[str] = None
    target_app: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    verification_state: Optional[str] = None
    verification_evidence: Optional[str] = None
    error: Optional[str] = None
    cost_usd: float = 0.0
    duration_ms: float = 0.0


class AuditLogger:
    """Structured, sanitized audit logging for production Computer Use tasks."""

    def __init__(self, task_id: str, session_id: str, log_dir: Optional[str] = None):
        self.task_id = task_id
        self.session_id = session_id
        self.log_dir = log_dir or os.path.expanduser("~/.computer_use/logs")
        self.entries: List[AuditEntry] = []
        os.makedirs(self.log_dir, exist_ok=True)
        self.log_file = os.path.join(self.log_dir, f"task_{self.task_id}.jsonl")

    def record(
        self,
        step_id: int,
        event: str,
        tool_name: Optional[str] = None,
        action_type: Optional[str] = None,
        target_app: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        result: Optional[Dict[str, Any]] = None,
        verification_state: Optional[str] = None,
        verification_evidence: Optional[str] = None,
        error: Optional[str] = None,
        cost_usd: float = 0.0,
        duration_ms: float = 0.0,
    ) -> AuditEntry:
        entry = AuditEntry(
            timestamp=time.time(),
            task_id=self.task_id,
            session_id=self.session_id,
            step_id=step_id,
            event=event,
            tool_name=tool_name,
            action_type=action_type,
            target_app=target_app,
            parameters=redact_secrets(parameters),
            result=redact_secrets(result),
            verification_state=verification_state,
            verification_evidence=verification_evidence,
            error=redact_secrets(error) if error else None,
            cost_usd=cost_usd,
            duration_ms=duration_ms,
        )
        self.entries.append(entry)

        # Write to JSONL
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(entry)) + "\n")
        except Exception:
            pass

        return entry

    def export_summary(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "session_id": self.session_id,
            "total_entries": len(self.entries),
            "log_file": self.log_file,
            "entries": [asdict(e) for e in self.entries],
        }
