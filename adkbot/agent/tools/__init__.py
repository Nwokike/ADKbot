"""ADK function tools for ADKBot.

All tools are plain Python functions with docstrings and type annotations.
ADK auto-wraps them via FunctionTool when passed to Agent(tools=[...]).
"""

from adkbot.agent.tools.cron import schedule_task
from adkbot.agent.tools.filesystem import edit_file, list_directory, read_file, write_file
from adkbot.agent.tools.message import send_message
from adkbot.agent.tools.shell import execute_command
from adkbot.agent.tools.spawn import spawn_agent
from adkbot.agent.tools.web import web_fetch, web_search

__all__ = [
    # Web
    "web_search",
    "web_fetch",
    # File system
    "read_file",
    "write_file",
    "edit_file",
    "list_directory",
    # Shell
    "execute_command",
    # Messaging
    "send_message",
    # Cron
    "schedule_task",
    # Sub-agents
    "spawn_agent",
]
