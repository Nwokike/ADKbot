"""ADK callback functions for agent lifecycle hooks.

Replaces the old AgentHook system with ADK's native callback mechanism.
These callbacks are passed directly to the Agent constructor.

Reference: https://google.github.io/adk-docs/callbacks/
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from loguru import logger

# ADK callback context and types
try:
    from google.adk.agents.callback_context import CallbackContext
    from google.adk.models import LlmRequest, LlmResponse
    from google.adk.tools import BaseTool, ToolContext
    from google.genai import types
except ImportError:
    # Graceful degradation if ADK types not available
    CallbackContext = Any
    LlmRequest = Any
    LlmResponse = Any
    BaseTool = Any
    ToolContext = Any


# ---------------------------------------------------------------------------
# Agent callbacks
# ---------------------------------------------------------------------------

def before_agent_callback(
    callback_context: CallbackContext,
) -> Optional[types.Content]:
    """Runs at the start of agent processing.

    Used for:
    - Request logging
    - Performance monitoring (start timer)
    - State initialization
    """
    state = callback_context.state

    # Initialize request counter
    if "request_counter" not in state:
        state["request_counter"] = 1
    else:
        state["request_counter"] = state["request_counter"] + 1

    # Store start time for duration calculation
    state["_request_start_time"] = datetime.now().isoformat()

    logger.info(
        "Agent run started | request #{} | agent={}",
        state["request_counter"],
        callback_context.agent_name,
    )

    return None  # Continue with normal agent processing


def after_agent_callback(
    callback_context: CallbackContext,
) -> Optional[types.Content]:
    """Runs after agent processing completes.

    Used for:
    - Logging completion and duration
    - Cleanup
    """
    state = callback_context.state

    # Calculate duration
    duration = None
    start_str = state.get("_request_start_time")
    if start_str:
        try:
            start = datetime.fromisoformat(start_str)
            duration = (datetime.now() - start).total_seconds()
        except (ValueError, TypeError):
            pass

    logger.info(
        "Agent run completed | request #{} | duration={}s",
        state.get("request_counter", "?"),
        f"{duration:.2f}" if duration else "?",
    )

    return None  # Continue with normal processing


# ---------------------------------------------------------------------------
# Model callbacks
# ---------------------------------------------------------------------------

def before_model_callback(
    callback_context: CallbackContext,
    llm_request: LlmRequest,
) -> Optional[LlmResponse]:
    """Intercepts requests before they reach the LLM.

    Used for:
    - Injecting runtime context (current time, etc.)
    - Content filtering
    - Request logging
    """
    logger.debug(
        "Model call | agent={} | invocation={}",
        callback_context.agent_name,
        callback_context.invocation_id,
    )

    return None  # Proceed with normal model request


def after_model_callback(
    callback_context: CallbackContext,
    llm_response: LlmResponse,
) -> Optional[LlmResponse]:
    """Processes responses after they come from the LLM.

    Used for:
    - Usage tracking (tokens)
    - Response logging
    """
    logger.debug(
        "Model response received | agent={}",
        callback_context.agent_name,
    )

    return None  # Use original response


# ---------------------------------------------------------------------------
# Tool callbacks
# ---------------------------------------------------------------------------

def before_tool_callback(
    tool: BaseTool,
    args: Dict[str, Any],
    tool_context: ToolContext,
) -> Optional[Dict]:
    """Runs before a tool is executed.

    Used for:
    - Logging tool calls
    - Argument validation/modification
    - Access control (workspace restriction)
    """
    logger.info(
        "Tool call: {} | args_keys={}",
        tool.name if hasattr(tool, "name") else str(tool),
        list(args.keys()),
    )

    # Track tool usage in state
    tools_used = tool_context.state.get("_tools_used", [])
    tool_name = tool.name if hasattr(tool, "name") else str(tool)
    tools_used.append(tool_name)
    tool_context.state["_tools_used"] = tools_used

    return None  # Proceed with normal tool call


def after_tool_callback(
    tool: BaseTool,
    args: Dict[str, Any],
    tool_context: ToolContext,
    tool_response: Dict,
) -> Optional[Dict]:
    """Runs after a tool execution completes.

    Used for:
    - Logging tool results
    - Response enhancement
    - Error handling
    """
    tool_name = tool.name if hasattr(tool, "name") else str(tool)
    logger.debug("Tool completed: {}", tool_name)

    return None  # Use original response
