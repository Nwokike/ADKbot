"""Tests for the ADK tool registry."""

from __future__ import annotations

from pathlib import Path

class TestMcpConfigPath:
    """Verify MCP servers are loaded from the correct config path."""

    def test_mcp_uses_correct_config_path(self):
        """Verify config.tools.mcp_servers is used (not config.tools.mcp.servers)."""
        src = Path("adkbot/agent/tools/registry.py").read_text(encoding="utf-8")
        assert "config.tools.mcp_servers" in src
        assert "config.tools.mcp.servers" not in src
