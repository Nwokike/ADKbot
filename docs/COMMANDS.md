# ADKBot CLI Commands

The `adkbot` Command Line Interface (CLI) provides a set of tools to initialize, configure, and interact with your personal AI assistant. This document provides an overview of the available commands.

## Basic Usage

```bash
adkbot [OPTIONS] COMMAND [ARGS]...
```

For general help, you can run:
```bash
adkbot --help
```

---

## Commands

### `adkbot onboard`
Launches the interactive configuration wizard. This is the recommended way to set up ADKBot for the first time.

- **Description:** Guides you through selecting your preferred Large Language Model (e.g., Gemini, NVIDIA NIM, OpenAI, Anthropic, or local models), configuring the essential API keys, and setting basic agent parameters like temperature and max tool iterations. By default, it will detect existing configurations and let you refresh or overwrite them.
- **Options:**
  - `--skip-wizard`: Skips the interactive wizard and generates a default configuration file instead (useful for manual editing).
  - `--config <path>`: Specifies a custom path to save/load the configuration.
  - `--workspace <path>`: Sets a custom workspace directory for the agent to operate in.

---

### `adkbot init`
Initializes a new ADKBot configuration and workspace *without* running the interactive wizard.

- **Description:** Creates the default `.adkbot` folder in your home directory along with `config.json` and `.env` files. It essentially acts like `adkbot onboard --skip-wizard`.
- **Options:**
  - `--workspace <path>`: Specifies the default workspace path for ADKBot.
  - `--config <path>`: Alternative path for the configuration file.

---

### `adkbot agent`
Starts the interactive CLI chat with your AI assistant.

- **Description:** This drops you into a chat interface directly in your terminal, connecting you to the LLM specified in your configuration. The agent operates within the configured workspace and can execute tools, read local files, and run commands.
- **Aliases:** `adkbot chat`
- **Options:**
  - `-m, --message <text>`: Send an initial message to the agent immediately upon starting. For example: `adkbot agent -m "Summarize the project"`
  - `--workspace <path>`: Temporarily override the configured workspace for this session.

---

### `adkbot gateway`
Starts the ADKBot server (Matrix bridge) for external chat integrations.

- **Description:** This command spins up the backend that allows your ADKBot agent to communicate over Matrix. This is required if you want to use ADKBot via Telegram, WhatsApp, or other third-party messaging apps bridged through Matrix.
- **Aliases:** `adkbot bot`, `adkbot server`
- **Options:**
  - `--config <path>`: Path to the configuration file to load.

---

## Examples

**1. Initial Setup**
```bash
adkbot onboard
```

**2. Quick Question in Terminal**
```bash
adkbot agent -m "What files are in the current directory?"
```

**3. Starting the Matrix Integration**
```bash
adkbot gateway
```
