"""Interactive onboarding questionnaire for ADKBot.

This module provides an interactive configuration wizard for ADKBot.
The wizard starts by default and guides users through:
1. Model selection (LiteLLM model strings)
2. API key configuration
3. Channel configuration (optional)
4. Other settings

Usage:
    adkbot onboard              # Starts wizard (default)
    adkbot onboard --skip-wizard  # Creates default config
"""

import importlib
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, get_args, get_origin

try:
    import questionary
    from questionary import Choice
except ModuleNotFoundError:
    questionary = None
    Choice = None

try:
    import dotenv
except ModuleNotFoundError:
    dotenv = None

from loguru import logger
from pydantic import BaseModel, ValidationError
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from adkbot.config.loader import get_config_path, load_config
from adkbot.config.schema import Config

console = Console()

# --- Result Type ---

@dataclass
class OnboardResult:
    """Result of an onboarding session."""
    config: Config
    should_save: bool


# Environment variable to model prefix mapping
PROVIDER_ENV_MAP = {
    "gemini": ("GEMINI_API_KEY", "https://aistudio.google.com/apikey"),
    "nvidia_nim": ("NVIDIA_NIM_API_KEY", "https://build.nvidia.com"),
    "groq": ("GROQ_API_KEY", "https://console.groq.com/keys"),
    "openai": ("OPENAI_API_KEY", "https://platform.openai.com/api-keys"),
    "anthropic": ("ANTHROPIC_API_KEY", "https://console.anthropic.com/settings/keys"),
    "openrouter": ("OPENROUTER_API_KEY", "https://openrouter.ai/keys"),
    "deepseek": ("DEEPSEEK_API_KEY", "https://platform.deepseek.com/api_keys"),
    "mistral": ("MISTRAL_API_KEY", "https://console.mistral.ai/api-keys"),
    "cohere": ("COHERE_API_KEY", "https://dashboard.cohere.com/api-keys"),
    "grok": ("GROK_API_KEY", "https://console.x.ai/"),
    "xai": ("GROK_API_KEY", "https://console.x.ai/"),
}

# Pre-configured models for the wizard UI and testing
MODEL_PRESETS = [
    ("Gemini 3.1 Pro", "gemini/gemini-3.1-pro-preview", "GEMINI_API_KEY", "Direct providers"),
    ("OpenAI GPT-4o", "openai/gpt-4o", "OPENAI_API_KEY", "Direct providers"),
    ("Claude 3 Opus", "anthropic/claude-3-opus-20240229", "ANTHROPIC_API_KEY", "Direct providers"),
    ("NVIDIA GLM-5", "nvidia_nim/z-ai/glm5", "NVIDIA_NIM_API_KEY", "Gateway providers"),
    ("OpenRouter Claude", "openrouter/anthropic/claude-3-opus", "OPENROUTER_API_KEY", "Gateway providers"),
    ("Ollama Llama 3.2", "ollama/llama3.2", None, "Local models"),
    ("Custom Model", None, None, "Custom"),
]

# --- CHANNEL UX IMPROVEMENTS ---
# These are technical fields that should use their defaults and NOT be shown in the wizard
ADVANCED_CHANNEL_FIELDS = {
    # General / Chat connections
    "connection_pool_size", "pool_timeout", "streaming", "intents", 
    "working_emoji", "working_emoji_delay", "read_receipt_emoji", 
    "react_emoji", "reply_to_message", "proxy",
    
    # Email Protocol Noise (Hide these so the user isn't overwhelmed)
    "consentGranted", "imapPort", "imapMailbox", "imapUseSsl",
    "smtpPort", "smtpUseTls", "smtpUseSsl", "autoReplyEnabled",
    "pollIntervalSeconds", "markSeen", "maxBodyChars", "subjectPrefix",
    "verifyDkim", "verifySpf",
    # (Pydantic might expose them as snake_case depending on aliases)
    "consent_granted", "imap_port", "imap_mailbox", "imap_use_ssl",
    "smtp_port", "smtp_use_tls", "smtp_use_ssl", "auto_reply_enabled",
    "poll_interval_seconds", "mark_seen", "max_body_chars", "subject_prefix",
    "verify_dkim", "verify_spf"
}

