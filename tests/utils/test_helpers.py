"""Tests for utility helpers and token counting logic."""

from __future__ import annotations

from pathlib import Path
from adkbot.utils.helpers import strip_think

class TestTiktokenReplaced:
    """Verify tiktoken dependency is replaced with LiteLLM."""

    def test_no_tiktoken_import(self):
        """No tiktoken import in helpers.py."""
        src = Path("adkbot/utils/helpers.py").read_text(encoding="utf-8")
        assert "import tiktoken" not in src

    def test_count_tokens_function_exists(self):
        """_count_tokens helper exists and uses litellm."""
        src = Path("adkbot/utils/helpers.py").read_text(encoding="utf-8")
        assert "def _count_tokens" in src
        assert "litellm" in src

    def test_estimate_prompt_tokens_chain_returns_litellm(self):
        """The chain function should return 'litellm' as source, not 'tiktoken'."""
        src = Path("adkbot/utils/helpers.py").read_text(encoding="utf-8")
        assert '"litellm"' in src
        assert '"tiktoken"' not in src

class TestStripThinkCaseInsensitive:
    """Verify strip_think handles various cases for <think> tags."""

    def test_lowercase(self):
        assert strip_think("<think>hidden</think>visible") == "visible"

    def test_uppercase(self):
        assert strip_think("<THINK>hidden</THINK>visible") == "visible"

    def test_mixed_case(self):
        assert strip_think("<Think>hidden</Think>visible") == "visible"

    def test_unclosed_uppercase(self):
        assert strip_think("before<THINK>trailing") == "before"
