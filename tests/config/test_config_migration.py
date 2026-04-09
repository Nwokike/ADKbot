"""Unit tests for config path resolution and migration logic."""

import json
from pathlib import Path

import pytest

from adkbot.config.loader import load_config, save_config
from adkbot.config.paths import (
    ADKBOT_HOME_ENV,
    XDG_CONFIG_HOME_ENV,
    _get_app_dir,
    get_config_path,
)
from adkbot.config.schema import Config


def test_xdg_config_home_takes_precedence(monkeypatch):
    """Test that XDG_CONFIG_HOME is used if set."""
    monkeypatch.setenv(XDG_CONFIG_HOME_ENV, "/mock/xdg/config")
    # Ensure ADKBOT_HOME isn't interfering
    monkeypatch.delenv(ADKBOT_HOME_ENV, raising=False)

    app_dir = _get_app_dir()
    assert app_dir == Path("/mock/xdg/config/adkbot")

    config_path = get_config_path()
    assert config_path == Path("/mock/xdg/config/adkbot/config.json")


def test_adkbot_home_takes_precedence_over_xdg(monkeypatch):
    """Test that ADKBOT_HOME overrides XDG_CONFIG_HOME."""
    monkeypatch.setenv(XDG_CONFIG_HOME_ENV, "/mock/xdg/config")
    monkeypatch.setenv(ADKBOT_HOME_ENV, "/mock/adkbot/home")

    app_dir = _get_app_dir()
    assert app_dir == Path("/mock/adkbot/home")

    config_path = get_config_path()
    assert config_path == Path("/mock/adkbot/home/config.json")


def test_load_config_keeps_max_tokens_and_ignores_legacy_memory_window(tmp_path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "agents": {
                    "defaults": {
                        "maxTokens": 1234,
                        "memoryWindow": 42,
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)
    assert config.agents.defaults.max_tokens == 1234
    assert config.agents.defaults.context_window_tokens == 128_000  # New default
    assert not hasattr(config.agents.defaults, "memory_window")


def test_save_config_writes_context_window_tokens_but_not_memory_window(tmp_path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "agents": {
                    "defaults": {
                        "maxTokens": 2222,
                        "memoryWindow": 30,
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)
    save_config(config, config_path)
    saved = json.loads(config_path.read_text(encoding="utf-8"))
    defaults = saved["agents"]["defaults"]
    assert defaults["maxTokens"] == 2222
    assert defaults["contextWindowTokens"] == 128_000  # New default
    assert "memoryWindow" not in defaults


def test_onboard_does_not_crash_with_legacy_memory_window(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "config.json"
    workspace = tmp_path / "workspace"
    config_path.write_text(
        json.dumps(
            {
                "agents": {
                    "defaults": {
                        "maxTokens": 3333,
                        "memoryWindow": 50,
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr("adkbot.config.loader.get_config_path", lambda: config_path)
    monkeypatch.setattr("adkbot.cli.commands.get_workspace_path", lambda _workspace=None: workspace)

    from typer.testing import CliRunner

    from adkbot.cli.commands import app

    runner = CliRunner()
    # Wizard is default, bypass it using --skip-wizard. 'N' answers "Refresh config?"
    result = runner.invoke(app, ["onboard", "--skip-wizard"], input="N\n")
    assert result.exit_code == 0


def test_onboard_refresh_backfills_missing_channel_fields(tmp_path, monkeypatch) -> None:
    from types import SimpleNamespace

    config_path = tmp_path / "config.json"
    workspace = tmp_path / "workspace"
    config_path.write_text(
        json.dumps(
            {
                "channels": {
                    "qq": {
                        "enabled": False,
                        "appId": "",
                        "secret": "",
                        "allowFrom": [],
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr("adkbot.config.loader.get_config_path", lambda: config_path)
    monkeypatch.setattr("adkbot.cli.commands.get_workspace_path", lambda _workspace=None: workspace)
    monkeypatch.setattr(
        "adkbot.channels.registry.discover_all",
        lambda: {
            "qq": SimpleNamespace(
                default_config=lambda: {
                    "enabled": False,
                    "appId": "",
                    "secret": "",
                    "allowFrom": [],
                    "msgFormat": "plain",
                }
            )
        },
    )

    from typer.testing import CliRunner

    from adkbot.cli.commands import app

    runner = CliRunner()
    # Wizard is default, bypass it using --skip-wizard. 'N' answers "Refresh config?"
    result = runner.invoke(app, ["onboard", "--skip-wizard"], input="N\n")
    assert result.exit_code == 0

    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["channels"]["qq"]["msgFormat"] == "plain"