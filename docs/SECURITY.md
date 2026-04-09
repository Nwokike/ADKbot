# Security Policy

## Supported Versions

Currently, ADKBot is in the **Alpha** phase (v0.1.0). We provide security updates for the current major release. 

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| < 0.1.0 | :x:                |

## Reporting a Vulnerability

Your security is important to us. If you discover a vulnerability in ADKBot:

1. **Please do not open a public GitHub issue.** This ensures bad actors don’t exploit it before we have a chance to fix it.
2. Direct all security reports and concerns securely via email to **onyeka@kiri.ng**.
3. In your email, please include:
   - A detailed description of the vulnerability.
   - Steps to reproduce the issue.
   - The potential impact.
   - Suggested mitigations if you have them.

We aim to respond to all reports within 48 hours.

## Best Practices for Users

Since ADKBot acts as a powerful Autonomous AI Agent with system-level capabilities, you must follow basic security hygiene:

* **API Keys**: ADKBot stores your API keys inside `~/.adkbot/.env`. Ensure only the creator account on your OS can read this directory. Never commit your `.env` configuration to source control and never share it.
* **Privilege Level**: **Never run ADKBot as a root/administrator user.** Give the ADKBot process only the minimal filesystem permissions required for the tasks you intend it to perform.
* **Skill Auditing**: Be cautious when installing new skills from ClawHub (`npx clawhub`). While ClawHub is a fantastic ecosystem, always verify what a skill does before blindly allowing it to execute code on your machine.
* **Network Binding**: Default local ports are bound to `127.0.0.1`. Do not expose ADKBot's internal APIs or bridges directly to the public internet without a reverse proxy and proper authentication.
