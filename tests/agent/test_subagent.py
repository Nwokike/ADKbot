"""Tests for the ADK Subagent runner logic."""

from __future__ import annotations

from pathlib import Path
import pytest

class TestSubagentAwait:
    """Verify create_session must be awaited in subagent.py."""

    def test_create_session_is_awaited_in_source(self):
        """Verify the source contains 'await session_service.create_session'."""
        src = Path("adkbot/agent/subagent.py").read_text(encoding="utf-8")
        assert "await session_service.create_session(" in src
        # Must NOT have a bare (non-awaited) call
        lines = src.split("\n")
        for line in lines:
            stripped = line.strip()
            if "session_service.create_session(" in stripped and "await" not in stripped:
                if not stripped.startswith("#") and not stripped.startswith('"'):
                    pytest.fail(f"Found non-awaited create_session call: {stripped}")

class TestSubagentBusPublish:
    """Verify subagent uses correct bus methods."""

    def test_no_generic_bus_publish_calls(self):
        """Verify no bus.publish('outbound', ...) calls remain."""
        src = Path("adkbot/agent/subagent.py").read_text(encoding="utf-8")
        assert 'bus.publish("outbound"' not in src
        assert "bus.publish('outbound'" not in src
        assert "bus.publish_outbound(" in src
