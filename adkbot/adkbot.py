"""High-level programmatic interface to ADKBot, powered by Google ADK."""

from __future__ import annotations

import asyncio
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService, InMemorySessionService
from google.genai import types
from loguru import logger


@dataclass(slots=True)
class RunResult:
    """Result of a single agent run."""

    content: str
    tools_used: list[str] = field(default_factory=list)
    events: list[Any] = field(default_factory=list)


class AdkBot:
    """Programmatic facade for running the ADKBot agent.

    Powered by Google ADK with LiteLLM for multi-provider model support.

    Usage::

        bot = AdkBot.from_config()
        result = await bot.run("Summarize this repo")
        print(result.content)
    """

    APP_NAME = "adkbot"

    def __init__(
        self,
        model: Any,
        tools: list | None = None,
        instruction: str = "",
        session_service: Any = None,
        workspace: Path | None = None,
    ) -> None:
        self.model = model
        self.workspace = workspace or Path("~/.adkbot/workspace").expanduser()
        self._tools = tools or []
        self._instruction = instruction

        self.session_service = session_service or InMemorySessionService()

        self.root_agent = self._create_root_agent()
        self.runner = Runner(
            agent=self.root_agent,
            app_name=self.APP_NAME,
            session_service=self.session_service,
            auto_create_session=True,
        )

    def _create_root_agent(self) -> Agent:
        """Create the ADK root agent with callbacks."""
        from adkbot.agent.callbacks import (
            after_agent_callback,
            after_model_callback,
            after_tool_callback,
            before_agent_callback,
            before_model_callback,
            before_tool_callback,
        )

        return Agent(
            name="adkbot",
            model=self.model,
            description="ADKBot — A powerful multi-model AI assistant",
            instruction=self._instruction,
            tools=self._tools,
            before_agent_callback=before_agent_callback,
            after_agent_callback=after_agent_callback,
            before_model_callback=before_model_callback,
            after_model_callback=after_model_callback,
            before_tool_callback=before_tool_callback,
            after_tool_callback=after_tool_callback,
        )

    @classmethod
    def from_config(
        cls,
        config_path: str | Path | None = None,
        *,
        workspace: str | Path | None = None,
    ) -> AdkBot:
        """Create an AdkBot instance from a config file.

        Args:
            config_path: Path to ``config.json``.  Defaults to
                ``~/.adkbot/config.json``.
            workspace: Override the workspace directory from config.
        """
        from adkbot.config.loader import load_config

        # Load .env for API keys (from working dir and ~/.adkbot/.env)
        load_dotenv()  # working directory .env
        from adkbot.config.paths import get_data_dir
        adkbot_env = get_data_dir() / ".env"
        if adkbot_env.exists():
            load_dotenv(adkbot_env, override=False)  # don't override existing vars

        resolved: Path | None = None
        if config_path is not None:
            resolved = Path(config_path).expanduser().resolve()
            if not resolved.exists():
                raise FileNotFoundError(f"Config not found: {resolved}")

        config = load_config(resolved)
        if workspace is not None:
            config.agents.defaults.workspace = str(Path(workspace).expanduser().resolve())

        # Build LiteLLM model from config
        model = _create_litellm_model(config)

        # Build instruction from context builder
        from adkbot.agent.context import ContextBuilder

        ctx = ContextBuilder(
            config.workspace_path,
            timezone=config.agents.defaults.timezone,
        )
        instruction = ctx.build_system_prompt()

        # Load tools
        tools = _load_tools(config)

        # Build session service
        session_service = _create_session_service(config)

        ws = Path(workspace).expanduser() if workspace else config.workspace_path

        return cls(
            model=model,
            tools=tools,
            instruction=instruction,
            session_service=session_service,
            workspace=ws,
        )

    async def run(
        self,
        message: str,
        *,
        user_id: str = "default_user",
        session_id: str | None = None,
    ) -> RunResult:
        """Run the agent once and return the result.

        Args:
            message: The user message to process.
            user_id: User identifier for session isolation.
            session_id: Session identifier. Auto-generated if not provided.
        """
        if session_id is None:
            session_id = str(uuid.uuid4())

        # Ensure session exists to prevent "Session not found" ADK error
        try:
            await self.session_service.get_session(
                app_name=self.APP_NAME, user_id=user_id, session_id=session_id
            )
        except Exception:
            await self.session_service.create_session(
                app_name=self.APP_NAME, user_id=user_id, session_id=session_id, state={}
            )

        new_message = types.Content(
            role="user",
            parts=[types.Part(text=message)],
        )

        final_text = ""
        tools_used: list[str] = []
        events: list[Any] = []

        # Runner.run_async handles session auto-creation via auto_create_session
        async for event in self.runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=new_message,
        ):
            events.append(event)
            if event.is_final_response():
                if event.content and event.content.parts:
                    final_text = event.content.parts[0].text or ""

        return RunResult(
            content=final_text,
            tools_used=tools_used,
            events=events,
        )

    def run_sync(
        self,
        message: str,
        *,
        user_id: str = "default_user",
        session_id: str | None = None,
    ) -> RunResult:
        """Synchronous wrapper around run() for CLI usage.

        Uses ADK Runner's built-in sync run() which handles
        the asyncio event loop internally.
        """
        if session_id is None:
            session_id = str(uuid.uuid4())

        # Ensure session exists to prevent "Session not found" ADK error
        async def _ensure_session():
            try:
                await self.session_service.get_session(
                    app_name=self.APP_NAME, user_id=user_id, session_id=session_id
                )
            except Exception:
                await self.session_service.create_session(
                    app_name=self.APP_NAME, user_id=user_id, session_id=session_id, state={}
                )

        try:
            asyncio.run(_ensure_session())
        except RuntimeError:
            pass # Fallback if an event loop is already running

        new_message = types.Content(
            role="user",
            parts=[types.Part(text=message)],
        )

        final_text = ""
        tools_used: list[str] = []
        events: list[Any] = []

        for event in self.runner.run(
            user_id=user_id,
            session_id=session_id,
            new_message=new_message,
        ):
            events.append(event)
            if event.is_final_response():
                if event.content and event.content.parts:
                    final_text = event.content.parts[0].text or ""

        return RunResult(
            content=final_text,
            tools_used=tools_used,
            events=events,
        )


