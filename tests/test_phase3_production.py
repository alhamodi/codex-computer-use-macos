"""
Tests for Phase 3: Observation Layer, Budget Governance, Audit Logging, and Closed-Loop Orchestration.
"""

import json
import os
import pytest
from unittest.mock import MagicMock, patch

from computer_use.audit import AuditLogger, redact_secrets
from computer_use.budget import BudgetExceededError, BudgetTracker, TaskBudget
from computer_use.models.base import ModelDecision, ModelUsage, ToolCallRequest
from computer_use.models.mock_provider import MockModelProvider
from computer_use.observation import Observation, ObservationManager
from computer_use.orchestrator import TaskOrchestrator, TaskState


class TestPhase3AuditAndSecurity:
    def test_secret_redaction(self):
        payload = {
            "api_key": "sk-1234567890abcdef1234567890",
            "password": "supersecretpassword123",
            "normal_field": "hello world with Bearer abcdef1234567890abcdef inside",
        }
        redacted = redact_secrets(payload)
        assert redacted["api_key"] == "[REDACTED_SECRET]"
        assert redacted["password"] == "[REDACTED_SECRET]"
        assert "[REDACTED_SECRET]" in redacted["normal_field"]

    def test_audit_logger_records_and_exports(self, tmp_path):
        logger = AuditLogger(task_id="t123", session_id="s456", log_dir=str(tmp_path))
        logger.record(
            step_id=1,
            event="action_execution",
            action_type="click",
            parameters={"coordinate": [100, 200]},
            result={"status": "ok"},
            cost_usd=0.002,
        )
        summary = logger.export_summary()
        assert summary["task_id"] == "t123"
        assert summary["total_entries"] == 1
        assert os.path.exists(summary["log_file"])


class TestPhase3BudgetGovernance:
    def test_budget_step_limit(self):
        budget = TaskBudget(max_steps=2)
        tracker = BudgetTracker(budget=budget)
        tracker.record_step()
        assert tracker.steps_count == 1
        with pytest.raises(BudgetExceededError):
            tracker.record_step()

    def test_budget_cost_limit(self):
        budget = TaskBudget(max_cost_usd=0.01)
        tracker = BudgetTracker(budget=budget)
        with pytest.raises(BudgetExceededError):
            tracker.record_model_call(cost_usd=0.02)


class TestPhase3ObservationLayer:
    def test_observation_creation_and_search(self):
        mock_comp = MagicMock()
        mock_comp.screen_info.return_value = {"screens": [{"width": 1440, "height": 900, "scale": 2.0}]}
        mock_comp.active_window.return_value = {"app_name": "Notes", "window_title": "Daily Notes"}
        mock_comp.screenshot.return_value = {"base64": "dummyb64"}
        mock_comp.extract_text.return_value = {"lines": [], "items": [{"text": "Submit Form", "bounds": [100, 200, 80, 30]}]}

        obs_mgr = ObservationManager(mock_comp)
        obs = obs_mgr.capture_observation(with_som=False, with_ocr=True, with_ax=False)

        assert obs.active_app == "Notes"
        assert obs.screen_width == 1440
        matches = obs.find_elements("Submit Form")
        assert len(matches) == 1
        assert matches[0].title == "Submit Form"
        assert matches[0].center == (140, 215)


class TestPhase3ClosedLoopOrchestrator:
    def test_closed_loop_tool_feedback_cycle(self):
        decision_click = ModelDecision(
            text_content="Clicking submit",
            tool_calls=[ToolCallRequest(call_id="call_submit", tool_name="computer", arguments={"action": "click", "coordinate": [150, 250]})],
            usage=ModelUsage(prompt_tokens=80, completion_tokens=15, total_tokens=95, estimated_cost_usd=0.0005),
        )
        decision_done = ModelDecision(
            text_content="Goal achieved cleanly.",
            tool_calls=[],
            usage=ModelUsage(prompt_tokens=95, completion_tokens=10, total_tokens=105, estimated_cost_usd=0.0005),
        )

        provider = MockModelProvider(scripted_decisions=[decision_click, decision_done])
        mock_comp = MagicMock()
        mock_comp.screen_info.return_value = {"screens": [{"width": 1440, "height": 900, "scale": 2.0}]}
        mock_comp.active_window.return_value = {"app_name": "TestApp", "window_title": "Main"}
        mock_comp.screenshot.return_value = {"base64": "b64mock"}
        mock_comp.extract_text.return_value = {"lines": [], "items": []}
        mock_comp.click.return_value = {"status": "ok", "x": 150, "y": 250}

        orchestrator = TaskOrchestrator(
            model_provider=provider,
            computer=mock_comp,
            budget=TaskBudget(max_steps=5),
        )

        res = orchestrator.execute_goal("Click submit button and finish")

        assert res["success"] is True
        assert res["state"] == TaskState.COMPLETED.value
        assert "Goal achieved cleanly." in res["summary"]

        # Ensure the model provider received the tool response in its message history
        second_call_messages = provider.call_history[1]
        tool_reply = next((m for m in second_call_messages if m.get("role") == "tool"), None)
        assert tool_reply is not None
        assert tool_reply["tool_call_id"] == "call_submit"
        assert json.loads(tool_reply["content"])["status"] == "ok"