# Human-readable hints for channel fields to explain WHAT they are and WHERE to get them
CHANNEL_FIELD_HINTS = {
    "telegram": {
        "token": "Create a bot via @BotFather on Telegram and paste the HTTP API Token here.",
        "allow_from": "List of Telegram Usernames or IDs allowed to talk to the bot (comma-separated, leave blank for anyone).",
        "group_policy": "If added to a group: 'mention' (only replies when tagged) or 'open' (replies to everything)."
    },
    "discord": {
        "token": "Bot Token from the Discord Developer Portal -> Bot -> Reset Token.",
        "allow_from": "List of Discord User IDs allowed to talk to the bot (comma-separated, leave blank for anyone).",
        "group_policy": "If added to a server: 'mention' (only replies when tagged) or 'open' (replies to everything)."
    },
    "whatsapp": {
        "bridge_url": "The local WebSocket URL for the Node.js bridge (default: ws://localhost:3001).",
        "bridge_token": "Optional password to secure the local bridge (leave blank normally).",
        "allow_from": "List of phone numbers allowed to talk to the bot e.g., 2348012345678 (comma-separated, leave blank for anyone).",
        "group_policy": "If added to a WhatsApp group: 'mention' (only replies when tagged) or 'open' (replies to everything)."
    },
    "email": {
        "imapHost": "IMAP Server Address to read mail (e.g., imap.gmail.com).",
        "imapUsername": "The email address the bot will read from.",
        "imapPassword": "The email password (Use an 'App Password' if using Gmail/2FA).",
        "smtpHost": "SMTP Server Address to send mail (e.g., smtp.gmail.com).",
        "smtpUsername": "The email address the bot will send from (usually same as IMAP).",
        "smtpPassword": "The SMTP password (or App Password).",
        "fromAddress": "The sender address shown to recipients (e.g., bot@yourdomain.com).",
        "allow_from": "List of email addresses allowed to talk to the bot (comma-separated, leave blank for anyone)."
    },
    "qq": {
        "app_id": "App ID from the QQ Bot Open Platform.",
        "token": "Bot Token from the QQ Bot Open Platform.",
        "app_secret": "App Secret from the QQ Bot Open Platform."
    },
    "slack": {
        "app_token": "App-Level Token starting with 'xapp-' (Slack API -> Basic Information -> App-Level Tokens).",
        "bot_token": "Bot User OAuth Token starting with 'xoxb-' (Slack API -> OAuth & Permissions)."
    },
    "feishu": {
        "app_id": "App ID from Feishu/Lark Developer Console -> Credentials & Basic Info.",
        "app_secret": "App Secret from Feishu/Lark Developer Console -> Credentials & Basic Info.",
        "verification_token": "Event verification token (optional, from Event Subscriptions).",
        "encrypt_key": "Event encryption key (optional, from Event Subscriptions)."
    },
    "dingtalk": {
        "client_id": "App Key / Client ID from the DingTalk Developer Console.",
        "client_secret": "App Secret from the DingTalk Developer Console."
    },
    "wecom": {
        "corp_id": "Your Enterprise ID (My Enterprise -> Enterprise Information).",
        "corp_secret": "Secret from your specific App in WeCom.",
        "agent_id": "The Agent ID for your specific App in WeCom."
    },
    "matrix": {
        "homeserver": "The Matrix homeserver URL (e.g., https://matrix.org).",
        "username": "The bot's full username (e.g., @mybot:matrix.org).",
        "password": "The bot's account password."
    }
}


def _check_dependencies() -> None:
    """Ensure interactive dependencies are installed."""
    missing = []
    if questionary is None:
        missing.append("questionary")
    if dotenv is None:
        missing.append("python-dotenv")
    
    if missing:
        raise RuntimeError(
            f"Interactive onboarding requires missing dependencies: {', '.join(missing)}. "
            "Please install them and rerun."
        )


def _detect_api_keys() -> dict[str, str]:
    """Detect existing API keys from environment variables."""
    detected = {}
    for prefix, (env_var, _url) in PROVIDER_ENV_MAP.items():
        key = os.environ.get(env_var)
        if key:
            masked = "*" * (len(key) - 4) + key[-4:] if len(key) > 4 else "****"
            detected[env_var] = masked
    return detected