def _create_litellm_model(config: Any) -> Any:
    """Create the LiteLLM model adapter from config.

    Maps the config's model to a LiteLLM model string.
    Supports: Gemini (native), OpenRouter, OpenAI, Anthropic, DeepSeek, Groq, Ollama,
    and any LiteLLM-supported provider.

    The model string format determines the provider:
    - "gemini/gemini-3.1-pro-preview" -> Gemini (native)
    - "openrouter/openai/gpt-4" -> OpenRouter
    - "anthropic/claude-3-opus" -> Anthropic
    - etc.
    """
    defaults = config.agents.defaults
    model_name = defaults.model

    # Determine API key (from config or environment)
    api_key = None
    # Check if there's a provider-specific config in the old format
    provider_cfg = getattr(config, "providers", None)
    if provider_cfg and hasattr(provider_cfg, "__getitem__"):
        # Try to get provider-specific config
        pass

    # Try environment variables based on model prefix
    # Detect provider from model string prefix
    model_lower = model_name.lower()
    if model_lower.startswith("openrouter/"):
        api_key = os.environ.get("OPENROUTER_API_KEY")
    elif model_lower.startswith("openai/"):
        api_key = os.environ.get("OPENAI_API_KEY")
    elif model_lower.startswith("anthropic/"):
        api_key = os.environ.get("ANTHROPIC_API_KEY")
    elif model_lower.startswith("deepseek/"):
        api_key = os.environ.get("DEEPSEEK_API_KEY")
    elif model_lower.startswith("groq/"):
        api_key = os.environ.get("GROQ_API_KEY")
    elif model_lower.startswith("gemini") or model_lower.startswith("models/gemini"):
        api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")

    # Fallback to Google API key if not set
    if not api_key:
        api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")

    # Use model string directly (LiteLLM format)
    litellm_model = model_name

    # Determine API base (for custom endpoints, Ollama, vLLM, etc.)
    api_base = getattr(defaults, "api_base", None)

    # For native Gemini models, use ADK's native model support (not LiteLLM)
    if _is_native_gemini(model_name):
        logger.info(f"Using native Gemini model: {model_name}")
        return model_name  # ADK natively supports Gemini model strings

    logger.info(f"Using LiteLLM model: {litellm_model}")

    kwargs: dict[str, Any] = {"model": litellm_model}
    if api_key:
        kwargs["api_key"] = api_key
    if api_base:
        kwargs["api_base"] = api_base
    if defaults.fallbacks:
        kwargs["fallbacks"] = defaults.fallbacks
    if defaults.reasoning_effort:
        kwargs["reasoning_effort"] = defaults.reasoning_effort

    return LiteLlm(**kwargs)


def _is_native_gemini(model_name: str) -> bool:
    """Check if the model should use ADK's native Gemini support."""
    model_lower = model_name.lower()
    if model_lower.startswith("gemini"):
        return True
    if model_lower.startswith("models/gemini"):
        return True
    return False


def _load_tools(config: Any) -> list:
    """Load ADK function tools based on config.

    Returns a list of plain Python functions that conform to ADK's
    function tool pattern (functions with docstrings and type annotations).
    """
    from adkbot.agent.tools.registry import get_all_tools

    return get_all_tools(config)


def _create_session_service(config: Any) -> Any:
    """Create the ADK session service from config.

    Uses DatabaseSessionService with SQLite for persistence by default.
    Falls back to InMemorySessionService if DB setup fails.
    """
    try:
        db_path = Path("~/.adkbot/sessions.db").expanduser()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        db_url = f"sqlite:///{db_path}"
        service = DatabaseSessionService(db_url=db_url)
        logger.info(f"Using persistent session storage: {db_url}")
        return service
    except Exception as e:
        logger.warning(f"Failed to create database session service: {e}")
        logger.info("Falling back to in-memory session storage")
        return InMemorySessionService()