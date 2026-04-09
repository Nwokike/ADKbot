import pytest

from adkbot.agent.tools.message import send_message


@pytest.mark.asyncio
async def test_message_tool_returns_error_when_no_target_context() -> None:
    result = await send_message(content="test")
    assert "error" in result
    assert "target" in result["error"].lower() or "channel" in result["error"].lower()
