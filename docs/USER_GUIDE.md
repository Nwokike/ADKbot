# ADKBot User Guide

Welcome to ADKBot! This guide is written for non-technical users to get up and running quickly.

ADKBot is your personal AI assistant. It connects directly to your favorite messaging apps (like Telegram, Discord, and WhatsApp) and handles tasks efficiently using various AI providers like Google Gemini, Anthropic Claude, and more.

## Getting Started

### 1. Installation

If you're reading this, you likely already have the files. You just need to install ADKBot.
Open your terminal or command prompt and run:
```bash
pip install -e .
```

### 2. Onboarding

We've designed a simple walkthrough wizard to get you set up. Run the following command:
```bash
adkbot onboard
```

The wizard will ask you:
1. Which AI model you want to use (e.g. Gemini 2.0 Flash, Claude 3.5 Sonnet, Gemma 4).
2. Your API key for that model (it will provide a link where you can sign up and get one for free or cheap).
3. Where to store your configuration.

Your API keys are safely stored in your own computer (`~/.adkbot/.env`).

### 3. Choose Your Channels

Where do you want to talk to your bot? ADKBot supports several platforms:

*   **Telegram**: Talk to the bot right from your phone.
*   **Discord**: Bring the bot into your server or talk to it directly.
*   **WhatsApp**: Connect it to your WhatsApp account.
*   **CLI**: Talk to it directly in the terminal!

To configure a channel, simply run the onboarding process, or edit the `~/.adkbot/config.json` manually if you feel adventurous. 
For interactive platforms like Telegram and Discord, you will need a API token:
- Telegram: Go to Telegram, search `@BotFather`, create a new bot, and copy the "token".
- Discord: Go to the Discord Developer Portal, create an App, add a Bot, and copy the token.

### 4. Start the Bot

Once configured, simply run:
```bash
adkbot gateway
```
Your bot is now alive! Send it a message on your chosen channel.

## Skills

ADKBot can learn new things! You can add skills via **ClawHub**.
To explore what ADKBot can do, you can search for skills (e.g., web scraping, email reading) and install them.

For more details on skills, check out the `adkbot/skills` folder.

## Troubleshooting

- **Bot is not answering:** Ensure `adkbot gateway` is running in your terminal.
- **Commands failing:** Ensure your API key has enough credits and is correctly set in your environment.
- **Support:** Feel free to open an issue on [GitHub](https://github.com/nwokike/ADKbot) or reach out via email to onyeka@kiri.ng.
