"""Spawn tool for creating background sub-agents.

Converted to ADK function-tool pattern. In ADK, sub-agent delegation
is handled natively via sub_agents, but this tool provides a dynamic
spawning mechanism for ad-hoc background tasks.
"""

from __future__ import annotations

from typing import Any

from google.adk.tools import ToolContext
from loguru import logger


async def spawn_agent(
    task: str,
    label: str = "",
    tool_context: ToolContext = None,
) -> dict:
    """Spawn a sub-agent to handle a task in the background.

    Use this for complex or time-consuming tasks that can run independently.
    The sub-agent will complete the task and report back when done.
    For deliverables or existing projects, inspect the workspace first
    and use a dedicated subdirectory when helpful.

    Args:
        task: The task for the sub-agent to complete.
        label: Optional short label for the task (for display).

    Returns:
        A dict with the spawn result or error.
    """
    state = tool_context.state if tool_context else {}

    # Get the subagent manager from state (injected by gateway/CLI setup)
    manager = state.get("_subagent_manager")
    if not manager:
        return {"error": "Sub-agent spawning not available in this context"}

    channel = state.get("_channel", "cli")
    chat_id = state.get("_chat_id", "direct")
    session_key = f"{channel}:{chat_id}"

    try:
        result = await manager.spawn(
            task=task,
            label=label,
            origin_channel=channel,
            origin_chat_id=chat_id,
            session_key=session_key,
        )
        return {"result": result}
    except Exception as e:
        return {"error": f"Error spawning sub-agent: {e}"}