def _show_welcome() -> None:
    """Display the welcome screen."""
    console.clear()
    console.print()
    console.print(
        Panel.fit(
            "[bold cyan]🤖 ADKBot Configuration Wizard[/bold cyan]\n\n"
            "This wizard will help you set up ADKBot.\n"
            "You can configure:\n"
            "  • LLM model (using LiteLLM for multi-provider support)\n"
            "  • Chat channels (Telegram, Discord, WhatsApp, etc.)\n"
            "  • Agent settings\n\n"
            "[dim]Press Ctrl+C at any time to exit without saving.[/dim]",
            border_style="blue",
        )
    )
    console.print()


def _show_main_menu_header() -> None:
    """Display the main menu header."""
    from adkbot import __logo__, __version__
    console.print()
    console.print(Align.center(f"{__logo__} [bold cyan]ADKBot v{__version__}[/bold cyan]"))
    console.print()


def _configure_model_and_key(config: Config) -> None:
    """Wizard flow to set the LiteLLM model and associated API Key."""
    console.clear()
    detected_keys = _detect_api_keys()

    if detected_keys:
        console.print("[dim]Detected API keys in environment:[/dim]")
        for env_var, masked in detected_keys.items():
            console.print(f"  [green]✓[/green] {env_var}: {masked}")
        console.print()

    # Dynamically build the panel text from MODEL_PRESETS
    panel_content = "[bold]LiteLLM Model String Format[/bold]\n\nFormat: [cyan]provider/model-name[/cyan]\n\n"
    categories = {}
    for _name, model_str, _env, cat in MODEL_PRESETS:
        if not model_str:
            continue
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(model_str)

    for cat, models in categories.items():
        suffix = " (no API key needed):" if cat == "Local models" else ":"
        panel_content += f"[bold]{cat}[/bold]{suffix}\n"
        for m in models:
            panel_content += f"  [cyan]{m}[/cyan]\n"
        panel_content += "\n"

    console.print(Panel(
        panel_content.strip(),
        title="Model Selection",
        border_style="blue",
    ))
    console.print()

    current_model = config.agents.defaults.model
    model_string = questionary.text(
        "Enter your LiteLLM model string:",
        default=current_model if current_model else "nvidia_nim/z-ai/glm5",
    ).ask()

    if not model_string:
        return

    config.agents.defaults.model = model_string
    model_lower = model_string.lower()

    # 1. Handle API Base (Local Models)
    is_local = model_lower.startswith("ollama") or (model_lower.startswith("openai/") and "localhost" in model_lower)

    if is_local:
        console.print("\n[dim]Local model detected. Specify the API base URL.[/dim]")
        api_base = questionary.text(
            "API base URL:",
            default=getattr(config.agents.defaults, "api_base", None) or ("http://localhost:11434" if "ollama" in model_lower else "http://localhost:8000/v1"),
        ).ask()
        if api_base:
            setattr(config.agents.defaults, "api_base", api_base)
        return

    # 2. Handle API Key Configuration
    env_var, sign_up_url = None, None
    provider_name = model_string.split("/")[0] if "/" in model_string else model_string

    for prefix, (var, url) in PROVIDER_ENV_MAP.items():
        if model_lower.startswith(f"{prefix}/") or model_lower == prefix:
            env_var, sign_up_url = var, url
            break
            
    # Fallback for native Gemini string
    if not env_var and "gemini" in model_lower and "/" not in model_lower:
        env_var, sign_up_url = "GEMINI_API_KEY", "https://aistudio.google.com/apikey"

    # UNKNOWN PROVIDER LOGIC: Save to config.json
    if not env_var:
        console.print(f"\n[yellow]The provider '{provider_name}' is not in the standard known map.[/yellow]")
        custom_key = questionary.text(f"Enter API key for {provider_name} (leave blank if none):").ask()
        if custom_key:
            config.agents.defaults.api_key = custom_key
            console.print("[green]✓ Custom API key saved directly to config.json[/green]")
        else:
            config.agents.defaults.api_key = ""  # Explicitly clear the custom key!
            console.print("[dim]No custom API key provided. Existing custom key cleared.[/dim]")
        return

    # KNOWN PROVIDER LOGIC: Save to .env and clear config.json to prevent overrides
    existing_key = os.environ.get(env_var)
    if existing_key:
        console.print(f"\n[green]✓ Using {env_var} from environment[/green]")
        # Clear custom key so it doesn't override the valid .env key
        config.agents.defaults.api_key = "" 
        return

    console.print(f"\n[yellow]The model '{model_string}' requires an API key ({env_var}).[/yellow]")
    if sign_up_url:
        console.print(f"[dim]Get your key at: {sign_up_url}[/dim]")

    api_key = questionary.text(f"Enter your {env_var}:", default="").ask()

    if api_key:
        os.environ[env_var] = api_key
        _save_api_key_to_dotenv(env_var, api_key)
        # Clear custom key so it doesn't override the new .env key
        config.agents.defaults.api_key = ""
    else:
        console.print("[yellow]Warning: No API key provided. Model will likely fail to connect.[/yellow]")


