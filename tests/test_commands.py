"""Tests for built-in slash commands."""

from __future__ import annotations

from pathlib import Path

class TestStatusSingleRegistration:
    """Verify /status is only registered once in the command router."""

    def test_status_registered_once(self):
        """Verify /status is registered in priority tier only."""
        src = Path("adkbot/command/builtin.py").read_text(encoding="utf-8")
        # Count all /status registrations
        status_lines = [
            line.strip()
            for line in src.split("\n")
            if '"/status"' in line and line.strip().startswith("router.")
        ]
        assert len(status_lines) == 1, f"Expected 1 /status registration, got {len(status_lines)}: {status_lines}"
        assert "priority" in status_lines[0]
