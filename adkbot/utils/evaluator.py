"""Post-run evaluation for background tasks (heartbeat & cron).

After the agent executes a background task, this module makes a lightweight LLM
call to decide whether the result warrants notifying the user.

Uses ADK patterns: LlmAgent + LiteLlm + Runner for model-agnostic evaluation.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

try:
    from google.adk.agents import LlmAgent
    from google.adk.models.lite_llm import LiteLlm
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    ADK_AVAILABLE = True
except ImportError:
    ADK_AVAILABLE = False
    LlmAgent = Any  # type: ignore
    LiteLlm = Any  # type: ignore
    Runner = Any  # type: ignore
    InMemorySessionService = Any  # type: ignore
    types = Any  # type: ignore

_EVALUATE_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "evaluate_notification",
            "description": "Decide whether the user should be notified about this background task result.",
            "parameters": {
                "type": "object",
                "properties": {
                    "should_notify": {
                        "type": "boolean",
                        "description": "true = result contains actionable/important info the user should see; false = routine or empty, safe to suppress",
                    },
                    "reason": {
                        "type": "string",
                        "description": "One-sentence reason for the decision",
                    },
                },
                "required": ["should_notify"],
            },
        },
    }
]

_SYSTEM_PROMPT = (
    "You are a notification gate for a background agent. "
    "You will be given the original task and the agent's response. "
    "Call the evaluate_notification tool to decide whether the user "
    "should be notified.\n\n"
    "Notify when the response contains actionable information, errors, "
    "completed deliverables, or anything the user explicitly asked to "
    "be reminded about.\n\n"
    "Suppress when the response is a routine status check with nothing "
    "new, a confirmation that everything is normal, or essentially empty."
)

_APP_NAME = "evaluator"
_USER_ID = "evaluator_system"


class AdkEvaluationAgent:
    """ADK-native evaluation agent for deciding notification delivery.

    Uses LlmAgent with LiteLlm for model-agnostic evaluation.
    """

    def __init__(self, model: str, api_key: str | None = None, api_base: str | None = None):
        """Initialize the evaluation agent.

        Args:
            model: LiteLLM model string (e.g., "gemini/gemini-3.1-pro-preview", "openrouter/openai/gpt-4")
            api_key: Optional API key (can also use environment variables)
            api_base: Optional API base URL for custom endpoints
        """
        if not ADK_AVAILABLE:
            raise ImportError("Google ADK is not installed. Install with: pip install google-adk")

        self.model = model
        self.api_key = api_key
        self.api_base = api_base

        # Create LiteLlm model wrapper
        litellm = LiteLlm(
            model=model,
            api_key=api_key,
            api_base=api_base,
        )

        # Create LlmAgent for evaluation
        self.agent = LlmAgent(
            name="notification_evaluator",
            model=litellm,
            instruction=_SYSTEM_PROMPT,
            description="Evaluates whether background task results should be delivered to users",
        )

        # Create runner with in-memory session service
        self.session_service = InMemorySessionService()
        self.runner = Runner(
            agent=self.agent,
            app_name=_APP_NAME,
            session_service=self.session_service,
        )

    async def evaluate(self, response: str, task_context: str) -> bool:
        """Decide whether a background-task result should be delivered to the user.

        Uses ADK Runner to execute the evaluation agent with tool calling.

        Args:
            response: The agent's response from the background task
            task_context: The original task that was executed

        Returns:
            True if the user should be notified, False to suppress.
            Defaults to True on any failure to ensure important messages are not dropped.
        """
        import uuid

        try:
            # Create session for this evaluation
            session_id = f"eval_{uuid.uuid4().hex[:8]}"
            await self.session_service.create_session(
                app_name=_APP_NAME,
                user_id=_USER_ID,
                session_id=session_id,
            )

            # Build the evaluation prompt
            user_content = types.Content(
                role="user",
                parts=[
                    types.Part(
                        text=f"## Original task\n{task_context}\n\n## Agent response\n{response}"
                    )
                ],
            )

            # Run the agent and collect response
            final_response = ""
            tool_result = None

            async for event in self.runner.run_async(
                user_id=_USER_ID,
                session_id=session_id,
                new_message=user_content,
            ):
                # Check for tool calls in the response
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        # Check for function call response
                        if hasattr(part, "function_response") and part.function_response:
                            tool_result = part.function_response.response
                        elif hasattr(part, "text") and part.text:
                            final_response += part.text

                # Check for final response with tool result
                if event.is_final_response() and tool_result:
                    break

            # Parse tool result if available
            if tool_result:
                if isinstance(tool_result, dict):
                    should_notify = tool_result.get("should_notify", True)
                    reason = tool_result.get("reason", "")
                else:
                    should_notify = True
                    reason = ""
                logger.info(
                    "evaluate_response: should_notify={}, reason={}",
                    should_notify,
                    reason,
                )
                return bool(should_notify)

            # If we got a final response without tool call, parse from text
            if final_response:
                # Check if the response contains tool-like JSON
                import json
                import re

                # Try to extract JSON from the response
                json_match = re.search(
                    r"\{[^{}]*should_notify[^{}]*\}", final_response, re.IGNORECASE
                )
                if json_match:
                    try:
                        parsed = json.loads(json_match.group())
                        should_notify = parsed.get("should_notify", True)
                        logger.info(
                            "evaluate_response: parsed from text, should_notify={}",
                            should_notify,
                        )
                        return bool(should_notify)
                    except json.JSONDecodeError:
                        pass

                logger.warning("evaluate_response: no tool call returned, defaulting to notify")
                return True

            # Default to notify if we couldn't parse anything
            logger.warning("evaluate_response: no valid response, defaulting to notify")
            return True

        except Exception:
            logger.exception("evaluate_response failed, defaulting to notify")
            return True


# Cache for evaluation agents to avoid recreating for each call
_evaluation_agents: dict[tuple[str, str | None, str | None], AdkEvaluationAgent] = {}


async def evaluate_response(
    response: str,
    task_context: str,
    model: str,
    api_key: str | None = None,
    api_base: str | None = None,
) -> bool:
    """Decide whether a background-task result should be delivered to the user.

    Uses a lightweight tool-call LLM request via ADK's Runner.
    Falls back to True (notify) on any failure so that important messages
    are never silently dropped.

    Args:
        response: The agent's response from the background task
        task_context: The original task that was executed
        model: LiteLLM model string (e.g., "gemini/gemini-3.1-pro-preview")
        api_key: Optional API key (can also use environment variables)
        api_base: Optional API base URL for custom endpoints

    Returns:
        True if the user should be notified, False to suppress.
    """
    global _evaluation_agents

    # Get or create cached evaluation agent
    cache_key = (model, api_key, api_base)
    if cache_key not in _evaluation_agents:
        try:
            _evaluation_agents[cache_key] = AdkEvaluationAgent(
                model=model,
                api_key=api_key,
                api_base=api_base,
            )
        except ImportError as e:
            logger.warning("ADK not available for evaluation: {}", e)
            return True

    agent = _evaluation_agents[cache_key]
    return await agent.evaluate(response, task_context)