def _save_api_key_to_dotenv(env_var: str, api_key: str) -> None:
    """Safely append or update an API key in ~/.adkbot/.env using python-dotenv."""
    from adkbot.config.paths import get_data_dir

    dotenv_path = get_data_dir() / ".env"
    dotenv_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Touch file if it doesn't exist so dotenv doesn't fail
    if not dotenv_path.exists():
        dotenv_path.write_text("", encoding="utf-8")

    dotenv.set_key(str(dotenv_path), env_var, api_key)
    console.print(f"[green]✓ Saved {env_var} to {dotenv_path}[/green]")


# Channel name → (required Python module, pip extra name)
_CHANNEL_SDK_MAP: dict[str, tuple[str, str]] = {
    "discord": ("discord", "discord"),
    "feishu": ("lark_oapi", "feishu"),
    "slack": ("slack_sdk", "slack"),
    "dingtalk": ("dingtalk_stream", "dingtalk"),
    "qq": ("botpy", "qq"),
    "matrix": ("nio", "matrix"),
    "wecom": ("wecom_aibot_sdk", "wecom"),
    "weixin": ("Crypto", "weixin"),
    "mochat": ("socketio", "mochat"),
    # telegram, whatsapp, email — no extra needed (core or no deps)
}


def _is_channel_sdk_installed(channel_name: str) -> bool:
    """Check if the required SDK for a channel is installed."""
    if channel_name not in _CHANNEL_SDK_MAP:
        return True  # No extra needed (telegram, whatsapp, email)

    module_name, _ = _CHANNEL_SDK_MAP[channel_name]
    try:
        importlib.import_module(module_name)
        return True
    except ImportError:
        return False


def _offer_install_channel(channel_name: str) -> bool:
    """Prompt the user to install a missing channel SDK. Returns True if installed successfully."""
    if channel_name not in _CHANNEL_SDK_MAP:
        return True

    _, extra_name = _CHANNEL_SDK_MAP[channel_name]

    console.print(
        f"\n[yellow]The {channel_name.title()} channel requires additional dependencies.[/yellow]\n\n"
        f"[dim]Depending on how you installed adkbot, you need one of these commands:[/dim]\n"
        f"  • uv:   [cyan]uv tool install adkbot --with \"adkbot[{extra_name}]\"[/cyan]\n"
        f"  • pipx: [cyan]pipx inject adkbot \"adkbot[{extra_name}]\"[/cyan]\n"
        f"  • pip:  [cyan]pip install \"adkbot[{extra_name}]\"[/cyan]\n"
    )

    install = questionary.confirm(
        "Attempt auto-install now? (May fail in strict uv/pipx environments)",
        default=True,
    ).ask()

    if not install:
        console.print("[dim]Skipping installation.[/dim]")
        return False

    import subprocess
    import sys

    # Smart detection: Use `uv pip` if uv is available, otherwise fallback to `python -m pip`
    if shutil.which("uv"):
        cmd = ["uv", "pip", "install", f"adkbot[{extra_name}]"]
    else:
        cmd = [sys.executable, "-m", "pip", "install", f"adkbot[{extra_name}]"]

    console.print(f"\n[cyan]Running: {' '.join(cmd)}...[/cyan]")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            console.print(f"[green]✓ {channel_name.title()} dependencies installed successfully![/green]")
            importlib.invalidate_caches()
            questionary.text("Press Enter to continue...").ask()
            return True
        else:
            console.print(f"\n[red]Auto-installation failed:[/red]\n{result.stderr.strip()[-800:]}")
            console.print(f"\n[yellow]Please copy the appropriate command above, run it manually in your terminal, and restart adkbot.[/yellow]")
            questionary.text("Press Enter to return to menu...").ask()
            return False
            
    except subprocess.TimeoutExpired:
        console.print("\n[red]Installation timed out.[/red]")
        console.print(f"[yellow]Please run the installation manually using the commands above.[/yellow]")
        questionary.text("Press Enter to return to menu...").ask()
        return False
    except Exception as e:
        console.print(f"\n[red]Installation error: {e}[/red]")
        questionary.text("Press Enter to return to menu...").ask()
        return False


