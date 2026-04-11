"""Tests for the Pydantic configuration schema."""

from __future__ import annotations

from pathlib import Path

class TestSchemaDeadCodeRemoved:
    """Verify dead ModelConfig and its methods are removed from schema.py."""

    def test_no_model_config_class(self):
        """ModelConfig class should be removed."""
        src = Path("adkbot/config/schema.py").read_text(encoding="utf-8")
        assert "class ModelConfig" not in src

    def test_no_get_model_config(self):
        """get_model_config method should be removed."""
        src = Path("adkbot/config/schema.py").read_text(encoding="utf-8")
        assert "def get_model_config" not in src

    def test_config_still_imports(self):
        """Config should still be importable."""
        from adkbot.config.schema import Config
        c = Config()
        assert c.agents.defaults.model is not None
