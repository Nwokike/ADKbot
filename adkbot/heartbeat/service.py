"""Heartbeat service — periodic agent wake-up to check for tasks.

Uses ADK patterns (LlmAgent + LiteLlm + Runner) for model-agnostic
decision-making and task execution.
"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Any, Callable, Coroutine

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

# Tool schema for heartbeat decision
_HEARTBEAT_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "heartbeat",
            "description": "Report heartbeat decision after reviewing tasks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["skip", "run"],
                        "description": "skip = nothing to do, run = has active tasks",
                    },
                    "tasks": {
                        "type": "string",
                        "description": "Natural-language summary of active tasks (required for run)",
                    },
                },
                "required": ["action"],
            },
        },
    }
]

_SYSTEM_PROMPT = (
    "You are a heartbeat agent. You will be given the current time and "
    "the contents of a HEARTBEAT.md file. "
    "Call the heartbeat tool to report your decision.\n\n"
    "Return 'run' if there are active tasks that need attention.\n"
    "Return 'skip' if everything is routine and nothing needs to be done."
)

_APP_NAME = "heartbeat"
_USER_ID = "heartbeat_system"


class AdkHeartbeatAgent:
    """ADK-native heartbeat decision agent.

    Uses LlmAgent with LiteLlm for model-agnostic heartbeat decisions.
    Implements the tool-call pattern for structured decision output.
    """

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        api_base: str | None = None,
        timezone: str | None = None,
    ):
        """Initialize the heartbeat decision agent.

        Args:
            model: LiteLLM model string (e.g., "gemini-2.0-flash")
            api_key: Optional API key (can also use environment variables)
            api_base: Optional API base URL for custom endpoints
            timezone: Timezone for timestamp generation
        """
        if not ADK_AVAILABLE:
            raise ImportError("Google ADK is not installed. Install with: pip install google-adk")

        self.model = model
        self.api_key = api_key
        self.api_base = api_base
        self.timezone = timezone or "UTC"

        # Create LiteLlm model wrapper
        litellm = LiteLlm(
            model=model,
            api_key=api_key,
            api_base=api_base,
        )

        # Create LlmAgent for heartbeat decisions
        self.agent = LlmAgent(
            name="heartbeat_decision",
            model=litellm,
            instruction=_SYSTEM_PROMPT,
            description="Decides whether heartbeat tasks need to be executed",
        )

        # Create runner with in-memory session service
        self.session_service = InMemorySessionService()
        self.runner = Runner(
            agent=self.agent,
            app_name=_APP_NAME,
            session_service=self.session_service,
        )

        logger.debug(
            "AdkHeartbeatAgent initialized | model={} | timezone={}",
            model,
            self.timezone,
        )

    async def decide(self, content: str) -> tuple[str, str]:
        """Decide whether there are active tasks.

        Uses ADK's Runner to execute the heartbeat agent with tool calling.

        Args:
            content: The contents of HEARTBEAT.md

        Returns:
            Tuple of (action, tasks) where action is 'skip' or 'run'
        """
        from adkbot.utils.helpers import current_time_str

        try:
            # Create session for this decision
            session_id = f"hb_{uuid.uuid4().hex[:8]}"
            await self.session_service.create_session(
                app_name=_APP_NAME,
                user_id=_USER_ID,
                session_id=session_id,
            )

            # Build the user message
            user_content = types.Content(
                role="user",
                parts=[
                    types.Part(
                        text=(
                            f"Current Time: {current_time_str(self.timezone)}\n\n"
                            "Review the following HEARTBEAT.md and decide whether "
                            "there are active tasks.\n\n"
                            f"{content}"
                        )
                    )
                ],
            )

            # Run the agent and collect response
            tool_result = None
            final_response = ""

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
                    action = tool_result.get("action", "skip")
                    tasks = tool_result.get("tasks", "")
                    return action, tasks

            # If we got a final response without tool call, parse from text
            if final_response:
                import json
                import re

                # Try to extract JSON from the response
                json_match = re.search(r"\{[^{}]*action[^{}]*\}", final_response, re.IGNORECASE)
                if json_match:
                    try:
                        parsed = json.loads(json_match.group())
                        action = parsed.get("action", "skip")
                        tasks = parsed.get("tasks", "")
                        return action, tasks
                    except json.JSONDecodeError:
                        pass

                # Check for keywords in text
                if "run" in final_response.lower():
                    return "run", final_response[:200]

            # Default to skip if we couldn't parse anything
            logger.warning("heartbeat: no valid decision, defaulting to skip")
            return "skip", ""

        except Exception:
            logger.exception("heartbeat decision failed, defaulting to skip")
            return "skip", ""


class HeartbeatService:
    """
    Periodic heartbeat service that wakes the agent to check for tasks.

    Decision step: reads HEARTBEAT.md and asks the LLM — via a virtual
    tool call — whether there are active tasks. This avoids free-text parsing
    and the unreliable HEARTBEAT_OK token.

    Execution step: only triggered when the decision returns ``run``.
    The ``on_execute`` callback runs the task through the full agent loop
    and returns the result to deliver.
    """

    def __init__(
        self,
        workspace: Path,
        model: str,
        api_key: str | None = None,
        api_base: str | None = None,
        on_execute: Callable[[str], Coroutine[Any, Any, str]] | None = None,
        on_notify: Callable[[str], Coroutine[Any, Any, None]] | None = None,
        interval_s: int = 30 * 60,
        enabled: bool = True,
        timezone: str | None = None,
    ):
        """Initialize the heartbeat service.

        Args:
            workspace: Path to the workspace directory
            model: LiteLLM model string (e.g., "gemini-2.0-flash")
            api_key: Optional API key (can also use environment variables)
            api_base: Optional API base URL for custom endpoints
            on_execute: Callback to execute tasks when heartbeat finds work
            on_notify: Callback to deliver responses to the user
            interval_s: Interval between heartbeat checks in seconds
            enabled: Whether the heartbeat is enabled
            timezone: Timezone for timestamp generation
        """
        self.workspace = workspace
        self.model = model
        self.api_key = api_key
        self.api_base = api_base
        self.on_execute = on_execute
        self.on_notify = on_notify
        self.interval_s = interval_s
        self.enabled = enabled
        self.timezone = timezone
        self._running = False
        self._task: asyncio.Task | None = None
        self._decision_agent: AdkHeartbeatAgent | None = None

    @property
    def heartbeat_file(self) -> Path:
        return self.workspace / "HEARTBEAT.md"

    def _get_decision_agent(self) -> AdkHeartbeatAgent:
        """Get or create the ADK heartbeat decision agent."""
        if self._decision_agent is None:
            self._decision_agent = AdkHeartbeatAgent(
                model=self.model,
                api_key=self.api_key,
                api_base=self.api_base,
                timezone=self.timezone,
            )
        return self._decision_agent

    def _read_heartbeat_file(self) -> str | None:
        if self.heartbeat_file.exists():
            try:
                return self.heartbeat_file.read_text(encoding="utf-8")
            except Exception:
                return None
        return None

    async def _decide(self, content: str) -> tuple[str, str]:
        """Ask LLM to decide skip/run via virtual tool call.

        Returns (action, tasks) where action is 'skip' or 'run'.
        """
        try:
            agent = self._get_decision_agent()
            return await agent.decide(content)
        except ImportError:
            logger.warning("ADK not available for heartbeat decision, skipping")
            return "skip", ""
        except Exception as e:
            logger.error("Heartbeat decision error: {}", e)
            return "skip", ""

    async def start(self) -> None:
        """Start the heartbeat service."""
        if not self.enabled:
            logger.info("Heartbeat disabled")
            return

        if self._running:
            logger.warning("Heartbeat already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Heartbeat started (every {}s)", self.interval_s)

    def stop(self) -> None:
        """Stop the heartbeat service."""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None

    async def _run_loop(self) -> None:
        """Main heartbeat loop."""
        while self._running:
            try:
                await asyncio.sleep(self.interval_s)
                if self._running:
                    await self._tick()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Heartbeat error: {}", e)

    async def _tick(self) -> None:
        """Execute a single heartbeat tick."""
        from adkbot.utils.evaluator import evaluate_response

        content = self._read_heartbeat_file()
        if not content:
            logger.debug("Heartbeat: HEARTBEAT.md missing or empty")
            return

        logger.info("Heartbeat: checking for tasks...")

        try:
            action, tasks = await self._decide(content)

            if action != "run":
                logger.info("Heartbeat: OK (nothing to report)")
                return

            logger.info("Heartbeat: tasks found, executing...")

            if self.on_execute:
                response = await self.on_execute(tasks)

                if response:
                    should_notify = await evaluate_response(
                        response,
                        tasks,
                        self.model,
                        self.api_key,
                    )

                    if should_notify and self.on_notify:
                        logger.info("Heartbeat: completed, delivering response")
                        await self.on_notify(response)
                    else:
                        logger.info("Heartbeat: silenced by post-run evaluation")

        except Exception:
            logger.exception("Heartbeat execution failed")

    async def trigger_now(self) -> str | None:
        """Manually trigger a heartbeat."""
        content = self._read_heartbeat_file()
        if not content:
            return None

        action, tasks = await self._decide(content)

        if action != "run" or not self.on_execute:
            return None

        return await self.on_execute(tasks)