def _configure_channels(config: Config) -> None:
    """Configure chat channels."""
    from adkbot.channels.registry import discover_channel_names

    # Show ALL channel names (even those whose SDKs aren't installed yet)
    all_channel_names = discover_channel_names()
    if not all_channel_names:
        console.print("[dim]No channels found in registry[/dim]")
        return

    while True:
        console.clear()
        console.print(Panel("[bold]Chat Channels[/bold]\nConfigure integrations with chat platforms.", border_style="blue"))

        choices = []
        for name in sorted(all_channel_names):
            channel_config = getattr(config.channels, name, None)

            enabled = False
            if isinstance(channel_config, BaseModel):
                enabled = getattr(channel_config, "enabled", False)
            elif isinstance(channel_config, dict):
                enabled = channel_config.get("enabled", False)

            # Check if the SDK is installed
            sdk_installed = _is_channel_sdk_installed(name)
            if enabled:
                status = "✓"
            elif not sdk_installed:
                status = "⬡"  # Not installed
            else:
                status = "○"

            label = f"{status} {name.title()}"
            if not sdk_installed:
                label += " [dim](not installed)[/dim]"
            choices.append(Choice(label, value=name))

        choices.append(Choice("← Back to Main Menu", value="back"))

        answer = questionary.select(
            "Select channel to configure:",
            choices=choices,
            qmark=">",
        ).ask()

        if answer is None or answer == "back":
            break

        # Auto-detect and offer to install missing SDK
        if not _is_channel_sdk_installed(answer):
            if not _offer_install_channel(answer):
                continue  # User declined or install failed, go back to menu

        # Now try to load the channel class
        try:
            from adkbot.channels.registry import load_channel_class
            channel_cls = load_channel_class(answer)
            _configure_single_channel(config, answer, channel_cls)
        except ImportError as e:
            console.print(f"\n[red]Could not load {answer.title()}: {e}[/red]")
            questionary.text("Press Enter to continue...").ask()


def _get_config_class_for_channel(channel_cls: type) -> type | None:
    """Attempt to find the Pydantic config class for a channel."""
    if hasattr(channel_cls, "get_config_class"):
        return channel_cls.get_config_class()
    
    import sys
    mod = sys.modules.get(channel_cls.__module__)
    if mod:
        cls_name = channel_cls.__name__.replace("Channel", "Config")
        if hasattr(mod, cls_name):
            attr = getattr(mod, cls_name)
            if isinstance(attr, type) and issubclass(attr, BaseModel):
                return attr
                
        for attr_name in dir(mod):
            if attr_name.endswith("Config"):
                attr = getattr(mod, attr_name)
                if isinstance(attr, type) and issubclass(attr, BaseModel) and attr.__name__ != "BaseConfig":
                    return attr
    return None


def _configure_single_channel(config: Config, channel_name: str, channel_cls: type) -> None:
    """Configure a single channel."""
    console.clear()
    console.print(Panel(f"[bold]Configure {channel_name.title()}[/bold]", border_style="blue"))

    current = getattr(config.channels, channel_name, None)
    if isinstance(current, BaseModel):
        current_dict = current.model_dump(by_alias=True, exclude_none=True)
    elif isinstance(current, dict):
        current_dict = current
    else:
        current_dict = {}

    config_class = _get_config_class_for_channel(channel_cls)
    
    if config_class:
        _configure_pydantic_channel(config, channel_name, config_class, current_dict)
    else:
        enabled = questionary.confirm(
            f"Enable {channel_name.title()}?",
            default=current_dict.get("enabled", False),
        ).ask()
        setattr(config.channels, channel_name, {"enabled": enabled})


