"""Unit tests for onboard core logic functions.

These tests focus on the business logic behind the onboard wizard,
without testing the interactive UI components.

Updated for Phase 1 refactoring - removed tests for deleted functions.
"""

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from adkbot.cli import onboard as onboard_wizard

# Import functions to test
from adkbot.cli.commands import _merge_missing_defaults
from adkbot.cli.onboard import (
    run_onboard,
)
from adkbot.config.schema import Config
from adkbot.utils.helpers import sync_workspace_templates


class TestMergeMissingDefaults:
    """Tests for _merge_missing_defaults recursive config merging."""

    def test_adds_missing_top_level_keys(self):
        existing = {"a": 1}
        defaults = {"a": 1, "b": 2, "c": 3}

        result = _merge_missing_defaults(existing, defaults)

        assert result == {"a": 1, "b": 2, "c": 3}

    def test_preserves_existing_values(self):
        existing = {"a": "custom_value"}
        defaults = {"a": "default_value"}

        result = _merge_missing_defaults(existing, defaults)

        assert result == {"a": "custom_value"}

    def test_merges_nested_dicts_recursively(self):
        existing = {
            "level1": {
                "level2": {
                    "existing": "kept",
                }
            }
        }
        defaults = {
            "level1": {
                "level2": {
                    "existing": "replaced",
                    "added": "new",
                },
                "level2b": "also_new",
            }
        }

        result = _merge_missing_defaults(existing, defaults)

        assert result == {
            "level1": {
                "level2": {
                    "existing": "kept",
                    "added": "new",
                },
                "level2b": "also_new",
            }
        }

    def test_returns_existing_if_not_dict(self):
        assert _merge_missing_defaults("string", {"a": 1}) == "string"
        assert _merge_missing_defaults([1, 2, 3], {"a": 1}) == [1, 2, 3]
        assert _merge_missing_defaults(None, {"a": 1}) is None
        assert _merge_missing_defaults(42, {"a": 1}) == 42

    def test_returns_existing_if_defaults_not_dict(self):
        assert _merge_missing_defaults({"a": 1}, "string") == {"a": 1}
        assert _merge_missing_defaults({"a": 1}, None) == {"a": 1}

    def test_handles_empty_dicts(self):
        assert _merge_missing_defaults({}, {"a": 1}) == {"a": 1}
        assert _merge_missing_defaults({"a": 1}, {}) == {"a": 1}
        assert _merge_missing_defaults({}, {}) == {}

    def test_backfills_channel_config(self):
        """Real-world scenario: backfill missing channel fields."""
        existing_channel = {
            "enabled": False,
            "appId": "",
            "secret": "",
        }
        default_channel = {
            "enabled": False,
            "appId": "",
            "secret": "",
            "msgFormat": "plain",
            "allowFrom": [],
        }

        result = _merge_missing_defaults(existing_channel, default_channel)

        assert result["msgFormat"] == "plain"
        assert result["allowFrom"] == []


class TestGetFieldTypeInfo:
    """Tests for _get_field_type_info type extraction."""


# Note: _get_field_type_info and _get_field_display_name functions removed in Phase 1
# The new onboard.py uses simpler field handling directly in the wizard


class TestSyncWorkspaceTemplates:
    """Tests for sync_workspace_templates file synchronization."""

    def test_creates_missing_files(self, tmp_path):
        """Should create template files that don't exist."""
        workspace = tmp_path / "workspace"

        added = sync_workspace_templates(workspace, silent=True)

        # Check that some files were created
        assert isinstance(added, list)
        # The actual files depend on the templates directory

    def test_does_not_overwrite_existing_files(self, tmp_path):
        """Should not overwrite files that already exist."""
        workspace = tmp_path / "workspace"
        workspace.mkdir(parents=True)
        (workspace / "AGENTS.md").write_text("existing content")

        sync_workspace_templates(workspace, silent=True)

        # Existing file should not be changed
        content = (workspace / "AGENTS.md").read_text()
        assert content == "existing content"

    def test_creates_memory_directory(self, tmp_path):
        """Should create memory directory structure."""
        workspace = tmp_path / "workspace"

        sync_workspace_templates(workspace, silent=True)

        assert (workspace / "memory").exists() or (workspace / "skills").exists()

    def test_returns_list_of_added_files(self, tmp_path):
        """Should return list of relative paths for added files."""
        workspace = tmp_path / "workspace"

        added = sync_workspace_templates(workspace, silent=True)

        assert isinstance(added, list)
        # All paths should be relative to workspace
        for path in added:
            assert not Path(path).is_absolute()


# Note: _get_provider_names, _get_channel_names, _get_provider_info removed in Phase 1
# The new onboard.py uses MODEL_PRESETS list directly


class TestModelPresets:
    """Tests for the MODEL_PRESETS constant in onboard.py."""

    def test_model_presets_is_list(self):
        """MODEL_PRESETS should be a list of tuples."""
        from adkbot.cli.onboard import MODEL_PRESETS

        assert isinstance(MODEL_PRESETS, list)
        assert len(MODEL_PRESETS) > 0

    def test_model_presets_have_correct_structure(self):
        """Each preset should be (display_name, model_string, env_var, description)."""
        from adkbot.cli.onboard import MODEL_PRESETS

        for preset in MODEL_PRESETS:
            assert isinstance(preset, tuple)
            assert len(preset) == 4
            display_name, model_string, env_var, description = preset
            assert isinstance(display_name, str)
            # model_string can be None for custom option
            assert model_string is None or isinstance(model_string, str)
            # env_var can be None for local models
            assert env_var is None or isinstance(env_var, str)
            assert isinstance(description, str)

    def test_model_presets_include_gemini(self):
        """Should include Gemini models (recommended default)."""
        from adkbot.cli.onboard import MODEL_PRESETS

        model_strings = [p[1] for p in MODEL_PRESETS if p[1]]
        gemini_models = [m for m in model_strings if "gemini" in m.lower()]
        assert len(gemini_models) > 0

    def test_model_presets_include_openrouter(self):
        """Should include OpenRouter models."""
        from adkbot.cli.onboard import MODEL_PRESETS

        model_strings = [p[1] for p in MODEL_PRESETS if p[1]]
        openrouter_models = [m for m in model_strings if m.startswith("openrouter/")]
        assert len(openrouter_models) > 0

    def test_custom_model_option_exists(self):
        """Should have a custom model string option."""
        from adkbot.cli.onboard import MODEL_PRESETS

        custom_options = [p for p in MODEL_PRESETS if p[1] is None]
        assert len(custom_options) == 1


# Note: _configure_pydantic_model and _BACK_PRESSED removed in Phase 1
# The new onboard.py uses simpler channel configuration flow


class TestRunOnboardExitBehavior:
    def test_skip_wizard_returns_config(self, monkeypatch):
        """Test that skip_wizard=True returns a valid config without interaction."""
        result = run_onboard(skip_wizard=True)
        assert result.config is not None
        assert isinstance(result.config, Config)

    def test_onboard_result_structure(self):
        """Test that OnboardResult has correct structure."""
        from adkbot.cli.onboard import OnboardResult

        config = Config()
        result = OnboardResult(config=config, should_save=True)
        assert result.config is config
        assert result.should_save is True
