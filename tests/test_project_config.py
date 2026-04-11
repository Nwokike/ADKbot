"""Tests for project-level configuration — pyproject.toml and gitignore."""

from __future__ import annotations

from pathlib import Path

class TestPyprojectRefactored:
    """Verify pyproject.toml has lean core dependencies and optional extras."""

    def test_tiktoken_removed_from_core(self):
        """tiktoken must not be in core dependencies."""
        toml = Path("pyproject.toml").read_text(encoding="utf-8")
        # Find the core [dependencies] section (before [project.optional-dependencies])
        deps_section = toml.split("[project.optional-dependencies]")[0]
        assert "tiktoken" not in deps_section

    def test_pydantic_settings_in_core(self):
        """pydantic-settings must be a core dependency."""
        toml = Path("pyproject.toml").read_text(encoding="utf-8")
        deps_section = toml.split("[project.optional-dependencies]")[0]
        assert "pydantic-settings" in deps_section

    def test_telegram_in_core_deps(self):
        """python-telegram-bot should be a core dependency for best UX."""
        toml = Path("pyproject.toml").read_text(encoding="utf-8")
        deps_section = toml.split("[project.optional-dependencies]")[0]
        assert "python-telegram-bot" in deps_section
        assert "[project.optional-dependencies]" in toml

    def test_all_extra_exists(self):
        """An [all] extra must exist for convenience installs."""
        toml = Path("pyproject.toml").read_text(encoding="utf-8")
        assert "all = [" in toml

class TestGitignore:
    """Verify runtime data directories are ignored."""

    def test_sessions_in_gitignore(self):
        """sessions/ directory should be in .gitignore."""
        gitignore = Path(".gitignore").read_text(encoding="utf-8")
        assert "sessions/" in gitignore
