"""Subagent manager for background task execution.

This module provides the AdkSubagentManager class for spawning and managing
background subagent tasks using Google ADK's Runner pattern.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any, Callable

from loguru import logger

from adkbot.agent.skills import BUILTIN_SKILLS_DIR
from adkbot.bus.events import InboundMessage
from adkbot.bus.queue import MessageBus
from adkbot.config.schema import ExecToolConfig, WebSearchConfig

# ADK imports (with graceful fallback)
try:
    from google.adk.agents import LlmAgent
    from google.adk.memory import InMemoryMemoryService
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
    InMemoryMemoryService = Any  # type: ignore
    types = Any  # type: ignore


# ---------------------------------------------------------------------------
# ADK-native SubagentManager
# ---------------------------------------------------------------------------


class AdkSubagentManager:
    """ADK-native subagent manager using google.adk.runners.Runner.

    Provides subagent functionality using ADK's Runner pattern.
    Used by AdkAgentLoop to spawn background tasks.

    Architecture:
    - Uses ADK's Runner for LLM orchestration
    - Uses LiteLlm model wrapper for multi-provider support
    - Uses ADK's InMemorySessionService for session management
    - Tools are plain functions (auto-wrapped by ADK's FunctionTool)
    """

    APP_NAME = "adkbot_subagent"

    def __init__(
        self,
        workspace: Path,
        bus: MessageBus,
        model: str = "nvidia_nim/nvidia/nemotron-3-super-120b-a12b",
        api_key: str | None = None,
        api_base: str | None = None,
        restrict_to_workspace: bool = False,
    ):
        """Initialize the ADK subagent manager.

        Args:
            workspace: Path to workspace directory
            bus: Message bus for result announcements
            model: LiteLLM model string (e.g., "gemini/gemini-3.1-pro-preview")
            api_key: API key for the model provider
            api_base: Optional API base URL
            restrict_to_workspace: Whether to restrict file operations to workspace
        """
        if not ADK_AVAILABLE:
            raise ImportError("Google ADK is not installed. Install with: pip install google-adk")

        self.workspace = workspace
        self.bus = bus
        self.model = model
        self.api_key = api_key
        self.api_base = api_base
        self.restrict_to_workspace = restrict_to_workspace

        # Task tracking
        self._running_tasks: dict[str, asyncio.Task[None]] = {}
        self._session_tasks: dict[str, set[str]] = {}

        logger.debug("AdkSubagentManager initialized | model={}", model)

    async def spawn(
        self,
        task: str,
        label: str | None = None,
        origin_channel: str = "cli",
        origin_chat_id: str = "direct",
        session_key: str | None = None,
    ) -> str:
        """Spawn a background subagent task.

        Args:
            task: The task description for the subagent
            label: Optional label for the task
            origin_channel: Channel that originated the request
            origin_chat_id: Chat ID that originated the request
            session_key: Optional session key for task tracking

        Returns:
            Status message with task ID
        """
        task_id = str(uuid.uuid4())[:8]
        display_label = label or task[:30] + ("..." if len(task) > 30 else "")
        origin = {"channel": origin_channel, "chat_id": origin_chat_id}

        bg_task = asyncio.create_task(self._run_subagent(task_id, task, display_label, origin))
        self._running_tasks[task_id] = bg_task

        if session_key:
            self._session_tasks.setdefault(session_key, set()).add(task_id)

        def _cleanup(_: asyncio.Task) -> None:
            self._running_tasks.pop(task_id, None)
            if session_key and (ids := self._session_tasks.get(session_key)):
                ids.discard(task_id)
                if not ids:
                    del self._session_tasks[session_key]

        bg_task.add_done_callback(_cleanup)

        logger.info("Spawned ADK subagent [{}]: {}", task_id, display_label)
        return f"Subagent [{display_label}] started (id: {task_id}). I'll notify you when it completes."

    async def _run_subagent(
        self,
        task_id: str,
        task: str,
        label: str,
        origin: dict[str, str],
    ) -> None:
        """Execute the subagent task using ADK Runner."""
        logger.info("ADK Subagent [{}] starting task: {}", task_id, label)

        try:
            # Create session service for this subagent
            session_service = InMemorySessionService()

            # Create session
            session = await session_service.create_session(
                app_name=self.APP_NAME,
                user_id="subagent",
                session_id=task_id,
                state={"workspace": str(self.workspace)},
            )

            # Build instruction
            instruction = self._build_subagent_instruction()

            # Create LiteLLM model wrapper
            litellm = LiteLlm(
                model=self.model,
                api_key=self.api_key,
                api_base=self.api_base,
            )

            # Get tools for subagent
            tools = self._get_subagent_tools()

            # Create LlmAgent
            agent = LlmAgent(
                name=f"subagent_{task_id}",
                model=litellm,
                instruction=instruction,
                description=f"Background subagent for: {label}",
                tools=tools,
            )

            # Create Runner
            runner = Runner(
                agent=agent,
                app_name=self.APP_NAME,
                session_service=session_service,
            )

            # Build the task message
            user_content = types.Content(
                role="user",
                parts=[types.Part(text=task)],
            )

            # Run the agent
            final_response = ""
            async for event in runner.run_async(
                user_id="subagent",
                session_id=task_id,
                new_message=user_content,
            ):
                if event.is_final_response():
                    if event.content and event.content.parts:
                        final_response = event.content.parts[0].text or ""

            logger.info("ADK Subagent [{}] completed: {}", task_id, label)

            # Announce result
            await self._announce_result(task_id, label, final_response, origin)

        except Exception as e:
            logger.exception("ADK Subagent [{}] failed: {}", task_id, e)
            await self._announce_result(
                task_id,
                label,
                f"Error: {e}",
                origin,
                is_error=True,
            )

    def _get_subagent_tools(self) -> list[Callable]:
        """Get tools available to subagents.

        Subagents get a subset of tools - no spawning more subagents
        to prevent infinite recursion.
        """
        from adkbot.agent.tools.filesystem import (
            edit_file,
            list_directory,
            read_file,
            write_file,
        )
        from adkbot.agent.tools.shell import execute_command
        from adkbot.agent.tools.web import web_fetch, web_search

        tools: list[Callable] = [
            # File operations
            read_file,
            write_file,
            edit_file,
            list_directory,
            # Web tools
            web_search,
            web_fetch,
        ]

        # Add shell execution if not restricted
        if not self.restrict_to_workspace:
            tools.append(execute_command)

        return tools

    def _build_subagent_instruction(self) -> str:
        """Build the instruction prompt for subagents."""
        return f"""You are a focused subagent executing a specific task.

## Workspace
Your workspace is: {self.workspace}

## Guidelines
- Focus on completing the assigned task efficiently
- Use available tools as needed
- Report results concisely
- If you cannot complete the task, explain why

## Available Tools
- read_file: Read file contents
- write_file: Create or overwrite files
- edit_file: Make targeted edits to files
- list_directory: List directory contents
- web_search: Search the web
- web_fetch: Fetch web pages

Execute the task and report your findings.
"""

    async def _announce_result(
        self,
        task_id: str,
        label: str,
        result: str,
        origin: dict[str, str],
        is_error: bool = False,
    ) -> None:
        """Announce subagent result to the origin channel."""
        channel = origin.get("channel", "cli")
        chat_id = origin.get("chat_id", "direct")

        # Format the result message
        if is_error:
            content = f"❌ **Subagent [{label}]** (id: {task_id}) failed:\n\n{result}"
        else:
            # Truncate long results
            display_result = result[:2000] + "..." if len(result) > 2000 else result
            content = f"✅ **Subagent [{label}]** (id: {task_id}) completed:\n\n{display_result}"

        # Create outbound message
        from adkbot.bus.events import OutboundMessage

        msg = OutboundMessage(
            channel=channel,
            chat_id=chat_id,
            content=content,
            media=[],
            metadata={"subagent_result": True, "task_id": task_id},
        )

        # Publish to bus
        await self.bus.publish_outbound(msg)

    async def cancel_by_session(self, session_key: str) -> int:
        """Cancel all tasks for a session.

        Args:
            session_key: The session key to cancel tasks for

        Returns:
            Number of tasks cancelled
        """
        task_ids = self._session_tasks.get(session_key, set())
        cancelled = 0

        for task_id in list(task_ids):
            task = self._running_tasks.get(task_id)
            if task and not task.done():
                task.cancel()
                cancelled += 1
                logger.info("Cancelled subagent [{}] for session {}", task_id, session_key)

        return cancelled

    def get_running_count(self) -> int:
        """Return the number of currently running subagent tasks."""
        return len([t for t in self._running_tasks.values() if not t.done()])