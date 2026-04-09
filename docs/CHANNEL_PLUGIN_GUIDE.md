# ADKBot Channel Plugin Guide

An ADKBot "Channel plugin" allows your agent to talk to different messaging platforms across the web.

Out of the box, ADKBot implements Telegram, Discord, and a CLI loop. But it's trivial to add your own, like Slack, Matrix, or a custom Webhook!

## Concept

ADKBot uses Python entry points to discover and bind instances of classes that subclass `BaseChannel`. During the `adkbot gateway` startup sequence, any enabled channels listen on the ADKBot event bus.

## Writing a Custom Webhook Channel

Let's assume you want to create a generic HTTP POST Webhook channel.

### 1. Minimal Implementation

Create your channel python script:

```python
# my_webhook_channel.py
import asyncio
from aiohttp import web
from loguru import logger
from adkbot.channels.base import BaseChannel
from adkbot.bus.events import OutboundMessage

class WebhookChannel(BaseChannel):
    name = "webhook"          # The identifier shown in CLI
    display_name = "Webhook"  # Pretty display name

    @classmethod
    def default_config(cls) -> dict:
        return {"enabled": False, "port": 9000, "allowFrom": []}

    async def start(self) -> None:
        """Starts the listener loop"""
        self._running = True
        port = self.config.get("port", 9000)

        app = web.Application()
        app.router.add_post("/message", self._on_request)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        
        logger.info(f"Webhook channel active on port {port}")

        # Block loop holding channel alive
        while self._running:
            await asyncio.sleep(1)
        await runner.cleanup()

    async def stop(self) -> None:
        """Kills the listener loop"""
        self._running = False

    async def send(self, msg: OutboundMessage) -> None:
        """Handles agent -> user execution delivery"""
        logger.info(f"[Webhook outbound to {msg.chat_id}]: {msg.content}")
        # Build your custom delivery logic here

    async def _on_request(self, request: web.Request) -> web.Response:
        """Handles user -> agent incoming pings"""
        body = await request.json()
        
        # Fire message back onto the ADKBot Global Bus!
        await self._handle_message(
            sender_id=body.get("sender", "anon"),
            chat_id=body.get("chat_id", "anon"),
            content=body.get("text", "")
        )
        return web.json_response({"ok": True})
```

### 2. Registration

Create your `pyproject.toml` and register the `adkbot.channels` entry point.

```toml
[project]
name = "adkbot-channel-webhook"
version = "0.1.0"
dependencies = ["adkbot", "aiohttp"]

[project.entry-points."adkbot.channels"]
webhook = "my_webhook_channel:WebhookChannel"

[build-system]
requires = ["setuptools"]
build-backend = "setuptools.backends._legacy:_Backend"
```

### 3. Deploying 

Run:
```bash
pip install -e .
```

Now, check the plugins list via the ADKBot CLI:

```bash
adkbot plugins list
```

Enable your webhook in `~/.adkbot/config.json`:

```json
{
  "channels": {
    "webhook": {
      "enabled": true,
      "port": 9000
    }
  }
}
```

Now, when you run `adkbot gateway`, your custom server will be actively responding and sending payloads to the ADKBot cognitive brain engine!
