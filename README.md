<div align="center">
  <img src="adkbot_logo.png" alt="adkbot" width="500">
  <h1>Multi-Model AI Assistant</h1>
  <p>
    <img src="https://img.shields.io/badge/python-≥3.11-blue" alt="Python">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
    <img src="https://img.shields.io/badge/ADK-powered-orange" alt="ADK">
    <img src="https://img.shields.io/badge/LiteLLM-multi--model-purple" alt="LiteLLM">
  </p>
</div>

🤖 **ADKBot** is a powerful, multi-model AI assistant framework built on [Google's Agent Development Kit (ADK)](https://google.github.io/adk-docs/) with [LiteLLM](https://docs.litellm.ai/) for universal model support. ADKBot is an **ADK-native** project, built from the ground up to leverage ADK's agent architecture while preserving and extending a rich tooling and channel ecosystem.

⚡ Use **any LLM provider** (NVIDIA NIM, Gemini, Groq, OpenRouter, Anthropic, OpenAI, xAI, Ollama, and 50+ more) through a single unified interface.

🔌 Connect to **12+ chat platforms** (Telegram, Discord, WhatsApp, Slack, WeChat, and more).

🛠️ Equipped with **10+ built-in tools** (web search, file operations, shell commands, scheduled tasks, MCP support, and sub-agent spawning).

## Key Features

🧠 **ADK-Powered**: Built on Google's Agent Development Kit for robust agent lifecycle management, native callbacks, and session handling.

🌐 **Multi-Model**: LiteLLM integration means you can use Claude, GPT, Gemini, DeepSeek, Llama, and 50+ other models without changing code.

🔧 **Rich Tooling**: Web search (5 providers), file operations, shell execution, cron scheduling, MCP protocol support, and sub-agent spawning.

📱 **12+ Chat Channels**: Telegram, Discord, WhatsApp, WeChat, Feishu, DingTalk, Slack, Matrix, Email, QQ, WeCom, and Mochat.

⏰ **Scheduled Tasks**: Cron expressions, interval timers, and one-time scheduling with timezone support.

🔒 **Security**: Workspace sandboxing, command safety guards, SSRF protection, and per-channel access control.

💎 **Easy to Use**: One command to set up, one command to chat.

## Table of Contents

- [Key Features](#key-features)
- [Install](#-install)
- [Quick Start](#-quick-start)
- [Chat Apps](#-chat-apps)
- [Configuration](#️-configuration)
- [Multiple Instances](#-multiple-instances)
- [CLI Reference](#-cli-reference)
- [Python SDK](#-python-sdk)
- [OpenAI-Compatible API](#-openai-compatible-api)
- [Docker](#-docker)
- [Linux Service](#-linux-service)
- [Project Structure](#-project-structure)
- [Contributing](#-contributing)

## 📦 Install

**With [uv](https://github.com/astral-sh/uv)** (recommended, fast):

```bash
uv tool install adkbot
```

**With pip:**

```bash
pip install adkbot
```

<details>
<summary><b>Install from source (for development)</b></summary>

```bash
git clone https://github.com/nwokike/ADKbot.git
cd ADKbot
uv venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
uv sync --all-extras
```

</details>

<details>
<summary><b>Install on Termux (Android)</b></summary>

Python packages with native dependencies can cause build issues inside raw Termux. Use `proot-distro` to run a proper Linux distribution inside Termux instead.

```bash
# Install proot-distro
pkg update && pkg upgrade
pkg install proot-distro

# Install and log into Ubuntu
proot-distro install ubuntu
proot-distro login ubuntu

# Inside Ubuntu: install uv
apt update && apt upgrade -y
apt install curl -y
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.profile

# Install ADKBot
uv tool install adkbot
```

</details>

### Update to latest version

**uv:**

```bash
uv tool upgrade adkbot
adkbot --version
```

**pip:**

```bash
pip install -U adkbot
adkbot --version
```

### Requirements

- Python >= 3.11
- An API key from any supported LLM provider

## 🚀 Quick Start

> [!TIP]
> Get API keys:
> - [NVIDIA NIM](https://build.nvidia.com/) (recommended, completely free, massive open-weight model catalog)
> - [Google Gemini](https://aistudio.google.com/apikey) (free tier available, best ADK integration)
> - [Groq](https://console.groq.com/) (fastest inference, free tier)
> - [OpenRouter](https://openrouter.ai/) (access to many models via one key)
> - [Anthropic](https://console.anthropic.com/) (Claude Opus 4.6)
> - [OpenAI](https://platform.openai.com/api-keys) (GPT 5.4)
> - [xAI](https://console.x.ai/) (Grok 4.20)
>
> API keys can be set as environment variables (e.g., `NVIDIA_NIM_API_KEY=nvapi-xxx`) or entered during the wizard.
>
> For web search setup, see [Web Search](#web-search).

**1. Initialize**

```bash
adkbot onboard
```

This starts the interactive wizard by default. Use `adkbot onboard --skip-wizard` to create a basic config without the wizard.

**2. Configure** (`~/.adkbot/config.json`)

*Configure your model* using a LiteLLM model string:

```json
{
  "agents": {
    "defaults": {
      "model": "nvidia_nim/nvidia/nemotron-3-super-120b-a12b"
    }
  }
}
```

LiteLLM model strings work with 100+ providers. Examples:
- `"nvidia_nim/nvidia/nemotron-3-super-120b-a12b"` - NVIDIA NIM (uses `NVIDIA_NIM_API_KEY`, free)
- `"nvidia_nim/moonshotai/kimi-k2-instruct-0905"` - Kimi K2 via NVIDIA NIM (free)
- `"gemini/gemini-3.1-pro-preview"` - Google Gemini (uses `GEMINI_API_KEY`)
- `"groq/llama-3.3-70b-versatile"` - Groq (uses `GROQ_API_KEY`)
- `"anthropic/claude-opus-4-6"` - Anthropic Claude (uses `ANTHROPIC_API_KEY`)
- `"openai/gpt-5.4"` - OpenAI (uses `OPENAI_API_KEY`)
- `"openrouter/anthropic/claude-opus-4-6"` - OpenRouter gateway (uses `OPENROUTER_API_KEY`)
- `"xai/grok-4.20-beta-0309-reasoning"` - xAI Grok (uses `GROK_API_KEY`)
- `"deepseek/deepseek-chat"` - DeepSeek (uses `DEEPSEEK_API_KEY`)
- `"ollama/llama3.2"` - Local Ollama (no API key needed)

Set your API key as an environment variable (e.g., `NVIDIA_NIM_API_KEY=nvapi-xxx`) or enter it during the wizard.

<details>
<summary><b>Why NVIDIA NIM?</b></summary>

NVIDIA NIM is our recommended default for new users because:

- **Completely free** with no credit card required
- Hosts hundreds of top open-weight models (Nemotron, Llama 4, Kimi K2, Mistral, Gemma, and more)
- Runs on NVIDIA's own Hopper GPU infrastructure so inference is fast
- Works with LiteLLM out of the box using the `nvidia_nim/` prefix

Popular NVIDIA NIM models:

| Model | String | Best for |
|-------|--------|----------|
| Nemotron 3 Super 120B | `nvidia_nim/nvidia/nemotron-3-super-120b-a12b` | General reasoning, coding |
| Kimi K2 Instruct | `nvidia_nim/moonshotai/kimi-k2-instruct-0905` | Long context, complex tasks |
| Llama 4 Scout 17B | `nvidia_nim/meta/llama-4-scout-17b-16e-instruct` | Fast text generation |
| Gemma 4 27B | `nvidia_nim/google/gemma-4-27b-it` | Lightweight general tasks |

Sign up at [build.nvidia.com](https://build.nvidia.com/) and grab your free API key.

</details>

<details>
<summary><b>Provider comparison at a glance</b></summary>

| Provider | Free tier | Speed | Model variety | Best for |
|----------|-----------|-------|---------------|----------|
| **NVIDIA NIM** | Yes (completely free) | Fast | Hundreds of open-weight models | Default choice, coding, reasoning |
| **Google Gemini** | Yes (generous limits) | Fast | Gemini family only | Native ADK integration, huge context |
| **Groq** | Yes (rate limited) | Fastest | Llama, Mixtral | Low-latency chat |
| **OpenRouter** | No (pay per token) | Varies | 200+ models from all providers | Access to everything via one key |
| **Anthropic** | No | Medium | Claude family only | Complex writing, analysis |
| **OpenAI** | No | Medium | GPT family only | Broad compatibility |
| **xAI** | Limited | Fast | Grok family only | Reasoning, code |
| **Ollama** | Yes (local) | Hardware dependent | Any GGUF model | Privacy, offline use |

</details>

**3. Chat**

```bash
adkbot agent
```

That's it! You have a working AI assistant in 2 minutes.

## 💬 Chat Apps

Connect ADKBot to your favorite chat platform. Want to build your own? See the [Channel Plugin Guide](./docs/CHANNEL_PLUGIN_GUIDE.md).

| Channel | What you need |
|---------|---------------|
| **Telegram** | Bot token from @BotFather |
| **Discord** | Bot token + Message Content intent |
| **WhatsApp** | QR code scan (`adkbot channels login whatsapp`) |
| **WeChat (Weixin)** | QR code scan (`adkbot channels login weixin`) |
| **Feishu** | App ID + App Secret |
| **DingTalk** | App Key + App Secret |
| **Slack** | Bot token + App-Level token |
| **Matrix** | Homeserver URL + Access token |
| **Email** | IMAP/SMTP credentials |
| **QQ** | App ID + App Secret |
| **WeCom** | Bot ID + Bot Secret |
| **Mochat** | Claw token (auto-setup available) |

<details>
<summary><b>Telegram</b> (Recommended)</summary>

**1. Create a bot**
- Open Telegram, search `@BotFather`
- Send `/newbot`, follow prompts
- Copy the token

**2. Configure**

```json
{
  "channels": {
    "telegram": {
      "enabled": true,
      "token": "YOUR_BOT_TOKEN",
      "allowFrom": ["YOUR_USER_ID"]
    }
  }
}
```

> You can find your **User ID** in Telegram settings. Copy without the `@` symbol.

**3. Run**

```bash
adkbot gateway
```

</details>

<details>
<summary><b>Discord</b></summary>

**1. Create a bot**
- Go to https://discord.com/developers/applications
- Create an application → Bot → Add Bot
- Copy the bot token

**2. Enable intents**
- In Bot settings, enable **MESSAGE CONTENT INTENT**

**3. Get your User ID**
- Discord Settings → Advanced → enable **Developer Mode**
- Right-click your avatar → **Copy User ID**

**4. Configure**

```json
{
  "channels": {
    "discord": {
      "enabled": true,
      "token": "YOUR_BOT_TOKEN",
      "allowFrom": ["YOUR_USER_ID"],
      "groupPolicy": "mention"
    }
  }
}
```

> `groupPolicy`: `"mention"` (default — respond when @mentioned), `"open"` (respond to all messages).

**5. Invite the bot**
- OAuth2 → URL Generator
- Scopes: `bot`
- Bot Permissions: `Send Messages`, `Read Message History`
- Open the generated invite URL and add the bot to your server

**6. Run**

```bash
adkbot gateway
```

</details>

<details>
<summary><b>WhatsApp</b></summary>

Requires **Node.js ≥18**.

**1. Link device**

```bash
adkbot channels login whatsapp
# Scan QR with WhatsApp → Settings → Linked Devices
```

**2. Configure**

```json
{
  "channels": {
    "whatsapp": {
      "enabled": true,
      "allowFrom": ["+1234567890"]
    }
  }
}
```

**3. Run**

```bash
adkbot gateway
```

</details>

<details>
<summary><b>Matrix (Element)</b></summary>

Install Matrix dependencies first:

```bash
pip install "adkbot[matrix]"
```

**1. Create/choose a Matrix account**

Create or reuse a Matrix account on your homeserver (for example `matrix.org`).

**2. Get credentials**

You need:
- `userId` (example: `@adkbot:matrix.org`)
- `accessToken`
- `deviceId` (recommended so sync tokens can be restored across restarts)

**3. Configure**

```json
{
  "channels": {
    "matrix": {
      "enabled": true,
      "homeserver": "https://matrix.org",
      "userId": "@adkbot:matrix.org",
      "accessToken": "syt_xxx",
      "deviceId": "ADKBOT01",
      "e2eeEnabled": true,
      "allowFrom": ["@your_user:matrix.org"],
      "groupPolicy": "open"
    }
  }
}
```

| Option | Description |
|--------|-------------|
| `allowFrom` | User IDs allowed to interact. Empty denies all; use `["*"]` to allow everyone. |
| `groupPolicy` | `open` (default), `mention`, or `allowlist`. |
| `e2eeEnabled` | E2EE support (default `true`). Set `false` for plaintext-only. |

**4. Run**

```bash
adkbot gateway
```

</details>

<details>
<summary><b>Mochat (Claw IM)</b></summary>

Uses **Socket.IO WebSocket** by default, with HTTP polling fallback.

**1. Ask ADKBot to set up Mochat for you**

Simply send this message to ADKBot:

```
Read https://raw.githubusercontent.com/nwokike/MoChat/refs/heads/main/skills/adkbot/skill.md and register on MoChat. My Email account is onyeka@kiri.ng Bind me as your owner and DM me on MoChat.
```

**2. Restart gateway**

```bash
adkbot gateway
```

<details>
<summary>Manual configuration (advanced)</summary>

```json
{
  "channels": {
    "mochat": {
      "enabled": true,
      "base_url": "https://mochat.io",
      "socket_url": "https://mochat.io",
      "socket_path": "/socket.io",
      "claw_token": "claw_xxx",
      "agent_user_id": "6982abcdef",
      "sessions": ["*"],
      "panels": ["*"]
    }
  }
}
```

</details>

</details>

<details>
<summary><b>Feishu</b></summary>

Uses **WebSocket** long connection — no public IP required.

**1. Create a Feishu bot**
- Visit [Feishu Open Platform](https://open.feishu.cn/app)
- Create a new app → Enable **Bot** capability
- **Permissions**: `im:message`, `im:message.p2p_msg:readonly`, `cardkit:card:write`
- **Events**: Add `im.message.receive_v1` → Select **Long Connection** mode
- Get **App ID** and **App Secret**
- Publish the app

**2. Configure**

```json
{
  "channels": {
    "feishu": {
      "enabled": true,
      "appId": "cli_xxx",
      "appSecret": "xxx",
      "allowFrom": ["ou_YOUR_OPEN_ID"],
      "groupPolicy": "mention",
      "streaming": true
    }
  }
}
```

**3. Run**

```bash
adkbot gateway
```

</details>

<details>
<summary><b>DingTalk (钉钉)</b></summary>

Uses **Stream Mode** — no public IP required.

**1. Create a DingTalk bot**
- Visit [DingTalk Open Platform](https://open-dev.dingtalk.com/)
- Create a new app → Add **Robot** capability → Toggle **Stream Mode** ON
- Get **AppKey** and **AppSecret**

**2. Configure**

```json
{
  "channels": {
    "dingtalk": {
      "enabled": true,
      "clientId": "YOUR_APP_KEY",
      "clientSecret": "YOUR_APP_SECRET",
      "allowFrom": ["YOUR_STAFF_ID"]
    }
  }
}
```

**3. Run**

```bash
adkbot gateway
```

</details>

<details>
<summary><b>Slack</b></summary>

Uses **Socket Mode** — no public URL required.

**1. Create a Slack app**
- Go to [Slack API](https://api.slack.com/apps) → **Create New App** → "From scratch"

**2. Configure the app**
- **Socket Mode**: Toggle ON → Generate an **App-Level Token** with `connections:write` scope → copy it (`xapp-...`)
- **OAuth & Permissions**: Add bot scopes: `chat:write`, `reactions:write`, `app_mentions:read`
- **Event Subscriptions**: Toggle ON → Subscribe to: `message.im`, `message.channels`, `app_mention`
- **App Home**: Enable **Messages Tab** → Check **"Allow users to send Slash commands and messages from the messages tab"**
- **Install App**: Click **Install to Workspace** → copy the **Bot Token** (`xoxb-...`)

**3. Configure ADKBot**

```json
{
  "channels": {
    "slack": {
      "enabled": true,
      "botToken": "xoxb-...",
      "appToken": "xapp-...",
      "allowFrom": ["YOUR_SLACK_USER_ID"],
      "groupPolicy": "mention"
    }
  }
}
```

**4. Run**

```bash
adkbot gateway
```

</details>

<details>
<summary><b>Email</b></summary>

Give ADKBot its own email account. It polls **IMAP** for incoming mail and replies via **SMTP**.

**1. Get credentials (Gmail example)**
- Create a dedicated Gmail account (e.g. `my-adkbot@gmail.com`)
- Enable 2-Step Verification → Create an [App Password](https://myaccount.google.com/apppasswords)

**2. Configure**

```json
{
  "channels": {
    "email": {
      "enabled": true,
      "consentGranted": true,
      "imapHost": "imap.gmail.com",
      "imapPort": 993,
      "imapUsername": "my-adkbot@gmail.com",
      "imapPassword": "your-app-password",
      "smtpHost": "smtp.gmail.com",
      "smtpPort": 587,
      "smtpUsername": "my-adkbot@gmail.com",
      "smtpPassword": "your-app-password",
      "fromAddress": "my-adkbot@gmail.com",
      "allowFrom": ["your-real-email@gmail.com"]
    }
  }
}
```

**3. Run**

```bash
adkbot gateway
```

</details>

<details>
<summary><b>QQ (QQ单聊)</b></summary>

Uses **botpy SDK** with WebSocket — no public IP required. Currently supports **private messages only**.

**1. Register & create bot**
- Visit [QQ Open Platform](https://q.qq.com) → Create a new bot application
- Copy **AppID** and **AppSecret**

**2. Configure**

```json
{
  "channels": {
    "qq": {
      "enabled": true,
      "appId": "YOUR_APP_ID",
      "secret": "YOUR_APP_SECRET",
      "allowFrom": ["YOUR_OPENID"]
    }
  }
}
```

**3. Run**

```bash
adkbot gateway
```

</details>

<details>
<summary><b>WeChat (微信 / Weixin)</b></summary>

Uses **HTTP long-poll** with QR-code login.

**1. Install with WeChat support**

```bash
pip install "adkbot[weixin]"
```

**2. Configure**

```json
{
  "channels": {
    "weixin": {
      "enabled": true,
      "allowFrom": ["YOUR_WECHAT_USER_ID"]
    }
  }
}
```

**3. Login**

```bash
adkbot channels login weixin
```

**4. Run**

```bash
adkbot gateway
```

</details>

<details>
<summary><b>WeCom (企业微信)</b></summary>

Uses **WebSocket** long connection — no public IP required.

**1. Install**

```bash
pip install adkbot[wecom]
```

**2. Configure**

```json
{
  "channels": {
    "wecom": {
      "enabled": true,
      "botId": "your_bot_id",
      "secret": "your_bot_secret",
      "allowFrom": ["your_id"]
    }
  }
}
```

**3. Run**

```bash
adkbot gateway
```

</details>

## ⚙️ Configuration

Config file: `~/.adkbot/config.json`

### Model Configuration

ADKBot uses **LiteLLM** under the hood, which means it supports 100+ LLM providers through a unified interface. Simply specify the model using a LiteLLM model string.

> [!TIP]
> - **Groq** provides free voice transcription via Whisper. If configured, Telegram voice messages will be automatically transcribed.
> - For local models, use `ollama` or `vllm` model strings.

| Provider | LiteLLM Model String | API Key Environment Variable |
|----------|---------------------|------------------------------|
| Google Gemini | `gemini/gemini-3.1-pro-preview` | `GEMINI_API_KEY` |
| NVIDIA NIM | `nvidia_nim/nvidia/nemotron-3-super-120b-a12b` | `NVIDIA_NIM_API_KEY` |
| Groq | `groq/llama-3.3-70b-versatile` | `GROQ_API_KEY` |
| Anthropic Claude | `anthropic/claude-opus-4-6` | `ANTHROPIC_API_KEY` |
| OpenAI | `openai/gpt-5.4` | `OPENAI_API_KEY` |
| OpenRouter | `openrouter/anthropic/claude-opus-4-6` | `OPENROUTER_API_KEY` |
| xAI (Grok) | `xai/grok-4.20-beta-0309-reasoning` | `GROK_API_KEY` |
| DeepSeek | `deepseek/deepseek-chat` | `DEEPSEEK_API_KEY` |
| Ollama (local) | `ollama/llama3.2` | None |
| vLLM (local) | `openai/meta-llama/Llama-3.1-8B-Instruct` + `apiBase` | Any (e.g., `dummy`) |

> **Gemini** is a first-class citizen. ADKBot uses Google ADK natively, so Gemini models get the best possible integration.

<details>
<summary><b>LiteLLM Model String Format</b></summary>

LiteLLM uses the format `provider/model-name` or just `model-name` for native providers:

```json
{
  "agents": {
    "defaults": {
      "model": "gemini/gemini-3.1-pro-preview",
      "apiKey": "",
      "apiBase": null
    }
  }
}
```

- **model**: LiteLLM model string (e.g., `gemini/gemini-3.1-pro-preview`, `nvidia_nim/nvidia/nemotron-3-super-120b-a12b`)
- **apiKey**: Optional API key. If empty, uses environment variables
- **apiBase**: Optional custom API base URL (for self-hosted endpoints)

Examples:
- `"gemini/gemini-3.1-pro-preview"` - Google Gemini (uses `GEMINI_API_KEY`)
- `"nvidia_nim/nvidia/nemotron-3-super-120b-a12b"` - NVIDIA NIM (uses `NVIDIA_NIM_API_KEY`)
- `"anthropic/claude-opus-4-6"` - Anthropic Claude (uses `ANTHROPIC_API_KEY`)
- `"ollama/llama3.2"` - Local Ollama (no API key needed)

For 100+ providers, see: https://docs.litellm.ai/docs/providers

</details>

<details>
<summary><b>Ollama (local)</b></summary>

Run a local model with Ollama:

**1. Start Ollama:**
```bash
ollama run llama3.2
```

**2. Add to config:**
```json
{
  "agents": {
    "defaults": {
      "model": "ollama/llama3.2"
    }
  }
}
```

</details>

<details>
<summary><b>vLLM (local / OpenAI-compatible)</b></summary>

Run your own model with vLLM or any OpenAI-compatible server:

**1. Start the server:**
```bash
vllm serve meta-llama/Llama-3.1-8B-Instruct --port 8000
```

**2. Add to config:**
```json
{
  "agents": {
    "defaults": {
      "model": "openai/meta-llama/Llama-3.1-8B-Instruct",
      "apiKey": "dummy",
      "apiBase": "http://localhost:8000/v1"
    }
  }
}
```

> For local servers that don't require a key, set `apiKey` to any non-empty string (e.g., `"dummy"`).

</details>

<details>
<summary><b>Custom/OpenAI-compatible Endpoint</b></summary>

Connect to any OpenAI-compatible endpoint (LM Studio, llama.cpp, Together AI, Fireworks):

```json
{
  "agents": {
    "defaults": {
      "model": "openai/your-model-name",
      "apiKey": "your-api-key",
      "apiBase": "https://api.your-provider.com/v1"
    }
  }
}
```

</details>

### Channel Settings

Global settings that apply to all channels:

```json
{
  "channels": {
    "sendProgress": true,
    "sendToolHints": false,
    "sendMaxRetries": 3,
    "telegram": { "..." : "..." }
  }
}
```

| Setting | Default | Description |
|---------|---------|-------------|
| `sendProgress` | `true` | Stream agent's text progress to the channel |
| `sendToolHints` | `false` | Stream tool-call hints (e.g. `read_file("…")`) |
| `sendMaxRetries` | `3` | Max delivery attempts per outbound message |

### Web Search

> [!TIP]
> Use `proxy` in `tools.web` to route all web requests through a proxy:
> ```json
> { "tools": { "web": { "proxy": "http://127.0.0.1:7890" } } }
> ```

ADKBot supports multiple web search providers. Configure in `~/.adkbot/config.json` under `tools.web.search`.

| Provider | Config fields | Env var fallback | Free |
|----------|--------------|------------------|------|
| `brave` (default) | `apiKey` | `BRAVE_API_KEY` | No |
| `tavily` | `apiKey` | `TAVILY_API_KEY` | No |
| `jina` | `apiKey` | `JINA_API_KEY` | Free tier (10M tokens) |
| `searxng` | `baseUrl` | `SEARXNG_BASE_URL` | Yes (self-hosted) |
| `duckduckgo` | — | — | Yes |

When credentials are missing, ADKBot automatically falls back to DuckDuckGo.

<details>
<summary><b>Search provider examples</b></summary>

**Brave** (default):
```json
{
  "tools": { "web": { "search": { "provider": "brave", "apiKey": "BSA..." } } }
}
```

**Tavily:**
```json
{
  "tools": { "web": { "search": { "provider": "tavily", "apiKey": "tvly-..." } } }
}
```

**DuckDuckGo** (zero config):
```json
{
  "tools": { "web": { "search": { "provider": "duckduckgo" } } }
}
```

</details>

### MCP (Model Context Protocol)

> [!TIP]
> The config format is compatible with Claude Desktop / Cursor. You can copy MCP server configs directly from any MCP server's README.

ADKBot supports [MCP](https://modelcontextprotocol.io/) — connect external tool servers and use them as native agent tools.

```json
{
  "tools": {
    "mcpServers": {
      "filesystem": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/dir"]
      },
      "my-remote-mcp": {
        "url": "https://example.com/mcp/",
        "headers": { "Authorization": "Bearer xxxxx" }
      }
    }
  }
}
```

| Mode | Config | Example |
|------|--------|---------|
| **Stdio** | `command` + `args` | Local process via `npx` / `uvx` |
| **HTTP** | `url` + `headers` (optional) | Remote endpoint |

MCP tools are automatically discovered and registered on startup. The LLM can use them alongside built-in tools — no extra configuration needed.

### Security

> [!TIP]
> For production deployments, set `"restrictToWorkspace": true` to sandbox the agent.

| Option | Default | Description |
|--------|---------|-------------|
| `tools.restrictToWorkspace` | `false` | Restricts all tools to the workspace directory |
| `tools.exec.enable` | `true` | When `false`, disables shell command execution entirely |
| `tools.exec.pathAppend` | `""` | Extra directories to append to `PATH` for shell commands |
| `channels.*.allowFrom` | `[]` (deny all) | Whitelist of user IDs. Use `["*"]` to allow everyone |

### Timezone

By default, ADKBot uses `UTC`. Set `agents.defaults.timezone` to your local timezone:

```json
{
  "agents": {
    "defaults": {
      "timezone": "Asia/Shanghai"
    }
  }
}
```

This affects runtime time context, cron schedule defaults, and one-shot `at` times.

Common examples: `UTC`, `America/New_York`, `America/Los_Angeles`, `Europe/London`, `Asia/Tokyo`, `Asia/Shanghai`.

## 🧩 Multiple Instances

Run multiple ADKBot instances simultaneously with separate configs and runtime data.

### Quick Start

```bash
# Create separate instance configs
adkbot onboard --config ~/.adkbot-telegram/config.json --workspace ~/.adkbot-telegram/workspace
adkbot onboard --config ~/.adkbot-discord/config.json --workspace ~/.adkbot-discord/workspace
```

**Run instances:**

```bash
# Instance A - Telegram bot
adkbot gateway --config ~/.adkbot-telegram/config.json

# Instance B - Discord bot
adkbot gateway --config ~/.adkbot-discord/config.json
```

### Path Resolution

| Component | Resolved From | Example |
|-----------|---------------|---------|
| **Config** | `--config` path | `~/.adkbot-A/config.json` |
| **Workspace** | `--workspace` or config | `~/.adkbot-A/workspace/` |
| **Cron Jobs** | config directory | `~/.adkbot-A/cron/` |
| **Media / state** | config directory | `~/.adkbot-A/media/` |

### Notes

- Each instance must use a different port if they run concurrently
- Use a different workspace per instance for isolated memory and sessions
- `--workspace` overrides the workspace defined in the config file

## 💻 CLI Reference

<details>
<summary><b>View Common Commands</b></summary>

| Command | Description |
|---------|-------------|
| `adkbot onboard` | Initialize config & workspace at `~/.adkbot/` |
| `adkbot onboard --wizard` | Launch the interactive onboarding wizard |
| `adkbot agent -m "..."` | Chat with the agent |
| `adkbot agent` | Interactive chat mode |
| `adkbot gateway` | Start the gateway (connects to chat channels) |
| `adkbot status` | Show status |
| `adkbot channels login <channel>` | Authenticate a channel interactively |

Interactive mode exits: `exit`, `quit`, `/exit`, `/quit`, `:q`, or `Ctrl+D`.

For a full list of commands and options, see the **[Comprehensive CLI Reference](docs/COMMANDS.md)**.

</details>

<details>
<summary><b>Heartbeat (Periodic Tasks)</b></summary>

The gateway wakes up every 30 minutes and checks `HEARTBEAT.md` in your workspace (`~/.adkbot/workspace/HEARTBEAT.md`). If the file has tasks, the agent executes them and delivers results to your most recently active chat channel.

**Setup:** edit `~/.adkbot/workspace/HEARTBEAT.md`:

```markdown
## Periodic Tasks

- [ ] Check weather forecast and send a summary
- [ ] Scan inbox for urgent emails
```

The agent can also manage this file itself — ask it to "add a periodic task" and it will update `HEARTBEAT.md` for you.

> **Note:** The gateway must be running (`adkbot gateway`) and you must have chatted with the bot at least once.

</details>

## 🐍 Python SDK

Use ADKBot as a library — no CLI, no gateway, just Python:

```python
from adkbot import AdkBot

bot = AdkBot.from_config()
result = await bot.run("Summarize the README")
print(result.content)
```

Each call carries a `session_id` for conversation isolation — different IDs get independent history:

```python
await bot.run("hi", session_id="user-alice")
await bot.run("hi", session_id="task-42")
```

ADKBot uses ADK's native callback system for lifecycle hooks:

```python
# Callbacks are configured via the Agent's before/after hooks
# See adkbot/agent/callbacks.py for the full callback API
```

## 🔌 OpenAI-Compatible API

ADKBot can expose a minimal OpenAI-compatible endpoint for local integrations:

```bash
pip install "adkbot[api]"
adkbot serve
```

By default, the API binds to `127.0.0.1:8900`.

### Endpoints

- `GET /health`
- `GET /v1/models`
- `POST /v1/chat/completions`

### curl

```bash
curl http://127.0.0.1:8900/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "hi"}],
    "session_id": "my-session"
  }'
```

### Python (`openai`)

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8900/v1",
    api_key="dummy",
)

resp = client.chat.completions.create(
    model="adkbot",
    messages=[{"role": "user", "content": "hi"}],
    extra_body={"session_id": "my-session"},
)
print(resp.choices[0].message.content)
```

## 🐳 Docker

> [!TIP]
> The `-v ~/.adkbot:/root/.adkbot` flag mounts your local config directory into the container for persistence.

### Docker Compose

```bash
docker compose run --rm adkbot-cli onboard   # first-time setup
vim ~/.adkbot/config.json                     # add API keys
docker compose up -d adkbot-gateway           # start gateway
```

```bash
docker compose run --rm adkbot-cli agent -m "Hello!"   # run CLI
docker compose logs -f adkbot-gateway                   # view logs
docker compose down                                      # stop
```

### Docker

```bash
# Build the image
docker build -t adkbot .

# Initialize config (first time only)
docker run -v ~/.adkbot:/root/.adkbot --rm adkbot onboard

# Edit config on host to add API keys
vim ~/.adkbot/config.json

# Run gateway
docker run -v ~/.adkbot:/root/.adkbot -p 18790:18790 adkbot gateway

# Or run a single command
docker run -v ~/.adkbot:/root/.adkbot --rm adkbot agent -m "Hello!"
```

## 🐧 Linux Service

You can automatically run the gateway in the background on system boot using the built-in systemd installer.

**1. Install and start the system service:**

```bash
adkbot install-service
```

> **Note:** To keep the gateway running after you log out of SSH, enable user lingering:
> ```bash
> loginctl enable-linger $USER
> ```

**Common operations:**

```bash
systemctl --user status adkbot-gateway        # check status
systemctl --user restart adkbot-gateway       # restart after config changes
journalctl --user -u adkbot-gateway -f        # follow logs
```

## 📁 Project Structure

```
adkbot/
├── agent/          # 🧠 Core agent (ADK Agent + Runner)
│   ├── callbacks.py#    ADK lifecycle callbacks
│   ├── context.py  #    Prompt builder
│   ├── memory.py   #    Persistent memory
│   ├── skills.py   #    Skills loader
│   ├── subagent.py #    Background task execution
│   └── tools/      #    Built-in tools (10+ tools)
├── adkbot.py       # 🤖 Main AdkBot class (ADK Agent + Runner + LiteLLM)
├── skills/         # 🎯 Bundled skills
├── channels/       # 📱 Chat channel integrations (12+ channels)
├── bus/            # 🚌 Message routing
├── cron/           # ⏰ Scheduled tasks
├── heartbeat/      # 💓 Proactive wake-up
├── session/        # 💬 Conversation sessions
├── config/         # ⚙️ Configuration
├── security/       # 🔒 Safety guards & SSRF protection
└── cli/            # 🖥️ CLI commands
```

## 🤝 Contributing

PRs welcome! The codebase is intentionally readable and well-structured. 🤗

**Roadmap:**

- [ ] **Multi-modal** — See and hear (images, voice, video)
- [ ] **Long-term memory** — Never forget important context
- [ ] **Better reasoning** — Multi-step planning and reflection
- [ ] **More integrations** — Calendar, GitHub, and more
- [ ] **ADK Web UI** — Built-in web interface via `adk web`
- [ ] **Self-improvement** — Learn from feedback and mistakes

---

<p align="center">
  <em>By <a href="https://kiri.ng">Kiri Research Labs</a> <br>
  <em>Inspired by <a href="https://github.com/openclaw/openclaw">OpenClaw</a> <br>
  <sub>ADKBot is for educational, research, and technical exchange purposes only</sub>
</p>