def _configure_pydantic_channel(config: Config, channel_name: str, config_class: type[BaseModel], current_dict: dict) -> None:
    """Configure a channel using its Pydantic model with smart hints and typing."""
    try:
        working_model = config_class.model_validate(current_dict)
    except ValidationError:
        working_model = config_class()

    # Step 1: Always ask to Enable/Disable first
    if "enabled" in config_class.model_fields:
        enabled = questionary.confirm(
            f"Enable {channel_name.title()}?",
            default=getattr(working_model, "enabled", False),
        ).ask()
        setattr(working_model, "enabled", enabled)

        if not enabled:
            # If disabled, save and return immediately. Don't prompt for tokens.
            setattr(config.channels, channel_name, working_model.model_dump(by_alias=True, exclude_none=True))
            return

    # Look up the hints dictionary for this specific channel
    channel_hints = CHANNEL_FIELD_HINTS.get(channel_name, {})

    # Step 2: Loop through the relevant fields
    for field_name, field_info in config_class.model_fields.items():
        if field_name == "enabled":
            continue
            
        # Hide overly technical fields from the simple wizard UI
        if field_name in ADVANCED_CHANNEL_FIELDS:
            continue

        current_value = getattr(working_model, field_name, None)
        is_sensitive = any(kw in field_name.lower() for kw in ["token", "key", "secret", "password"])
        
        display_name = field_info.alias if field_info.alias else field_name.replace("_", " ").title()

        # Display the custom hint if we have one
        hint_text = channel_hints.get(field_name)
        if hint_text:
            console.print(f"\n[cyan]💡 {display_name}:[/cyan] [dim]{hint_text}[/dim]")
        else:
            console.print(f"\n[bold]{display_name}[/bold]")

        # Mask sensitive keys so no one screen-shares them
        if is_sensitive and current_value:
            masked = "*" * (len(str(current_value)) - 4) + str(current_value)[-4:]
            console.print(f"[dim]Current value: {masked}[/dim]")

        # Prepare default text for the prompt
        if isinstance(current_value, list):
            prompt_default = ",".join(str(v) for v in current_value)
        else:
            prompt_default = str(current_value) if current_value is not None else ""

        # Check if the field is a literal choice (like group_policy: 'open' or 'mention')
        origin = get_origin(field_info.annotation) or field_info.annotation
        
        # Determine the best Questionary UI prompt based on the variable type
        new_value = None
        if origin is bool:
            # Native Y/N prompt for booleans
            bool_val = questionary.confirm(
                f"Enable {display_name}?", 
                default=(current_value is True)
            ).ask()
            if bool_val is not None:
                new_value = "true" if bool_val else "false"
        elif get_origin(field_info.annotation) is Literal:
            # Dropdown menu for literal choices (e.g. ['open', 'mention'])
            choices = list(get_args(field_info.annotation))
            selected = questionary.select(
                f"Select {display_name}:",
                choices=choices,
                default=prompt_default if prompt_default in choices else choices[0]
            ).ask()
            if selected is not None:
                new_value = str(selected)
        else:
            # Standard text input
            new_value = questionary.text(
                f"Enter {display_name}:", 
                default=prompt_default
            ).ask()

        # Apply the new value and cast it properly
        if new_value is not None:
            parsed_value = new_value

            try:
                if origin is bool:
                    parsed_value = new_value.lower() in ("true", "1", "t", "y", "yes")
                elif origin is list or origin is set:
                    parsed_value = [v.strip() for v in new_value.split(",") if v.strip()]
                elif origin is int and new_value.isdigit():
                    parsed_value = int(new_value)
                elif origin is float and new_value:
                    parsed_value = float(new_value)
            except ValueError:
                pass

            setattr(working_model, field_name, parsed_value)

    # Save configuration to the active Pydantic Config tree
    dump = working_model.model_dump(by_alias=True, exclude_none=True)
    setattr(config.channels, channel_name, dump)
    console.print(f"\n[green]✓ {channel_name.title()} configured successfully![/green]")
    questionary.text("Press Enter to continue...").ask()


