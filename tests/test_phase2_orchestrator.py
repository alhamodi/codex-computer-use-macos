"""
Tests for Phase 2: Model Abstraction, Task Orchestrator, Semantic Goals, and Workflows.
"""

import pytest
from unittest.mock import MagicMock, patch

from computer_use.models.base import ModelDecision, ModelUsage, ToolCallRequest
from computer_use.models.mock_provider import MockModelProvider
from computer_use.models.openai_provider import OpenAIModelProvider
from computer_use.orchestrator import TaskOrchestrator, TaskState
from computer_use.semantic import SemanticResolver, SemanticTarget
from computer_use.workflows import MultiAppWorkflowManager


class TestPhase2ModelAdapters:
    def test_mock_provider_decisions(self):
        decision1 = ModelDecision(
            text_content="Moving mouse",
            tool_calls=[ToolCallRequest(call_id="call_1", tool_name="computer", arguments={"action": "mouse_move", "coordinate": [100, 200]})],
            usage=ModelUsage(prompt_tokens=50, completion_tokens=10, total_tokens=60, estimated_cost_usd=0.0001),
        )
        provider = MockModelProvider(scripted_decisions=[decision1])
        assert provider.capabilities.supports_computer_use is True
        assert provider.capabilities.supports_vision is True

        # First call gets decision1
        res1 = provider.generate_decision([{"role": "user", "content": "hi"}])
        assert res1.has_tool_calls is True
        assert res1.tool_calls[0].tool_name == "computer"
        assert res1.tool_calls[0].arguments["action"] == "mouse_move"

        # Second call gets default finish decision
        res2 = provider.generate_decision([{"role": "user", "content": "next"}])
        assert res2.has_tool_calls is False
        assert "Goal accomplished" in res2.text_content
        assert provider.cumulative_usage.total_tokens == 240

    def test_openai_provider_cost_estimation(self):
        provider = OpenAIModelProvider(model_name="gpt-4o", api_key="sk-test-dummy")
        assert provider.capabilities.name == "openai-gpt-4o"
        # 1000 input tokens = $0.005, 1000 output tokens = $0.015 -> total $0.02
        cost = provider.estimate_cost(1000, 1000)
        assert abs(cost - 0.02) < 0.0001


class TestPhase2SemanticResolver:
    def test_semantic_resolution_from_som(self):
        resolver = SemanticResolver()
        # Seed the som registry with a mock element
        resolver.som_registry.register(
            mark_id=1,
            element_data={
                "bounds": [250, 350, 120, 40],
                "box": [250, 350, 120, 40],
                "role": "button",
                "title": "Export Video",
                "text": "Export Video",
            },
        )

        target = resolver.resolve("Export Video", role="button", prefer_source="any")
        assert target.found is True
        assert target.x == 250 + 60
        assert target.y == 350 + 20
        assert target.source == "som"
        assert target.mark_id == 1

    def test_semantic_resolution_not_found(self):
        resolver = SemanticResolver()
        target = resolver.resolve("NonExistentSpecialButtonXYZ_999")
        assert target.found is False
        assert target.source == "none"


class TestPhase2TaskOrchestrator:
    def test_orchestrator_multi_step_flow(self):
        # Setup mock decisions
        decision_click = ModelDecision(
            text_content="Clicking target button",
            tool_calls=[ToolCallRequest(call_id="c1", tool_name="computer", arguments={"action": "click", "coordinate": [200, 300]})],
            usage=ModelUsage(prompt_tokens=100, completion_tokens=20, total_tokens=120, estimated_cost_usd=0.001),
        )
        decision_finish = ModelDecision(
            text_content="Task successfully completed!",
            tool_calls=[],
            usage=ModelUsage(prompt_tokens=120, completion_tokens=15, total_tokens=135, estimated_cost_usd=0.001),
        )

        mock_provider = MockModelProvider(scripted_decisions=[decision_click, decision_finish])
        mock_computer = MagicMock()
        mock_computer.screenshot.return_value = {"base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==", "width": 1280, "height": 800}
        mock_computer.click.return_value = {"status": "ok", "x": 200, "y": 300}

        orchestrator = TaskOrchestrator(
            model_provider=mock_provider,
            computer=mock_computer,
            max_steps=5,
        )

        result = orchestrator.execute_goal("Open application and click button")

        assert result["success"] is True
        assert result["state"] == TaskState.COMPLETED.value
        assert "Task successfully completed!" in result["summary"]
        assert result["metrics"].successful_steps == 1
        assert result["metrics"].model_usage.total_tokens == 255
        mock_computer.click.assert_called_once_with(200, 300)

    def test_orchestrator_stagnation_detection(self):
        orchestrator = TaskOrchestrator(
            model_provider=MockModelProvider(),
            computer=MagicMock(),
        )
        sig = "click:[100, 100]:"
        # First 2 times: no stagnation
        assert orchestrator.check_stagnation(sig, "hash1") is False
        assert orchestrator.check_stagnation(sig, "hash1") is False
        # 3rd time: triggers stagnation detection
        assert orchestrator.check_stagnation(sig, "hash1") is True
        assert orchestrator.metrics.stagnation_events == 1


class TestPhase2Workflows:
    def test_davinci_pipeline_not_running(self):
        mock_comp = MagicMock()
        mock_comp.davinci_status.return_value = {"is_running": False}

        wf_manager = MultiAppWorkflowManager(mock_comp)
        res = wf_manager.run_davinci_resolve_pipeline(target_page="edit")

        assert res.success is False
        assert "not running" in res.error

    def test_davinci_pipeline_success(self):
        mock_comp = MagicMock()
        mock_comp.davinci_status.return_value = {"is_running": True}
        mock_comp.focus_window.return_value = {"success": True}
        mock_comp.davinci_switch_page.return_value = {"status": "ok", "page": "color"}

        from computer_use.verification import VerificationResult, VerificationState
        with patch("computer_use.verification.ActionVerifier.verify_window_title") as mock_verify:
            mock_verify.return_value = VerificationResult(
                state=VerificationState.SUCCESS,
                evidence="DaVinci Resolve title matches",
                elapsed_seconds=0.1,
            )
            wf_manager = MultiAppWorkflowManager(mock_comp)
            res = wf_manager.run_davinci_resolve_pipeline(target_page="color")

            assert res.success is True
            assert res.verification_passed is True
            assert res.steps_executed == 4
