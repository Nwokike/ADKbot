"""Message tool for sending messages to users.

Converted to ADK function-tool pattern. Uses ToolContext to access
the channel send callback stored in session state.
"""

from __future__ import annotations

from typing import Any

from google.adk.tools import ToolContext
from loguru import logger


async def send_message(
    content: str,
    media: list[str] | None = None,
    channel: str = "",
    chat_id: str = "",
    tool_context: ToolContext = None,
) -> dict:
    """Send a message to the user, optionally with file attachments.

    This is the ONLY way to deliver files (images, documents, audio, video)
    to the user. Use the 'media' parameter with file paths to attach files.
    Do NOT use read_file to send files — that only reads content for analysis.

    Args:
        content: The message content to send.
        media: Optional list of file paths to attach (images, audio, documents).
        channel: Optional target channel (telegram, discord, etc.). Auto-detected if not set.
        chat_id: Optional target chat/user ID. Auto-detected if not set.

    Returns:
        A dict with success message or error.
    """
    # Get channel context from session state (set by the channel gateway)
    state = tool_context.state if tool_context else {}
    channel = channel or state.get("_channel", "")
    chat_id = chat_id or state.get("_chat_id", "")
    message_id = state.get("_message_id")

    if not channel or not chat_id:
        return {"error": "No target channel/chat specified"}

    # Get the send callback from state (injected by channel gateway)
    send_callback = state.get("_send_callback")
    if not send_callback:
        # In CLI mode, just return the content as the response
        return {"result": f"Message prepared for {channel}:{chat_id}", "content": content}

    try:
        from adkbot.bus.events import OutboundMessage

        # Only inherit message_id when targeting the same channel+chat
        default_channel = state.get("_channel", "")
        default_chat_id = state.get("_chat_id", "")
        if channel != default_channel or chat_id != default_chat_id:
            message_id = None

        msg = OutboundMessage(
            channel=channel,
            chat_id=chat_id,
            content=content,
            media=media or [],
            metadata={"message_id": message_id} if message_id else {},
        )

        await send_callback(msg)
        media_info = f" with {len(media)} attachments" if media else ""
        return {"result": f"Message sent to {channel}:{chat_id}{media_info}"}
    except Exception as e:
        return {"error": f"Error sending message: {e}"}


