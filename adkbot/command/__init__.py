"""Slash command routing and built-in handlers."""

from adkbot.command.builtin import register_builtin_commands
from adkbot.command.router import CommandContext, CommandRouter

__all__ = ["CommandContext", "CommandRouter", "register_builtin_commands"]
