"""
ADK-native agent loop that uses google.adk.runners.Runner.

This module provides a modern ADK-compliant agent execution loop that:
- Uses ADK's Runner for LLM orchestration
- Preserves message bus integration for channel handling
- Supports streaming responses via callbacks
- Integrates with ADK SessionService and MemoryService
- Includes self-healing retries for LLM tool hallucinations

Reference: https://google.github.io/adk-docs/runtime/
"""

from __future__ import annotations

import asyncio
import uuid
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any, Callable, Coroutine

from loguru import logger

try:
    from google.adk.agents import LlmAgent
    from google.adk.memory import InMemoryMemoryService
    from google.adk.models.lite_llm import LiteLlm
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.adk.tools.base_tool import BaseTool
    from google.adk.tools.tool_context import ToolContext
    from google.genai import types

    ADK_AVAILABLE = True
except ImportError:
    ADK_AVAILABLE = False
    LlmAgent = Any  # type: ignore
    LiteLlm = Any  # type: ignore
    Runner = Any  # type: ignore
    InMemorySessionService = Any  # type: ignore
    InMemoryMemoryService = Any  # type: ignore
    BaseTool = Any  # type: ignore
    ToolContext = Any  # type: ignore

from adkbot.agent.callbacks import (
    after_agent_callback,
    after_model_callback,
    after_tool_callback,
    before_agent_callback,
    before_model_callback,
    before_tool_callback,
)
from adkbot.agent.context import ContextBuilder
from adkbot.agent.memory import AdkMemoryConsolidator, MemoryStore
from adkbot.agent.subagent import AdkSubagentManager
from adkbot.agent.tools.registry import get_all_tools
from adkbot.bus.events import InboundMessage, OutboundMessage
from adkbot.bus.queue import MessageBus
from adkbot.config.schema import AgentDefaults, Config
from adkbot.session.manager import SessionManager


