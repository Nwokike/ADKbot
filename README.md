<div align="center">

  <img src="https://raw.githubusercontent.com/Nwokike/ADKbot/refs/heads/main/adkbot_logo.png" alt="adkbot" width="500">

  <h1>Multi-Model AI Assistant</h1>

  <p>
    <a href="https://pypi.org/project/adkbot/">
      <img src="https://img.shields.io/pypi/v/adkbot" alt="PyPI Version">
    </a>
    <a href="https://pepy.tech/project/adkbot">
      <img src="https://static.pepy.tech/badge/adkbot" alt="PyPI Downloads">
    </a>
    <img src="https://img.shields.io/badge/python-≥3.11-blue" alt="Python">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
    <img src="https://img.shields.io/badge/ADK-powered-orange" alt="ADK">
    <img src="https://img.shields.io/badge/LiteLLM-multi--model-purple" alt="LiteLLM">
  </p>

  <h3>⚠️ PROJECT ARCHIVED & DEPRECATED ⚠️</h3>

</div>

> **Notice:** This project is no longer actively maintained and has been archived in a read-only state.

## Why is this archived?

I initially built ADKBot as an exploratory project. However, the AI assistant landscape has grown incredibly fast, and there are now many robust, highly-supported alternatives available that already do exactly what this project aimed to achieve. 

Instead of continuing to maintain this in a highly competitive space without a long-term plan, I am archiving this repository to focus my time and energy on a brand new project. 

The code remains available here for historical, educational, and research purposes. Feel free to fork it or use snippets of the code, but please note that **no further updates, bug fixes, or support will be provided.**

---

## Legacy Documentation

<details>
<summary><b>Click here to view the original project documentation</b></summary>
## 🤖 ADKBot

ADKBot is a powerful, multi-model AI assistant framework built on Google's Agent Development Kit (ADK) with LiteLLM for universal model support.

ADKBot is an ADK-native project, built from the ground up to leverage ADK's agent architecture while preserving and extending a rich tooling and channel ecosystem.

---

## ⚡ Highlights

- Use any LLM provider (NVIDIA NIM, Gemini, Groq, OpenRouter, Anthropic, OpenAI, xAI, Ollama, and 50+ more) through a single unified interface  
- Connect to 12+ chat platforms (Telegram, Discord, WhatsApp, Slack, WeChat, and more)  
- Equipped with 10+ built-in tools (web search, file operations, shell commands, scheduled tasks, MCP support, and sub-agent spawning)

---

## 🧠 Key Features

- **ADK-Powered:** Built on Google's Agent Development Kit for robust agent lifecycle management, native callbacks, and session handling  
- **🌐 Multi-Model:** LiteLLM integration means you can use Claude, GPT, Gemini, DeepSeek, Llama, and 50+ other models without changing code  
- **🔧 Rich Tooling:** Web search (5 providers), file operations, shell execution, cron scheduling, MCP protocol support, and sub-agent spawning  
- **📱 12+ Chat Channels:** Telegram, Discord, WhatsApp, WeChat, Feishu, DingTalk, Slack, Matrix, Email, QQ, WeCom, and Mochat  
- **⏰ Scheduled Tasks:** Cron expressions, interval timers, and one-time scheduling with timezone support  
- **🔒 Security:** Workspace sandboxing, command safety guards, SSRF protection, and per-channel access control  
- **💎 Easy to Use:** One command to set up, one command to chat  

---

## 📚 Table of Contents

- Key Features  
- Install  
- Quick Start  
- Chat Apps  
- Configuration  
- Multiple Instances  
- CLI Reference  
- Python SDK  
- OpenAI-Compatible API  
- Docker  
- Linux Service  
- Project Structure  
- Contributing  

---

## 📦 Install

### With uv (recommended, fast):
```bash
uv tool install adkbot
````

### With pip:

```bash
pip install adkbot
```

The core install includes Telegram and WhatsApp out of the box. For other channels, install the extras you need:

```bash
# Install with Discord support
pip install "adkbot[discord]"

# Install with multiple channels
pip install "adkbot[discord,slack,feishu]"

# Install everything (all channels + tools)
pip install "adkbot[all]"
```

**Available extras:**
`discord, slack, feishu, dingtalk, qq, mochat, matrix, weixin, wecom, socks, api`

> **Note:** When configuring a channel during `adkbot onboard`, the wizard will automatically detect if its SDK is missing and offer to install it for you.

---

### From source

```bash
git clone https://github.com/nwokike/ADKbot.git
cd ADKbot
uv venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

