"""Tests for the AdkBot programmatic facade."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from adkbot.adkbot import AdkBot, RunResult
from google.genai import types


def _write_config(tmp_path: Path, overrides: dict | None = None) -> Path:
    data = {
        "providers": {"openrouter": {"apiKey": "sk-test-key"}},
        "agents": {"defaults": {"model": "openai/gpt-4.1"}},
    }
    if overrides:
        data.update(overrides)
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(data))
    return config_path


def test_from_config_missing_file():
    with pytest.raises(FileNotFoundError):
        AdkBot.from_config("/nonexistent/config.json")


def test_from_config_creates_instance(tmp_path):
    config_path = _write_config(tmp_path)
    bot = AdkBot.from_config(config_path, workspace=tmp_path)
    assert bot.runner is not None
    assert str(bot.workspace) == str(tmp_path)


def test_from_config_default_path():
    from adkbot.config.schema import Config

    with patch("adkbot.config.loader.load_config") as mock_load, \
         patch("adkbot.adkbot.Agent") as _mock_agent, \
         patch("adkbot.adkbot._load_tools") as mock_tools:
        mock_load.return_value = Config()
        mock_tools.return_value = []
        AdkBot.from_config()
        mock_load.assert_called_once_with(None)


@pytest.mark.asyncio
async def test_run_returns_result(tmp_path):
    config_path = _write_config(tmp_path)
    bot = AdkBot.from_config(config_path, workspace=tmp_path)

    # Mock the generator returned by run_async
    async def mock_run_async(*args, **kwargs):
        class MockEvent:
            def is_final_response(self):
                return True
            @property
            def content(self):
                return types.Content(parts=[types.Part(text="Hello back!")])
        yield MockEvent()

    bot.runner.run_async = mock_run_async

    result = await bot.run("hi")

    assert isinstance(result, RunResult)
    assert result.content == "Hello back!"


def test_workspace_override(tmp_path):
    config_path = _write_config(tmp_path)
    custom_ws = tmp_path / "custom_workspace"
    custom_ws.mkdir()

    bot = AdkBot.from_config(config_path, workspace=custom_ws)
    assert str(bot.workspace) == str(custom_ws)


def test_sdk_make_provider_uses_github_copilot_backend():
    from adkbot.config.schema import Config
    from adkbot.adkbot import _create_litellm_model

    config = Config.model_validate(
        {
            "agents": {
                "defaults": {
                    "provider": "github-copilot",
                    "model": "github-copilot/gpt-4.1",
                }
            }
        }
    )

    model = _create_litellm_model(config)
    assert "github-copilot" in model.model


def test_import_from_top_level():
    from adkbot import AdkBot as N, RunResult as R
    assert N is AdkBot
    assert R is RunResult