class AdkAgentLoop:
    """
    ADK-native agent loop using google.adk.runners.Runner.

    This class replaces the legacy AgentLoop with ADK's Runner pattern while
    preserving message bus integration, channel handling, and progress callbacks.

    Key differences from legacy AgentLoop:
    - Uses ADK's Runner for LLM orchestration (not custom AgentRunner)
    - Uses ADK's SessionService for state management
    - Uses ADK's callbacks instead of AgentHook
    - Tools are plain functions (not Tool classes)
    - Incorporates self-healing retry logic for tool hallucinations

    Example:
        >>> loop = AdkAgentLoop(
        ...     bus=MessageBus(),
        ...     workspace=Path("./workspace"),
        ...     model="gemini/gemini-3.1-pro-preview",
        ...     api_key="your-api-key",
        ... )
        >>> async for event in loop.process_message(message):
        ...     print(event)
    """

    APP_NAME = "adkbot"

    def __init__(
        self,
        bus: MessageBus,
        workspace: Path,
        config: Config | None = None,
        model: str = "nvidia_nim/nvidia/nemotron-3-super-120b-a12b",
        api_key: str | None = None,
        api_base: str | None = None,
        session_service: InMemorySessionService | None = None,
        memory_service: InMemoryMemoryService | None = None,
        timezone: str | None = None,
        restrict_to_workspace: bool = False,
        on_progress: Callable[..., Coroutine[None, None, None]] | None = None,
        on_stream: Callable[[str], Coroutine[None, None, None]] | None = None,
    ):
        """
        Initialize the ADK agent loop.

        Args:
            bus: Message bus for channel communication
            workspace: Path to the workspace directory
            config: Optional configuration object (takes precedence over individual args)
            model: LiteLLM model string (e.g., "gemini/gemini-3.1-pro-preview", "openrouter/openai/gpt-4")
            api_key: API key for the model provider
            api_base: Optional API base URL for custom endpoints
            session_service: Optional ADK session service (defaults to InMemorySessionService)
            memory_service: Optional ADK memory service (defaults to InMemoryMemoryService)
            timezone: Timezone for timestamp generation
            restrict_to_workspace: Whether to restrict file operations to workspace
            on_progress: Optional async callback for progress updates
            on_stream: Optional async callback for streaming text chunks
        """
        if not ADK_AVAILABLE:
            raise ImportError("Google ADK is not installed. Install with: pip install google-adk")

        # Apply config if provided
        if config:
            defaults = config.agents.defaults
            model = config.get_effective_model()
            api_key = config.get_effective_api_key(model)
            api_base = config.get_api_base(model)
            timezone = getattr(defaults, "timezone", timezone)

        self.bus = bus
        self.workspace = workspace
        self.model = model
        self.api_key = api_key
        self.api_base = api_base
        self.timezone = timezone
        self.restrict_to_workspace = restrict_to_workspace

        # Callbacks
        self._on_progress = on_progress
        self._on_stream = on_stream
        self._on_stream_end: Callable[..., Coroutine[None, None, None]] | None = None

        # ADK services
        self.session_service = session_service or InMemorySessionService()
        self.memory_service = memory_service or InMemoryMemoryService()

        # Context builder for instruction generation
        self.context = ContextBuilder(workspace, timezone=timezone)

        # Session manager for legacy JSONL persistence
        self.sessions = SessionManager(workspace)

        # Memory store for long-term memory
        self.memory_store = MemoryStore(workspace)

        # Memory consolidator
        self.memory_consolidator = AdkMemoryConsolidator(
            workspace=workspace,
            model=model,
            api_key=api_key,
            api_base=api_base,
        )

        # Subagent manager
        self.subagents = AdkSubagentManager(
            workspace=workspace,
            bus=bus,
            model=model,
            api_key=api_key,
            api_base=api_base,
        )

        # State
        self._running = False
        self._active_sessions: dict[str, str] = {}  # session_key -> ADK session_id
        self._session_locks: dict[str, asyncio.Lock] = {}
        self._background_tasks: list[asyncio.Task] = []

        # MCP connection state
        self._mcp_stack: AsyncExitStack | None = None
        self._mcp_connected = False

        # Store config for backward compatibility
        self._config = config
        if config:
            self._channels_config = getattr(config, "channels", None)
        else:
            self._channels_config = None

        # Create the ADK agent
        self._setup_agent()

        # Create the Runner with auto_create_session enabled!
        self.runner = Runner(
            agent=self.agent,
            app_name=self.APP_NAME,
            session_service=self.session_service,
            memory_service=self.memory_service,
            auto_create_session=True,
        )

        logger.info(
            "AdkAgentLoop initialized | model={} | workspace={}",
            model,
            workspace,
        )

    def _setup_agent(self) -> None:
        """Create the ADK LlmAgent with proper configuration."""
        # Build instruction from context
        instruction = self.context.build_adk_instruction()

        # Get tools as ADK-compatible functions
        tools = self._get_tools()

        # Create LiteLLM model wrapper
        litellm = LiteLlm(
            model=self.model,
            api_key=self.api_key,
            api_base=self.api_base,
        )

        # Create the LlmAgent
        self.agent = LlmAgent(
            name="adkbot",
            model=litellm,
            instruction=instruction,
            description="ADKBot - A helpful AI assistant powered by Google ADK",
            tools=tools,
            # ADK callbacks
            before_agent_callback=self._before_agent_callback,
            after_agent_callback=self._after_agent_callback,
            before_model_callback=self._before_model_callback,
            after_model_callback=self._after_model_callback,
            before_tool_callback=self._before_tool_callback,
            after_tool_callback=self._after_tool_callback,
        )

        logger.debug("ADK agent created with {} tools", len(tools))

    def _get_tools(self) -> list[Callable]:
        """Get tools as ADK-compatible functions."""
        return get_all_tools()

    # -------------------------------------------------------------------------
    # ADK Callback wrappers (Fully kwarg-safe to prevent crash bugs)
    # -------------------------------------------------------------------------

    async def _before_agent_callback(self, *args, **kwargs) -> Any:
        """Wrapper for ADK before_agent_callback."""
        if self._on_progress:
            try:
                await self._on_progress("agent_start")
            except Exception as e:
                logger.debug("Progress callback error: {}", e)
        return before_agent_callback(*args, **kwargs)

    async def _after_agent_callback(self, *args, **kwargs) -> Any:
        """Wrapper for ADK after_agent_callback."""
        if self._on_progress:
            try:
                await self._on_progress("agent_end")
            except Exception as e:
                logger.debug("Progress callback error: {}", e)
        return after_agent_callback(*args, **kwargs)

    async def _before_model_callback(self, *args, **kwargs) -> Any:
        """Wrapper for ADK before_model_callback."""
        return before_model_callback(*args, **kwargs)

    async def _after_model_callback(self, *args, **kwargs) -> Any:
        """Wrapper for ADK after_model_callback."""
        return after_model_callback(*args, **kwargs)

    async def _before_tool_callback(self, *args, **kwargs) -> Any:
        """Wrapper for ADK before_tool_callback."""
        return before_tool_callback(*args, **kwargs)

    async def _after_tool_callback(self, *args, **kwargs) -> Any:
        """Wrapper for ADK after_tool_callback."""
        return after_tool_callback(*args, **kwargs)

    # -------------------------------------------------------------------------
    # Message processing
    # -------------------------------------------------------------------------

    async def process_message(
        self,
        message: InboundMessage,
        on_progress: Callable[..., Coroutine[None, None, None]] | None = None,
        on_stream: Callable[[str], Coroutine[None, None, None]] | None = None,
        on_stream_end: Callable[..., Coroutine[None, None, None]] | None = None,
    ) -> str:
        """
        Process an incoming message using ADK Runner. Includes self-healing for hallucinations.

        Args:
            message: The inbound message to process
            on_progress: Optional async callback for progress updates
            on_stream: Optional async callback for streaming text chunks
            on_stream_end: Optional async callback when streaming ends

        Returns:
            The final response text from the agent
        """
        # Update callbacks
        self._on_progress = on_progress or self._on_progress
        self._on_stream = on_stream or self._on_stream
        self._on_stream_end = on_stream_end or self._on_stream_end

        # Generate session identifiers
        session_key = f"{message.channel}:{message.chat_id}"
        user_id = message.sender_id or "default_user"
        session_id = self._active_sessions.get(session_key)

        if not session_id:
            session_id = str(uuid.uuid4())
            self._active_sessions[session_key] = session_id

        # Get or create session
        session = await self._get_or_create_session(
            user_id=user_id,
            session_id=session_id,
            session_key=session_key,
        )

        # Build user content
        user_content = types.Content(
            role="user",
            parts=[types.Part(text=message.content)],
        )

        # Add media if present
        if message.media:
            for media_path in message.media:
                user_content.parts.append(types.Part(text=f"\n[Media: {media_path}]"))

        # Track response
        final_response = ""
        streaming_parts: list[str] = []

        logger.debug(
            "Processing message | channel={} | chat_id={} | user={}",
            message.channel,
            message.chat_id,
            user_id,
        )

        try:
            max_retries = 3
            for attempt in range(max_retries):
                turn_failed_due_to_hallucination = False
                
                try:
                    # Run agent and collect events
                    async for event in self.runner.run_async(
                        user_id=user_id,
                        session_id=session_id,
                        new_message=user_content,
                    ):
                        # Handle streaming text
                        if event.content and event.content.parts:
                            for part in event.content.parts:
                                if hasattr(part, "text") and part.text:
                                    streaming_parts.append(part.text)
                                    if self._on_stream:
                                        try:
                                            await self._on_stream(part.text)
                                        except Exception as e:
                                            logger.debug("Stream callback error: {}", e)

                        # Check for final response
                        if event.is_final_response():
                            if event.content and event.content.parts:
                                for part in event.content.parts:
                                    if hasattr(part, "text") and part.text:
                                        final_response = part.text

                except ValueError as ve:
                    error_str = str(ve)
                    # Self-Healing: Intercept ADK throwing a Tool Not Found ValueError
                    if "Tool" in error_str and "not found" in error_str:
                        logger.warning(
                            "LLM hallucinated a tool (attempt {}/{}). Injecting correction. Error: {}", 
                            attempt + 1, max_retries, error_str.split('\n')[0]
                        )
                        # We create a new user message containing the error to feed back into the session
                        user_content = types.Content(
                            role="user",
                            parts=[types.Part(text=f"SYSTEM NOTIFICATION: {error_str}\n\nPlease correct your tool call name. If you simply wanted to reply to the user, DO NOT call any tool—just output your message as plain text.")]
                        )
                        turn_failed_due_to_hallucination = True
                        
                        if attempt == max_retries - 1:
                            raise  # We gave it 3 tries, it's still hallucinating, let the user see the error
                    else:
                        raise  # It was some other ValueError, re-raise it immediately

                if not turn_failed_due_to_hallucination:
                    break  # Success! The generator completed normally without a hallucination

            # Notify stream end
            if self._on_stream_end and streaming_parts:
                try:
                    await self._on_stream_end(
                        "".join(streaming_parts),
                        channel=message.channel,
                        chat_id=message.chat_id,
                    )
                except Exception as e:
                    logger.debug("Stream end callback error: {}", e)

            # Save session state
            await self._save_session_state(session_key)

            logger.debug(
                "Message processed | response_len={} | channel={}",
                len(final_response),
                message.channel,
            )

        except Exception as e:
            logger.exception("Error processing message: {}", e)
            final_response = f"Error processing message: {e}"

        return final_response

    async def _get_or_create_session(
        self,
        user_id: str,
        session_id: str,
        session_key: str,
    ) -> Any:
        """Get or create an ADK session."""
        try:
            # Try to get existing session
            session = await self.session_service.get_session(
                app_name=self.APP_NAME,
                user_id=user_id,
                session_id=session_id,
            )
            return session
        except Exception:
            # Create new session with initial state
            initial_state = self._build_initial_state(session_key)
            session = await self.session_service.create_session(
                app_name=self.APP_NAME,
                user_id=user_id,
                session_id=session_id,
                state=initial_state,
            )
            return session

    def _build_initial_state(self, session_key: str) -> dict[str, Any]:
        """Build initial session state."""
        return {
            "session_key": session_key,
            "workspace": str(self.workspace),
            "timezone": self.timezone or "UTC",
        }

    async def _save_session_state(self, session_key: str) -> None:
        """Save session state to persistent storage."""
        # The ADK session service handles persistence automatically
        # We just need to ensure any legacy state is synced
        pass

    # -------------------------------------------------------------------------
    # Main loop
    # -------------------------------------------------------------------------

    async def run(self) -> None:
        """
        Main loop: listen to bus and process messages.

        This method starts the agent loop, subscribing to inbound messages
        from the message bus and processing them through the ADK Runner.
        """
        self._running = True
        logger.info("ADK Agent Loop started | model={} | workspace={}", self.model, self.workspace)

        try:
            async for message in self.bus.subscribe_inbound():
                if not self._running:
                    break
                try:
                    # Process the message
                    response = await self.process_message(message)

                    # Send response if we got one
                    if response:
                        outbound = OutboundMessage(
                            channel=message.channel,
                            chat_id=message.chat_id,
                            content=response,
                            reply_to=message.metadata.get("message_id"),
                        )
                        await self.bus.publish_outbound(outbound)
                except Exception as e:
                    logger.exception("Error processing message: {}", e)
                    # Send error notification
                    error_msg = f"An error occurred: {e}"
                    outbound = OutboundMessage(
                        channel=message.channel,
                        chat_id=message.chat_id,
                        content=error_msg,
                        reply_to=message.metadata.get("message_id"),
                    )
                    await self.bus.publish_outbound(outbound)
        except asyncio.CancelledError:
            logger.info("Agent loop cancelled")
        except Exception as e:
            logger.exception("Agent loop error: {}", e)
        finally:
            self._running = False
            logger.info("ADK Agent Loop stopped")

    def stop(self) -> None:
        """Stop the agent loop."""
        self._running = False
        logger.info("Stopping ADK Agent Loop")

    # -------------------------------------------------------------------------
    # Backward compatibility methods (for legacy AgentLoop interface)
    # -------------------------------------------------------------------------

    async def _connect_mcp(self) -> None:
        """Connect to MCP servers (backward compatibility stub).

        Note: MCP connection is handled differently in ADK mode.
        This method exists for backward compatibility with legacy AgentLoop.
        """
        if self._mcp_connected or not hasattr(self, "_mcp_servers"):
            return
        # MCP connection would be handled via ADK tools if needed
        logger.debug("MCP connection requested (ADK mode - stub)")
        self._mcp_connected = True

    async def close_mcp(self) -> None:
        """Close MCP connections (backward compatibility stub)."""
        if self._mcp_stack:
            try:
                await self._mcp_stack.aclose()
            except Exception:
                pass
        self._mcp_stack = None
        self._mcp_connected = False
        logger.debug("MCP connections closed")

    @property
    def tools(self):
        """Access to tools registry (backward compatibility stub).

        Note: ADK uses plain function tools, not a registry.
        This property exists for backward compatibility with legacy AgentLoop.
        """

        # Return a minimal compatibility shim
        class _ToolsShim:
            def get(self, name: str):
                return None

        return _ToolsShim()

    @property
    def channels_config(self):
        """Channels configuration (backward compatibility stub)."""
        return getattr(self, "_channels_config", None)

    async def process_direct(
        self,
        content: str,
        session_key: str | None = None,
        channel: str = "cli",
        chat_id: str = "direct",
        sender_id: str = "user",
        media: list[str] | None = None,
        on_progress: Callable[..., Coroutine[None, None, None]] | None = None,
        on_stream: Callable[[str], Coroutine[None, None, None]] | None = None,
        on_stream_end: Callable[..., Coroutine[None, None, None]] | None = None,
    ) -> Any:
        """
        Process a direct message without going through the bus.
        Useful for CLI mode and testing.

        Args:
            content: The message content
            session_key: Optional session key (for backward compatibility)
            channel: Channel identifier (default: "cli")
            chat_id: Chat identifier (default: "direct")
            sender_id: Sender identifier (default: "user")
            media: Optional list of media file paths
            on_progress: Optional async callback for progress updates
            on_stream: Optional async callback for streaming text
            on_stream_end: Optional async callback when streaming ends

        Returns:
            The agent's response as an object with .content and .metadata
        """
        message = InboundMessage(
            channel=channel,
            sender_id=sender_id,
            chat_id=chat_id,
            content=content,
            media=media or [],
        )
        response_text = await self.process_message(
            message,
            on_progress=on_progress,
            on_stream=on_stream,
            on_stream_end=on_stream_end,
        )

        # Return a response object similar to legacy AgentLoop
        class _Response:
            def __init__(self, content: str):
                self.content = content
                self.metadata = {}

        return _Response(response_text)

    def get_running_status(self) -> dict[str, Any]:
        """Get the current running status of the agent loop."""
        return {
            "running": self._running,
            "model": self.model,
            "workspace": str(self.workspace),
            "active_sessions": len(self._active_sessions),
            "subagents_running": self.subagents.get_running_count(),
        }


# -------------------------------------------------------------------------
# Factory function for backward compatibility
# -------------------------------------------------------------------------


def create_adk_loop(
    bus: MessageBus,
    workspace: Path,
    config: Config | None = None,
    **kwargs,
) -> AdkAgentLoop:
    """
    Factory function to create an AdkAgentLoop with sensible defaults.

    This function provides backward compatibility with the old AgentLoop
    creation pattern.

    Args:
        bus: Message bus for communication
        workspace: Path to workspace directory
        config: Optional configuration object
        **kwargs: Additional arguments passed to AdkAgentLoop

    Returns:
        Configured AdkAgentLoop instance
    """
    return AdkAgentLoop(
        bus=bus,
        workspace=workspace,
        config=config,
        **kwargs,
    )
