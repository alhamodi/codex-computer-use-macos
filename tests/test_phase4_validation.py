"""
Tests for Phase 4: Task Checkpointing, Resumption, and Real-World Validation Scenarios.
"""

import os
import pytest
from unittest.mock import MagicMock

from computer_use.checkpoint import CheckpointStore, TaskCheckpoint
from computer_use.validation import RealWorldValidator


class TestPhase4Checkpoints:
    def test_checkpoint_store_save_and_load(self, tmp_path):
        store = CheckpointStore(storage_dir=str(tmp_path))
        cp = TaskCheckpoint(
            task_id="task_abc",
            session_id="sess_123",
            goal="Test Goal",
            state="RUNNING",
            step_index=3,
            completed_steps=[{"step_id": 1, "action": "click"}],
            cumulative_cost_usd=0.005,
            total_tokens=150,
            created_at=100.0,
            updated_at=110.0,
        )

        saved_path = store.save(cp)
        assert os.path.exists(saved_path)

        loaded = store.load("task_abc")
        assert loaded is not None
        assert loaded.task_id == "task_abc"
        assert loaded.goal == "Test Goal"
        assert loaded.step_index == 3
        assert len(loaded.completed_steps) == 1

        all_tasks = store.list_checkpoints()
        assert "task_abc" in all_tasks


class TestPhase4RealWorldValidator:
    def test_validator_file_scenario(self):
        validator = RealWorldValidator()
        try:
            res = validator.run_scenario_b_file_task()
            assert res["status"] == "PASSED"
            assert "sha256" in res["evidence"]
        finally:
            validator.cleanup()

    def test_validator_clipboard_pipe(self):
        validator = RealWorldValidator()
        res = validator.run_scenario_c_clipboard_pipe()
        assert res["status"] == "PASSED"
        assert res["evidence"]["matched"] is True

    def test_validator_davinci_status(self):
        from unittest.mock import patch
        with patch("computer_use.profiles.davinci.DaVinciResolveProfile.get_status") as mock_status:
            mock_status.return_value = {"is_running": False}
            validator = RealWorldValidator()
            res = validator.run_scenario_d_davinci_status()
            assert res["status"] == "BLOCKED_ENVIRONMENT"