uv sync --all-extras
```

---

### Termux (Android)

Python packages with native dependencies can cause build issues inside raw Termux. Use proot-distro to run a proper Linux distribution instead:

```bash
# Install proot-distro
pkg update && pkg upgrade
pkg install proot-distro

# Install and log into Ubuntu
proot-distro install ubuntu
proot-distro login ubuntu

# Inside Ubuntu
apt update && apt upgrade -y
apt install curl -y
curl -LsSf https://astral.sh/uv/install.sh | sh

echo 'export UV_LINK_MODE=copy' >> ~/.bashrc
source ~/.bashrc

# Install ADKBot
uv tool install adkbot
```

---

## 🔄 Update

### uv:

```bash
uv tool upgrade adkbot
adkbot --version
```

### pip:

```bash
pip install -U adkbot
adkbot --version
```

---

## 📋 Requirements

* Python >= 3.11
* An API key from any supported LLM provider

---

## 🚀 Quick Start

### [!TIP] Get API keys

* NVIDIA NIM (recommended, completely free, massive open-weight model catalog)
* Google Gemini (free tier available, best ADK integration, try gemini/gemma-4-31b-it practically impossible to hit the free limits)
* Groq (fastest inference, free tier)
* OpenRouter (access to many models via one key)
* Anthropic (Claude Opus 4.6)
* OpenAI (GPT 5.4)
* xAI (Grok 4.20)

API keys can be set as environment variables (e.g., `NVIDIA_NIM_API_KEY=nvapi-xxx`) or entered during the wizard.

---

### 1. Initialize

```bash
adkbot onboard
```

---

### 2. Configure (~/.adkbot/config.json)

```json
{
  "agents": {
    "defaults": {
      "model": "nvidia_nim/nvidia/nemotron-3-super-120b-a12b"
    }
  }
}
```

---

### 3. Chat

```bash
adkbot agent
```

That's it! You have a working AI assistant in 2 minutes.

---

## 💬 Chat Apps

Connect ADKBot to your favorite chat platform. Want to build your own? See the Channel Plugin Guide.

### Example: Telegram

#### 1. Create a bot

* Open Telegram, search `@BotFather`
* Send `/newbot`
* Copy the token

#### 2. Configure

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

#### 3. Run

```bash
adkbot gateway
```

---

## ⚙️ Configuration

Config file:

```
~/.adkbot/config.json
```

ADKBot uses LiteLLM, supporting 100+ providers via:

```
provider/model-name
```

Example:

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

---

## 🧩 Multiple Instances

```bash
adkbot onboard --config ~/.adkbot-telegram/config.json --workspace ~/.adkbot-telegram/workspace
adkbot onboard --config ~/.adkbot-discord/config.json --workspace ~/.adkbot-discord/workspace
```

Run:

```bash
adkbot gateway --config ~/.adkbot-telegram/config.json
adkbot gateway --config ~/.adkbot-discord/config.json
```

---

## 💻 CLI Reference

| Command        | Description         |
| -------------- | ------------------- |
| adkbot onboard | Initialize config   |
| adkbot agent   | Chat with the agent |
| adkbot gateway | Start gateway       |
| adkbot status  | Show status         |

---

## 🐍 Python SDK

```python
from adkbot import AdkBot

bot = AdkBot.from_config()
result = await bot.run("Summarize the README")
print(result.content)
```

---

## 🔌 OpenAI-Compatible API

```bash
pip install "adkbot[api]"
adkbot serve
```

---

## 🐳 Docker

```bash
docker build -t adkbot .

docker run -v ~/.adkbot:/root/.adkbot --rm adkbot onboard
docker run -v ~/.adkbot:/root/.adkbot -p 18790:18790 adkbot gateway
```

---

## 🐧 Linux Service

```bash
adkbot install-service
```

---

## 📁 Project Structure

```
adkbot/
├── agent/
├── adkbot.py
├── skills/
├── channels/
├── bus/
├── cron/
├── heartbeat/
├── session/
├── config/
├── security/
└── cli/
```

---

## 🤝 Contributing

PRs welcome! The codebase is intentionally readable and well-structured. 🤗

### Roadmap

* [ ] Multi-modal — See and hear (images, voice, video)
* [ ] Long-term memory — Never forget important context
* [ ] Better reasoning — Multi-step planning and reflection
* [ ] More integrations — Calendar, GitHub, and more
* [ ] ADK Web UI — Built-in web interface via adk web
* [ ] Self-improvement — Learn from feedback and mistakes

```
```
