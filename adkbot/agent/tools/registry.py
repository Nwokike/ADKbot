"""Tool registry — returns the list of ADK function tools based on config.

Replaces the old Tool-class registry with a simple function that returns
a filtered list of callable functions for ADK's Agent.tools parameter.
"""

from __future__ import annotations

from typing import Any, Callable

from loguru import logger


# ---------------------------------------------------------------------------
# ToolRegistry (used by MCP integration and tool registration)
# ---------------------------------------------------------------------------

class ToolRegistry:
    """Tool registry for managing ADK function tools.

    Provides get_all_tools() for ADK Agent.tools registration.
    """

    def __init__(self) -> None:
        self._tools: dict[str, Any] = {}

    def register(self, tool: Any) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Any | None:
        return self._tools.get(name)

    def all_tools(self) -> list[Any]:
        return list(self._tools.values())

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __iter__(self):
        return iter(self._tools.values())

    def get_definitions(self) -> list[dict]:
        return [tool.to_schema() for tool in self._tools.values() if hasattr(tool, "to_schema")]

    @property
    def tool_names(self) -> list[str]:
        return list(self._tools.keys())

    def prepare_call(self, name: str, arguments: dict) -> tuple[Any, dict, str | None]:
        """Locate a registered tool and return (tool, params, error_string).

        Called by AgentRunner._run_tool before execution.  Returns
        ``(tool_instance, arguments, None)`` on success or
        ``(None, arguments, error_message)`` if the tool is not found.
        """
        tool = self._tools.get(name)
        if tool is None:
            return None, arguments, f"Tool '{name}' not found in registry"
        return tool, arguments, None

    async def execute(self, name: str, arguments: dict) -> Any:
        """Fallback execution path used by the runner when prepare_call is absent.

        Looks up the tool by *name* and calls ``tool.execute(**arguments)``.
        """
        tool = self._tools.get(name)
        if tool is None:
            return {"error": f"Tool '{name}' not found"}
        return await tool.execute(**arguments)


def get_all_tools(config: Any = None) -> list[Callable]:
    """Return a list of ADK function tools based on configuration.

    Args:
        config: Optional config object. If None, returns all tools.

    Returns:
        A list of callable functions ready for ADK's Agent(tools=[...]).
    """
    from adkbot.agent.tools.cron import schedule_task
    from adkbot.agent.tools.filesystem import (
        edit_file,
        list_directory,
        read_file,
        write_file,
    )
    from adkbot.agent.tools.message import send_message
    from adkbot.agent.tools.shell import execute_command
    from adkbot.agent.tools.spawn import spawn_agent
    from adkbot.agent.tools.web import web_fetch, web_search

    tools: list[Callable] = [
        # Always available
        web_search,
        web_fetch,
        read_file,
        write_file,
        edit_file,
        list_directory,
        send_message,
    ]

    # Shell execution (can be disabled via config)
    exec_enabled = True
    if config:
        try:
            exec_enabled = config.tools.exec.enable
        except (AttributeError, TypeError):
            exec_enabled = True

    if exec_enabled:
        tools.append(execute_command)

    # Cron scheduling (available if cron service is configured)
    tools.append(schedule_task)

    # Sub-agent spawning
    tools.append(spawn_agent)

    # MCP tools (dynamically loaded from MCP servers)
    if config:
        mcp_tools = _load_mcp_tools(config)
        tools.extend(mcp_tools)

    logger.info("Loaded {} tools", len(tools))
    return tools


def _load_mcp_tools(config: Any) -> list[Callable]:
    """Load MCP tools from configured MCP servers.

    MCP tools are dynamically registered based on config.tools.mcp.servers.
    """
    try:
        mcp_servers = config.tools.mcp.servers
        if not mcp_servers:
            return []

        from adkbot.agent.tools.mcp import load_mcp_tools
        return load_mcp_tools(mcp_servers)
    except (AttributeError, ImportError) as e:
        logger.debug("MCP tools not available: {}", e)
        return []