def _configure_agent_settings(config: Config) -> None:
    """Configure agent settings."""
    console.clear()
    console.print(Panel("[bold]Agent Settings[/bold]\nConfigure general agent behavior.", border_style="blue"))

    settings = [
        ("max_tool_iterations", "Max tool iterations", "15", int),
        ("context_window_tokens", "Context window (tokens)", "128000", int),
        ("temperature", "Temperature", "0.1", float),
        ("timezone", "Timezone", "UTC", str),
    ]

    for field_name, display_name, default, field_type in settings:
        current = getattr(config.agents.defaults, field_name, None)
        new_value = questionary.text(
            f"{display_name}:",
            default=str(current) if current is not None else default,
        ).ask()

        if new_value:
            try:
                setattr(config.agents.defaults, field_name, field_type(new_value))
            except ValueError:
                console.print(f"[yellow]Invalid format for {display_name}, keeping current value.[/yellow]")


def _show_summary(config: Config) -> None:
    """Display a clean summary of the pending configuration."""
    console.clear()

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Setting", style="cyan")
    table.add_column("Value")

    table.add_row("Model", config.agents.defaults.model or "[dim]Not Set[/dim]")
    
    if getattr(config.agents.defaults, "api_key", None):
        table.add_row("API Key", "[green]Saved in config.json[/green]")
    else:
        table.add_row("API Key", "[dim]Managed via .env[/dim]")
        
    table.add_row("Max Iterations", str(config.agents.defaults.max_tool_iterations))
    table.add_row("Context Window", f"{config.agents.defaults.context_window_tokens:,} tokens")
    table.add_row("Temperature", str(config.agents.defaults.temperature))
    
    channels_entry = "None"
    enabled_list = []
    
    for name, config_val in config.channels.model_dump(by_alias=True).items():
        if isinstance(config_val, dict) and config_val.get("enabled", False):
            enabled_list.append(name.title())
    
    if enabled_list:
        channels_entry = ", ".join(enabled_list)

    table.add_row("Enabled Channels", f"[bold green]{channels_entry}[/bold green]")
    table.add_row("Timezone", config.agents.defaults.timezone)

    console.print(Panel(table, title="[bold]Configuration Summary[/bold]", border_style="blue"))
    console.print()


def _save_config(config: Config, config_path: Path) -> bool:
    """Save configuration to file safely."""
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_dict = config.model_dump(mode="json", by_alias=True, exclude_none=True)

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_dict, f, indent=2, ensure_ascii=False)

        console.print(f"\n[green]✓ Configuration perfectly saved to {config_path}[/green]")
        return True

    except Exception as e:
        console.print(f"\n[bold red]Error saving configuration:[/bold red] {e}")
        return False


def run_onboard(initial_config: Config | None = None, skip_wizard: bool = False) -> OnboardResult:
    """Run the main interactive onboarding questionnaire."""
    _check_dependencies()

    if skip_wizard:
        config_path = get_config_path()
        if config_path.exists():
            console.print(f"[dim]Loading existing config from {config_path}[/dim]")
            return OnboardResult(config=load_config(), should_save=False)
        else:
            console.print("[dim]Creating default configuration[/dim]")
            return OnboardResult(config=Config(), should_save=True)

    if initial_config is not None:
        config = initial_config.model_copy(deep=True)
    else:
        config_path = get_config_path()
        config = load_config() if config_path.exists() else Config()

    original_config = config.model_copy(deep=True)
    _show_welcome()

    while True:
        _show_main_menu_header()

        try:
            answer = questionary.select(
                "What would you like to configure?",
                choices=[
                    Choice("🤖 Configure Model & API Key", value="model"),
                    Choice("💬 Configure Chat Channels", value="channels"),
                    Choice("⚙️  Agent Settings", value="agent"),
                    Choice("📋 View Configuration Summary", value="summary"),
                    questionary.Separator(),
                    Choice("💾 Save and Exit", value="save"),
                    Choice("❌ Exit Without Saving", value="exit"),
                ],
                qmark=">",
            ).ask()
        except KeyboardInterrupt:
            answer = None

        if answer is None or answer == "exit":
            console.print("\n[dim]Exiting... Configuration discarded.[/dim]")
            return OnboardResult(config=original_config, should_save=False)

        if answer == "save":
            if _save_config(config, get_config_path()):
                return OnboardResult(config=config, should_save=True)
            continue

        if answer == "model":
            _configure_model_and_key(config)
        elif answer == "channels":
            _configure_channels(config)
        elif answer == "agent":
            _configure_agent_settings(config)
        elif answer == "summary":
            _show_summary(config)
            questionary.text("Press Enter to return to menu...").ask()