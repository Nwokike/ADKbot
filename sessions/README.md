# ADKBot Memory Sessions

This directory contains autonomous memory stores.

Whenever ADKBot communicates with a user on platforms like Telegram, Discord, CLI, or WhatsApp, it records the context of the conversation here in `.jsonl` files (e.g. `telegram_123456.jsonl`).

**Why is it here?**
Unlike standard CLI tools, AI Agents need "memory" to understand follow-up questions. This directory acts as the local brain storage. You can freely delete files in here to wipe the bot's memory of a specific conversation context.
