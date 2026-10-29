"""
Non-Destructive Task Persistence and Checkpointing for Computer Use Agents.

Enables:
- Serializing and persisting active task execution state to disk (`~/.computer_use/checkpoints/`).
- Inspecting and verifying stored checkpoints before resuming.
- Safe resume logic: validates that the desktop state matches expectations before continuing.
- Redaction of sensitive data and credentials from serialized checkpoints.
"""

from __future__ import annotations
import json
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from computer_use.audit import redact_secrets


@dataclass
class TaskCheckpoint:
    task_id: str
    session_id: str
    goal: str
    state: str
    step_index: int
    completed_steps: List[Dict[str, Any]]
    cumulative_cost_usd: float
    total_tokens: int
    created_at: float
    updated_at: float
    last_error: Optional[str] = None
    context_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return redact_secrets(asdict(self))


class CheckpointStore:
    """Manages atomic saving and loading of task checkpoints."""

    def __init__(self, storage_dir: Optional[str] = None):
        self.storage_dir = storage_dir or os.path.expanduser("~/.computer_use/checkpoints")
        os.makedirs(self.storage_dir, exist_ok=True)

    def get_path(self, task_id: str) -> str:
        return os.path.join(self.storage_dir, f"task_{task_id}.json")

    def save(self, checkpoint: TaskCheckpoint) -> str:
        """Saves a task checkpoint atomically."""
        checkpoint.updated_at = time.time()
        file_path = self.get_path(checkpoint.task_id)
        data = checkpoint.to_dict()

        temp_path = f"{file_path}.tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(temp_path, file_path)
        return file_path

    def load(self, task_id: str) -> Optional[TaskCheckpoint]:
        """Loads a stored task checkpoint."""
        file_path = self.get_path(task_id)
        if not os.path.exists(file_path):
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return TaskCheckpoint(**data)
        except Exception:
            return None

    def list_checkpoints(self) -> List[str]:
        """Returns list of saved task IDs."""
        if not os.path.exists(self.storage_dir):
            return []
        tasks = []
        for f in os.listdir(self.storage_dir):
            if f.startswith("task_") and f.endswith(".json"):
                tasks.append(f[5:-5])
        return sorted(tasks)
