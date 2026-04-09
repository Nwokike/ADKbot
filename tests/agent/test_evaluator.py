"""Tests for the ADK-based evaluation agent
.

Refactored in Phase 5 to test ADK patterns instead of deprecated LLMProvider.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# Test fixtures for ADK components
@pytest.fixture
def mock_runner():
    """Create a mock ADK Runner for testing."""
    runner = MagicMock()
    runner.run_async = AsyncMock()
    return runner


@pytest.fixture
def mock_session_service():
    """Create a mock InMemorySessionService for testing."""
    service = MagicMock()
    service.create_session = AsyncMock()
    return service


def _create_mock_event(tool_result: dict | None = None, text: str = "", is_final: bool = True):
    """Create a mock ADK event with
    optional tool result."""
    event = MagicMock()
    event.is_final_response = MagicMock(return_value=is_final)
    event.content = MagicMock()
    event.content.parts = []

    if tool_result:
        part = MagicMock()
        # ADK uses function_response.response for tool results
        part.function_response = MagicMock()
        part.function_response.response = tool_result
        # Make sure hasattr checks pass
        part.text = None
        event.content.parts.append(part)

    if text:
        part = MagicMock()
        part.text = text
        part.function_response = None
        event.content.parts.append(part)

    return event


class TestAdkEvaluationAgent:
    """Tests for the AdkEvaluationAgent class."""

    @pytest.mark.asyncio
    async def test_should_notify_true(self):
        """Test that agent returns True when tool indicates notification."""
        from adkbot.utils.evaluator import AdkEvaluationAgent

        with (
            patch("adkbot.utils.evaluator.ADK_AVAILABLE", True),
            patch("adkbot.utils.evaluator.LlmAgent") as mock_llm_agent,
            patch("adkbot.utils.evaluator.LiteLlm") as mock_litellm,
            patch("adkbot.utils.evaluator.Runner") as mock_runner_cls,
            patch("adkbot.utils.evaluator.InMemorySessionService") as mock_session_svc,
        ):
            # Setup mock session service
            mock_session = MagicMock()
            mock_session_svc.return_value.create_session = AsyncMock(return_value=mock_session)

            # Setup mock runner
            mock_runner = MagicMock()
            mock_runner_cls.return_value = mock_runner

            # Create event with tool result indicating should_notify=True
            mock_event = _create_mock_event(
                tool_result={"should_notify": True, "reason": "user asked to be reminded"}
            )

            # Make run_async return an async generator
            async def mock_run(*args, **kwargs):
                yield mock_event

            mock_runner.run_async = mock_run

            # Create agent and test
            agent = AdkEvaluationAgent(model="gemini-2.0-flash")
            result = await agent.evaluate("Task completed with results", "check emails")
            assert result is True

    @pytest.mark.asyncio
    async def test_should_notify_false(self):
        """Test that agent returns False when tool indicates no notification."""
        from adkbot.utils.evaluator import AdkEvaluationAgent

        with (
            patch("adkbot.utils.evaluator.ADK_AVAILABLE", True),
            patch("adkbot.utils.evaluator.LlmAgent") as mock_llm_agent,
            patch("adkbot.utils.evaluator.LiteLlm") as mock_litellm,
            patch("adkbot.utils.evaluator.Runner") as mock_runner_cls,
            patch("adkbot.utils.evaluator.InMemorySessionService") as mock_session_svc,
        ):
            # Setup mock session service
            mock_session = MagicMock()
            mock_session_svc.return_value.create_session = AsyncMock(return_value=mock_session)

            # Setup mock runner
            mock_runner = MagicMock()
            mock_runner_cls.return_value = mock_runner

            # Create event with tool result indicating should_notify=False
            mock_event = _create_mock_event(
                tool_result={"should_notify": False, "reason": "routine check, nothing new"}
            )

            async def mock_run(*args, **kwargs):
                yield mock_event

            mock_runner.run_async = mock_run

            # Create agent and test
            agent = AdkEvaluationAgent(model="gemini-2.0-flash")
            result = await agent.evaluate("All clear, no updates", "check status")
            assert result is False

    @pytest.mark.asyncio
    async def test_fallback_on_error(self):
        """Test that evaluation returns True on errors (safe default)."""
        from adkbot.utils.evaluator import AdkEvaluationAgent

        with (
            patch("adkbot.utils.evaluator.ADK_AVAILABLE", True),
            patch("adkbot.utils.evaluator.LlmAgent") as mock_llm_agent,
            patch("adkbot.utils.evaluator.LiteLlm") as mock_litellm,
            patch("adkbot.utils.evaluator.Runner") as mock_runner_cls,
            patch("adkbot.utils.evaluator.InMemorySessionService") as mock_session_svc,
        ):
            # Setup mock session service
            mock_session = MagicMock()
            mock_session_svc.return_value.create_session = AsyncMock(return_value=mock_session)

            # Setup mock runner that raises an error
            mock_runner = MagicMock()
            mock_runner_cls.return_value = mock_runner

            async def mock_run(*args, **kwargs):
                raise RuntimeError("provider down")
                yield  # Never reached

            mock_runner.run_async = mock_run

            # Create agent and test - should return True on error
            agent = AdkEvaluationAgent(model="gemini-2.0-flash")
            result = await agent.evaluate("some response", "some task")
            assert result is True  # Safe fallback

    @pytest.mark.asyncio
    async def test_no_tool_call_fallback(self):
        """Test that evaluation returns True when no tool call is made."""
        from adkbot.utils.evaluator import AdkEvaluationAgent

        with (
            patch("adkbot.utils.evaluator.ADK_AVAILABLE", True),
            patch("adkbot.utils.evaluator.LlmAgent") as mock_llm_agent,
            patch("adkbot.utils.evaluator.LiteLlm") as mock_litellm,
            patch("adkbot.utils.evaluator.Runner") as mock_runner_cls,
            patch("adkbot.utils.evaluator.InMemorySessionService") as mock_session_svc,
        ):
            # Setup mock session service
            mock_session = MagicMock()
            mock_session_svc.return_value.create_session = AsyncMock(return_value=mock_session)

            # Setup mock runner
            mock_runner = MagicMock()
            mock_runner_cls.return_value = mock_runner

            # Create event without tool result (just text)
            mock_event = _create_mock_event(text="The response looks routine.")

            async def mock_run(*args, **kwargs):
                yield mock_event

            mock_runner.run_async = mock_run

            # Create agent and test - should return True (safe default)
            agent = AdkEvaluationAgent(model="gemini-2.0-flash")
            result = await agent.evaluate("routine check", "status check")
            assert result is True  # No tool call = safe default


class TestEvaluateResponseFunction:
    """Tests for the evaluate_response convenience function."""

    @pytest.mark.asyncio
    async def test_evaluate_response_with_model_string(self):
        """Test evaluate_response with a model string."""
        from adkbot.utils.evaluator import evaluate_response

        with (
            patch("adkbot.utils.evaluator.ADK_AVAILABLE", True),
            patch("adkbot.utils.evaluator.AdkEvaluationAgent") as mock_agent_cls,
        ):
            # Setup mock agent
            mock_agent = MagicMock()
            mock_agent.evaluate = AsyncMock(return_value=True)
            mock_agent_cls.return_value = mock_agent

            result = await evaluate_response("test response", "test task", model="gemini-2.0-flash")
            assert result is True
            mock_agent_cls.assert_called_once()

    @pytest.mark.asyncio
    async def test_evaluate_response_caches_agent(self):
        """Test that evaluate_response reuses cached agents."""
        from adkbot.utils.evaluator import _evaluation_agents, evaluate_response

        # Clear cache
        _evaluation_agents.clear()

        with (
            patch("adkbot.utils.evaluator.ADK_AVAILABLE", True),
            patch("adkbot.utils.evaluator.AdkEvaluationAgent") as mock_agent_cls,
        ):
            # Setup mock agent
            mock_agent = MagicMock()
            mock_agent.evaluate = AsyncMock(return_value=True)
            mock_agent_cls.return_value = mock_agent

            # First call
            await evaluate_response("test1", "task1", model="gemini-2.0-flash")
            # Second call with same model should use cache
            await evaluate_response("test2", "task2", model="gemini-2.0-flash")

            # Agent should only be created once
            mock_agent_cls.assert_called_once()

    @pytest.mark.asyncio
    async def test_evaluate_response_different_models(self):
        """Test that evaluate_response creates different agents for different models."""
        from adkbot.utils.evaluator import _evaluation_agents, evaluate_response

        # Clear cache
        _evaluation_agents.clear()

        with (
            patch("adkbot.utils.evaluator.ADK_AVAILABLE", True),
            patch("adkbot.utils.evaluator.AdkEvaluationAgent") as mock_agent_cls,
        ):
            # Setup mock agent
            mock_agent = MagicMock()
            mock_agent.evaluate = AsyncMock(return_value=True)
            mock_agent_cls.return_value = mock_agent

            # Call with different models
            await evaluate_response("test", "task", model="gemini-2.0-flash")
            await evaluate_response("test", "task", model="openai/gpt-4o")

            # Agent should be created twice (different models)
            assert mock_agent_cls.call_count == 2

    @pytest.mark.asyncio
    async def test_evaluate_response_adk_not_available(self):
        """Test evaluate_response when ADK is not available."""
        from adkbot.utils.evaluator import evaluate_response

        with patch("adkbot.utils.evaluator.ADK_AVAILABLE", False):
            # Should return True (safe default) when ADK not available
            result = await evaluate_response("test", "task", model="gemini-2.0-flash")
            assert result is True
