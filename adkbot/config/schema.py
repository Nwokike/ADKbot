"""Configuration schema using Pydantic.

Defines the configuration schema for ADKBot. Uses LiteLLM model strings
for universal multi-provider support (e.g. "gemini-2.0-flash",
"nvidia_nim/moonshot/kimi-k2-instruct", "groq/llama-3.3-70b-versatile").
"""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from pydantic_settings import BaseSettings


class Base(BaseModel):
    """Base model that accepts both camelCase and snake_case keys."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ChannelsConfig(Base):
    """Configuration for chat channels.

    Built-in and plugin channel configs are stored as extra fields (dicts).
    Each channel parses its own config in __init__.
    Per-channel "streaming": true enables streaming output (requires send_delta impl).
    """

    model_config = ConfigDict(extra="allow")

    send_progress: bool = True  # stream agent's text progress to the channel
    send_tool_hints: bool = False  # stream tool-call hints (e.g. read_file("…"))
    send_max_retries: int = Field(
        default=3, ge=0, le=10
    )  # Max delivery attempts (initial send included)


class ModelConfig(Base):
    """Simplified model configuration using LiteLLM model strings.

    LiteLLM model strings follow the format: "provider/model-name"
    Examples:
        - "gemini-2.0-flash" (native Gemini, uses GOOGLE_API_KEY)
        - "openrouter/openai/gpt-4" (uses OPENROUTER_API_KEY)
        - "anthropic/claude-3-opus-20240229" (uses ANTHROPIC_API_KEY)
        - "openai/gpt-4" (uses OPENAI_API_KEY)
        - "deepseek/deepseek-chat" (uses DEEPSEEK_API_KEY)
        - "groq/llama-3.1-70b-versatile" (uses GROQ_API_KEY)
        - "ollama/llama3.2" (local Ollama)

    API keys can be provided via:
    1. This config (api_key field)
    2. Environment variables (provider-specific, e.g., OPENAI_API_KEY)
    3. .env file

    See: https://docs.litellm.ai/docs/providers for all supported providers
    """

    model: str = Field(
        default="gemini-2.0-flash",
        description="LiteLLM model string (e.g., 'gemini-2.0-flash', 'openrouter/openai/gpt-4')",
    )
    api_key: str = Field(
        default="",
        description="API key for the model provider. If empty, uses environment variables.",
    )
    api_base: str | None = Field(
        default=None,
        description="Custom API base URL (optional, for self-hosted or custom endpoints)",
    )
    extra_headers: dict[str, str] | None = Field(
        default=None,
        description="Custom headers for API requests (e.g., APP-Code for some gateways)",
    )


class AgentDefaults(Base):
    """Default agent configuration."""

    workspace: str = "~/.adkbot/workspace"
    model: str = "gemini-2.0-flash"  # Default to Gemini (free tier available)
    max_tokens: int = 8192
    context_window_tokens: int = 128_000  # Most modern models support 128k+
    context_block_limit: int | None = None
    temperature: float = 0.1
    max_tool_iterations: int = 15  # Reduced from 200, ADK handles this better
    max_tool_result_chars: int = 50_000  # Increased for better tool results
    provider_retry_mode: Literal["standard", "persistent"] = "standard"
    reasoning_effort: str | None = None  # low / medium / high - enables LLM thinking mode
    fallbacks: list[str] | None = None  # LiteLLM fallback models
    timezone: str = "UTC"  # IANA timezone, e.g. "Asia/Shanghai", "America/New_York"


class AgentsConfig(Base):
    """Agent configuration."""

    defaults: AgentDefaults = Field(default_factory=AgentDefaults)


class HeartbeatConfig(Base):
    """Heartbeat service configuration."""

    enabled: bool = True
    interval_s: int = 30 * 60  # 30 minutes
    keep_recent_messages: int = 8


class ApiConfig(Base):
    """OpenAI-compatible API server configuration."""

    host: str = "127.0.0.1"  # Safer default: local-only bind.
    port: int = 8900
    timeout: float = 120.0  # Per-request timeout in seconds.


class GatewayConfig(Base):
    """Gateway/server configuration."""

    host: str = "0.0.0.0"
    port: int = 18790
    heartbeat: HeartbeatConfig = Field(default_factory=HeartbeatConfig)


class WebSearchConfig(Base):
    """Web search tool configuration."""

    provider: str = "brave"  # brave, tavily, duckduckgo, searxng, jina
    api_key: str = ""
    base_url: str = ""  # SearXNG base URL
    max_results: int = 5


class WebToolsConfig(Base):
    """Web tools configuration."""

    proxy: str | None = (
        None  # HTTP/SOCKS5 proxy URL, e.g. "http://127.0.0.1:7890" or "socks5://127.0.0.1:1080"
    )
    search: WebSearchConfig = Field(default_factory=WebSearchConfig)


class ExecToolConfig(Base):
    """Shell exec tool configuration."""

    enable: bool = True
    timeout: int = 60
    path_append: str = ""


class MCPServerConfig(Base):
    """MCP server connection configuration (stdio or HTTP)."""

    type: Literal["stdio", "sse", "streamableHttp"] | None = None  # auto-detected if omitted
    command: str = ""  # Stdio: command to run (e.g. "npx")
    args: list[str] = Field(default_factory=list)  # Stdio: command arguments
    env: dict[str, str] = Field(default_factory=dict)  # Stdio: extra env vars
    url: str = ""  # HTTP/SSE: endpoint URL
    headers: dict[str, str] = Field(default_factory=dict)  # HTTP/SSE: custom headers
    tool_timeout: int = 30  # seconds before a tool call is cancelled
    enabled_tools: list[str] = Field(
        default_factory=lambda: ["*"]
    )  # Only register these tools; accepts raw MCP names or wrapped mcp_<server>_<tool> names; ["*"] = all tools; [] = no tools


class ToolsConfig(Base):
    """Tools configuration."""

    web: WebToolsConfig = Field(default_factory=WebToolsConfig)
    exec: ExecToolConfig = Field(default_factory=ExecToolConfig)
    restrict_to_workspace: bool = False  # If true, restrict all tool access to workspace directory
    mcp_servers: dict[str, MCPServerConfig] = Field(default_factory=dict)


class Config(BaseSettings):
    """Root configuration for ADKBot.

    Configuration can be provided via:
    1. JSON config file (default: ~/.adkbot/config.json)
    2. Environment variables with ADKBOT_ prefix
    3. .env file

    Model Configuration (New LiteLLM Pattern):
        Instead of configuring individual providers, use a LiteLLM model string:
        - "gemini-2.0-flash" - Google Gemini (uses GOOGLE_API_KEY or GEMINI_API_KEY)
        - "openrouter/openai/gpt-4" - Via OpenRouter (uses OPENROUTER_API_KEY)
        - "anthropic/claude-3-opus-20240229" - Anthropic Claude (uses ANTHROPIC_API_KEY)

    Example config.json:
        {
            "agents": {
                "defaults": {
                    "model": "gemini-2.0-flash",
                    "timezone": "America/New_York"
                }
            },
            "channels": {
                "telegram": {
                    "enabled": true,
                    "token": "your-bot-token"
                }
            }
        }
    """

    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    channels: ChannelsConfig = Field(default_factory=ChannelsConfig)
    api: ApiConfig = Field(default_factory=ApiConfig)
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)

    @property
    def workspace_path(self) -> Path:
        """Get expanded workspace path."""
        return Path(self.agents.defaults.workspace).expanduser()

    def get_model_config(self) -> ModelConfig:
        """Get the model configuration for ADK LiteLLM integration.

        Returns:
            ModelConfig with model string, api_key, and api_base for LiteLlm wrapper.
        """
        return ModelConfig(
            model=self.agents.defaults.model,
            api_key="",  # API keys should come from environment variables
            api_base=None,
        )

    def get_effective_model(self) -> str:
        """Get the effective model string for LiteLLM.

        Returns:
            The model string from config (e.g., "gemini-2.0-flash", "openrouter/openai/gpt-4").
        """
        return self.agents.defaults.model

    def get_effective_api_key(self, model: str | None = None) -> str | None:
        """Get the effective API key for the configured model.

        This method checks environment variables based on the model prefix.

        Args:
            model: Optional model string to check. Defaults to configured model.

        Returns:
            API key if found, None otherwise.
        """
        import os

        model = (model or self.agents.defaults.model).lower()

        # Map model prefixes to environment variable names
        # See: https://docs.litellm.ai/docs/providers
        provider_env_map = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "gemini": "GOOGLE_API_KEY",
            "google": "GOOGLE_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "groq": "GROQ_API_KEY",
            "mistral": "MISTRAL_API_KEY",
            "cohere": "COHERE_API_KEY",
            "huggingface": "HUGGINGFACE_API_KEY",
            "azure": "AZURE_OPENAI_API_KEY",
            "vertex_ai": "GOOGLE_APPLICATION_CREDENTIALS",
            "ollama": None,  # Local, no API key needed
            "vllm": None,  # Local, no API key needed
        }

        # Check for provider prefix in model string
        for prefix, env_var in provider_env_map.items():
            if model.startswith(f"{prefix}/") or model == prefix:
                if env_var:
                    return os.environ.get(env_var)
                return None

        # Gemini native (no prefix) uses GOOGLE_API_KEY
        if "gemini" in model:
            return os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")

        # Default: check common environment variables
        for env_var in ["GOOGLE_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"]:
            if os.environ.get(env_var):
                return os.environ.get(env_var)

        return None

    def get_api_base(self, model: str | None = None) -> str | None:
        """Get the API base URL for the model.

        For ADK/LiteLLM, this returns None by default as LiteLLM handles
        provider-specific URLs automatically. Override via environment variables
        if needed (e.g., OPENAI_BASE_URL).

        Args:
            model: Optional model string to check. Defaults to configured model.

        Returns:
            API base URL if configured, None otherwise.
        """
        import os

        model = (model or self.agents.defaults.model).lower()

        # Check for custom API base in environment variables
        # LiteLLM supports provider-specific base URLs via environment
        provider_base_map = {
            "openai": "OPENAI_BASE_URL",
            "anthropic": "ANTHROPIC_BASE_URL",
            "openrouter": "OPENROUTER_BASE_URL",
            "deepseek": "DEEPSEEK_BASE_URL",
            "groq": "GROQ_BASE_URL",
        }

        for prefix, env_var in provider_base_map.items():
            if model.startswith(f"{prefix}/"):
                return os.environ.get(env_var)

        return None

    model_config = ConfigDict(env_prefix="ADKBOT_", env_nested_delimiter="__")


