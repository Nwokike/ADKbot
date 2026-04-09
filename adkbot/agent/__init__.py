"""Agent core module — ADK-powered agent components."""

from adkbot.agent.callbacks import (
    after_agent_callback,
    after_model_callback,
    after_tool_callback,
    before_agent_callback,
    before_model_callback,
    before_tool_callback,
)
from adkbot.agent.context import ContextBuilder
from adkbot.agent.memory import MemoryStore
from adkbot.agent.skills import SkillsLoader

# ADK-native components (with graceful fallback)
try:
    from adkbot.agent.adk_loop import AdkAgentLoop, create_adk_loop
    from adkbot.agent.subagent import AdkSubagentManager

    _ADK_AVAILABLE = True
except ImportError:
    _ADK_AVAILABLE = False
    AdkAgentLoop = None  # type: ignore
    create_adk_loop = None  # type: ignore
    AdkSubagentManager = None  # type: ignore

__all__ = [
    # Context and skills
    "ContextBuilder",
    "MemoryStore",
    "SkillsLoader",
    # ADK callbacks
    "before_agent_callback",
    "after_agent_callback",
    "before_model_callback",
    "after_model_callback",
    "before_tool_callback",
    "after_tool_callback",
    # ADK-native components
    "AdkAgentLoop",
    "AdkSubagentManager",
    "create_adk_loop",
]
