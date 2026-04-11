# ADKBot Python SDK

Harness the power of ADKBot within your own Python applications.

ADKBot provides a complete Software Development Kit (SDK) wrapping Google's Agent Development Kit (ADK) and LiteLLM, allowing you to instantiate autonomous agents, run custom pipelines, and utilize powerful callback hooks.

## Installation

Ensure you have ADKBot installed in your environment:

```bash
pip install adkbot
# Or with all extras:
pip install "adkbot[all]"
```

## Quick Start

It's extremely simple to generate an ADKBot instance from code:

```python
import asyncio
from adkbot import AdkBot

async def main():
    # Load default configuration and credentials from ~/.adkbot/.env
    bot = AdkBot.from_config()
    
    # Run a simple message inference
    result = await bot.run("Summarize the theory of relativity in 2 sentences.")
    print(f"ADKBot Response: {result.content}")
    print(f"Tools Invoked: {result.tools_used}")

if __name__ == "__main__":
    asyncio.run(main())
```

## Core API Reference

### `AdkBot.from_config(config_path=None, workspace=None)`
Instantiates the primary agent builder. If unprovided, configuration gracefully falls back to `~/.adkbot/config.json`.

*   `config_path`: Optional path to force a custom JSON configuration.
*   `workspace`: Overrides the default execution workspace directory.

### `bot.run(message: str, session_key: str = "default", callbacks: dict = None)`
Asynchronously execute an evaluation chain given the User's message.

*   `message`: The prompt instructions.
*   `session_key`: Used for isolated memory channels (great for multi-user bots!).
*   `callbacks`: Powerful ADK injection points to interrupt or augment the agent chain.

## Understanding Callbacks

The `bot.run` command accepts Google ADK native callbacks to tap into the execution loop.

| Callback Type | Description |
| :--- | :--- |
| `before_agent_callback` | Triggered the moment your prompt is received. |
| `after_agent_callback` | Triggered when the agent finalizes output generation. |
| `before_model_callback` | Triggered just prior to LiteLLM payload transmission. |
| `after_model_callback` | Triggered immediately post-LiteLLM stream aggregation. |
| `before_tool_callback` | Triggered right before the agent fires a tool (e.g. `execute_command`). |
| `after_tool_callback` | Triggered directly after a tool returns a result. |

### Example: Tool Execution Audit

You can inject auditing capabilities seamlessly:

```python
async def log_before_tool(tool, args, context):
    print(f"[AUDIT] ADKBot is attempting to execute: {tool.name} with {args}")
    return None # Proceed as normal

async def main():
    bot = AdkBot.from_config()
    await bot.run(
        "List all txt files in the current directory",
        callbacks={
            "before_tool_callback": log_before_tool
        }
    )
```

## Configuration & Environment Let-throughs

ADKBot maps LiteLLM routing via local environment variables. The SDK operates exactly the same as the CLI wizard regarding API keys. 

Key Environment Map:
*   `GEMINI_API_KEY`: Used by default `gemini/gemini-3.1-pro-preview`
*   `NVIDIA_NIM_API_KEY`: NVIDIA NIM models
*   `OPENAI_API_KEY`
*   `ANTHROPIC_API_KEY`
*   `GROQ_API_KEY`
*   `GROK_API_KEY`: xAI Grok models

> **Note:** ADKBot uses LiteLLM which supports 100+ providers. Known providers have their API keys automatically resolved from `~/.adkbot/.env`. For providers not in the built-in map, set `apiKey` directly in `config.json`.

To force settings via code:

```python
import os
os.environ["GEMINI_API_KEY"] = "your_actual_token"
```

*For more advanced capabilities or deploying custom routers, refer to the ADK Documentation under `google.adk`.*