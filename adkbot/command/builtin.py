"""Built-in slash command handlers."""

from __future__ import annotations

import asyncio
import os
import sys

from adkbot import __version__
from adkbot.bus.events import OutboundMessage
from adkbot.command.router import CommandContext, CommandRouter
from adkbot.utils.helpers import build_status_content


async def cmd_stop(ctx: CommandContext) -> OutboundMessage:
    """Cancel all active tasks and subagents for the session."""
    loop = ctx.loop
    msg = ctx.msg
    tasks = loop._active_tasks.pop(msg.session_key, [])
    cancelled = sum(1 for t in tasks if not t.done() and t.cancel())
    for t in tasks:
        try:
            await t
        except (asyncio.CancelledError, Exception):
            pass
    sub_cancelled = await loop.subagents.cancel_by_session(msg.session_key)
    total = cancelled + sub_cancelled
    content = f"Stopped {total} task(s)." if total else "No active task to stop."
    return OutboundMessage(channel=msg.channel, chat_id=msg.chat_id, content=content)


async def cmd_restart(ctx: CommandContext) -> OutboundMessage:
    """Restart the process in-place via os.execv."""
    msg = ctx.msg

    async def _do_restart():
        await asyncio.sleep(1)
        os.execv(sys.executable, [sys.executable, "-m", "adkbot"] + sys.argv[1:])

    asyncio.create_task(_do_restart())
    return OutboundMessage(channel=msg.channel, chat_id=msg.chat_id, content="Restarting...")


async def cmd_status(ctx: CommandContext) -> OutboundMessage:
    """Build an outbound status message for a session."""
    loop = ctx.loop
    session = ctx.session or loop.sessions.get_or_create(ctx.key)
    ctx_est = 0
    try:
        ctx_est, _ = loop.memory_consolidator.estimate_session_prompt_tokens(session)
    except Exception:
        pass
    if ctx_est <= 0:
        ctx_est = loop._last_usage.get("prompt_tokens", 0)
    return OutboundMessage(
        channel=ctx.msg.channel,
        chat_id=ctx.msg.chat_id,
        content=build_status_content(
            version=__version__, model=loop.model,
            start_time=loop._start_time, last_usage=loop._last_usage,
            context_window_tokens=loop.context_window_tokens,
            session_msg_count=len(session.get_history(max_messages=0)),
            context_tokens_estimate=ctx_est,
        ),
        metadata={"render_as": "text"},
    )


async def cmd_new(ctx: CommandContext) -> OutboundMessage:
    """Start a fresh session."""
    loop = ctx.loop
    session = ctx.session or loop.sessions.get_or_create(ctx.key)
    snapshot = session.messages[session.last_consolidated:]
    session.clear()
    loop.sessions.save(session)
    loop.sessions.invalidate(session.key)
    if snapshot:
        loop._schedule_background(loop.memory_consolidator.archive_messages(snapshot))
    return OutboundMessage(
        channel=ctx.msg.channel, chat_id=ctx.msg.chat_id,
        content="New session started.",
    )


async def cmd_help(ctx: CommandContext) -> OutboundMessage:
    """Return available slash commands."""
    return OutboundMessage(
        channel=ctx.msg.channel,
        chat_id=ctx.msg.chat_id,
        content=build_help_text(),
        metadata={"render_as": "text"},
    )


async def cmd_model(ctx: CommandContext) -> OutboundMessage:
    """Show the current model or switch to a new one.

    Usage:
        /model           — Show the current model
        /model <name>    — Switch to a new model
    """
    loop = ctx.loop
    msg = ctx.msg
    new_model = ctx.args.strip() if ctx.args else ""

    if not new_model:
        # Show current model
        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=f"🤖 Current model: `{loop.model}`",
            metadata={"render_as": "text"},
        )

    # Switch model
    old_model = loop.model
    loop.model = new_model
    return OutboundMessage(
        channel=msg.channel,
        chat_id=msg.chat_id,
        content=f"✅ Model changed: `{old_model}` → `{new_model}`",
        metadata={"render_as": "text"},
    )


async def cmd_version(ctx: CommandContext) -> OutboundMessage:
    """Show the bot version."""
    return OutboundMessage(
        channel=ctx.msg.channel,
        chat_id=ctx.msg.chat_id,
        content=f"🤖 ADKBot v{__version__}",
        metadata={"render_as": "text"},
    )


async def cmd_ping(ctx: CommandContext) -> OutboundMessage:
    """Reply with pong — useful for checking if the bot is alive."""
    return OutboundMessage(
        channel=ctx.msg.channel,
        chat_id=ctx.msg.chat_id,
        content="🏓 Pong!",
        metadata={"render_as": "text"},
    )


def build_help_text() -> str:
    """Build canonical help text shared across channels."""
    lines = [
        "🤖 adkbot commands:",
        "/new — Start a new conversation",
        "/stop — Stop the current task",
        "/model — Show or switch the active model",
        "/status — Show bot status",
        "/version — Show bot version",
        "/ping — Check if the bot is alive",
        "/restart — Restart the bot",
        "/help — Show available commands",
    ]
    return "\n".join(lines)


def register_builtin_commands(router: CommandRouter) -> None:
    """Register the default set of slash commands."""
    router.priority("/stop", cmd_stop)
    router.priority("/restart", cmd_restart)
    router.priority("/status", cmd_status)
    router.exact("/new", cmd_new)
    router.exact("/help", cmd_help)
    router.exact("/version", cmd_version)
    router.exact("/ping", cmd_ping)
    # /model uses prefix so "/model gemini/..." works
    router.prefix("/model", cmd_model)

