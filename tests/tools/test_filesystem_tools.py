"""Tests for enhanced filesystem function tools: read_file, edit_file, list_directory."""

import pytest

from adkbot.agent.tools.filesystem import (
    read_file,
    write_file,
    edit_file,
    list_directory,
    _find_match,
)


# ---------------------------------------------------------------------------
# read_file
# ---------------------------------------------------------------------------

class TestReadFile:

    @pytest.fixture()
    def sample_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ADKBOT_WORKSPACE", str(tmp_path))
        f = tmp_path / "sample.txt"
        f.write_text("\n".join(f"line {i}" for i in range(1, 21)), encoding="utf-8")
        return f

    @pytest.mark.asyncio
    async def test_basic_read_has_line_numbers(self, sample_file, monkeypatch):
        monkeypatch.setenv("ADKBOT_WORKSPACE", str(sample_file.parent))
        result = await read_file(path=str(sample_file))
        assert "1| line 1" in str(result)
        assert "20| line 20" in str(result)

    @pytest.mark.asyncio
    async def test_offset_and_limit(self, sample_file, monkeypatch):
        monkeypatch.setenv("ADKBOT_WORKSPACE", str(sample_file.parent))
        result = await read_file(path=str(sample_file), offset=5, limit=3)
        assert "5| line 5" in str(result)
        assert "7| line 7" in str(result)
        assert "8| line 8" not in str(result)
        assert "Use offset=8 to continue" in str(result)

    @pytest.mark.asyncio
    async def test_offset_beyond_end(self, sample_file, monkeypatch):
        monkeypatch.setenv("ADKBOT_WORKSPACE", str(sample_file.parent))
        result = await read_file(path=str(sample_file), offset=999)
        assert "error" in result
        assert "beyond end" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_end_of_file_marker(self, sample_file, monkeypatch):
        monkeypatch.setenv("ADKBOT_WORKSPACE", str(sample_file.parent))
        result = await read_file(path=str(sample_file), offset=1, limit=9999)
        assert "End of file" in str(result)

    @pytest.mark.asyncio
    async def test_empty_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ADKBOT_WORKSPACE", str(tmp_path))
        f = tmp_path / "empty.txt"
        f.write_text("", encoding="utf-8")
        result = await read_file(path=str(f))
        assert "Empty file" in str(result)

    @pytest.mark.asyncio
    async def test_image_file_returns_type_info(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ADKBOT_WORKSPACE", str(tmp_path))
        f = tmp_path / "pixel.png"
        f.write_bytes(b"\x89PNG\r\n\x1a\nfake-png-data")
        result = await read_file(path=str(f))
        assert "content" in result
        assert "Image file:" in str(result["content"])

    @pytest.mark.asyncio
    async def test_file_not_found(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ADKBOT_WORKSPACE", str(tmp_path))
        result = await read_file(path=str(tmp_path / "nope.txt"))
        assert "error" in result
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_missing_path_returns_error(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ADKBOT_WORKSPACE", str(tmp_path))
        result = await read_file(path="")
        assert "error" in result


# ---------------------------------------------------------------------------
# _find_match  (unit tests for the helper)
# ---------------------------------------------------------------------------

class TestFindMatch:

    def test_exact_match(self):
        match, count = _find_match("hello world", "world")
        assert match == "world"
        assert count == 1

    def test_exact_no_match(self):
        match, count = _find_match("hello world", "xyz")
        assert match is None
        assert count == 0

    def test_crlf_normalisation(self):
        content = "line1\nline2\nline3"
        old_text = "line1\nline2\nline3"
        match, count = _find_match(content, old_text)
        assert match is not None
        assert count == 1

    def test_line_trim_fallback(self):
        content = "    def foo():\n        pass\n"
        old_text = "def foo():\n    pass"
        match, count = _find_match(content, old_text)
        assert match is not None
        assert count == 1
        assert "    def foo():" in match

    def test_line_trim_multiple_candidates(self):
        content = "  a\n  b\n  a\n  b\n"
        old_text = "a\nb"
        match, count = _find_match(content, old_text)
        assert count == 2

    def test_empty_old_text(self):
        match, count = _find_match("hello", "")
        assert match == ""


# ---------------------------------------------------------------------------
# edit_file
# ---------------------------------------------------------------------------

class TestEditFile:

    @pytest.mark.asyncio
    async def test_exact_match(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ADKBOT_WORKSPACE", str(tmp_path))
        f = tmp_path / "a.py"
        f.write_text("hello world", encoding="utf-8")
        result = await edit_file(path=str(f), old_text="world", new_text="earth")
        assert "Successfully" in str(result)
        assert f.read_text() == "hello earth"

    @pytest.mark.asyncio
    async def test_crlf_normalisation(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ADKBOT_WORKSPACE", str(tmp_path))
        f = tmp_path / "crlf.py"
        f.write_bytes(b"line1\r\nline2\r\nline3")
        result = await edit_file(
            path=str(f), old_text="line1\nline2", new_text="LINE1\nLINE2",
        )
        assert "Successfully" in str(result)
        raw = f.read_bytes()
        assert b"LINE1" in raw
        assert b"\r\n" in raw

    @pytest.mark.asyncio
    async def test_trim_fallback(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ADKBOT_WORKSPACE", str(tmp_path))
        f = tmp_path / "indent.py"
        f.write_text("    def foo():\n        pass\n", encoding="utf-8")
        result = await edit_file(
            path=str(f), old_text="def foo():\n    pass", new_text="def bar():\n    return 1",
        )
        assert "Successfully" in str(result)
        assert "bar" in f.read_text()

    @pytest.mark.asyncio
    async def test_ambiguous_match(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ADKBOT_WORKSPACE", str(tmp_path))
        f = tmp_path / "dup.py"
        f.write_text("aaa\nbbb\naaa\nbbb\n", encoding="utf-8")
        result = await edit_file(path=str(f), old_text="aaa\nbbb", new_text="xxx")
        assert "warning" in result
        assert "appears" in result["warning"].lower()

    @pytest.mark.asyncio
    async def test_replace_all(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ADKBOT_WORKSPACE", str(tmp_path))
        f = tmp_path / "multi.py"
        f.write_text("foo bar foo bar foo", encoding="utf-8")
        result = await edit_file(
            path=str(f), old_text="foo", new_text="baz", replace_all=True,
        )
        assert "Successfully" in str(result)
        assert f.read_text() == "baz bar baz bar baz"

    @pytest.mark.asyncio
    async def test_not_found(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ADKBOT_WORKSPACE", str(tmp_path))
        f = tmp_path / "nf.py"
        f.write_text("hello", encoding="utf-8")
        result = await edit_file(path=str(f), old_text="xyz", new_text="abc")
        assert "error" in result
        assert "not found" in result["error"].lower()


# ---------------------------------------------------------------------------
# list_directory
# ---------------------------------------------------------------------------

class TestListDirectory:

    @pytest.fixture()
    def populated_dir(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ADKBOT_WORKSPACE", str(tmp_path))
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("pass")
        (tmp_path / "src" / "utils.py").write_text("pass")
        (tmp_path / "README.md").write_text("hi")
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "config").write_text("x")
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "pkg").mkdir()
        return tmp_path

    @pytest.mark.asyncio
    async def test_basic_list(self, populated_dir):
        result = await list_directory(path=str(populated_dir))
        assert "README.md" in str(result)
        assert "src" in str(result)
        assert ".git" not in str(result)
        assert "node_modules" not in str(result)

    @pytest.mark.asyncio
    async def test_recursive(self, populated_dir):
        result = await list_directory(path=str(populated_dir), recursive=True)
        normalized = str(result).replace("\\", "/")
        assert "src" in normalized and "main.py" in normalized
        assert "README.md" in str(result)
        assert ".git" not in str(result)
        assert "node_modules" not in str(result)

    @pytest.mark.asyncio
    async def test_max_entries_truncation(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ADKBOT_WORKSPACE", str(tmp_path))
        for i in range(10):
            (tmp_path / f"file_{i}.txt").write_text("x")
        result = await list_directory(path=str(tmp_path), max_entries=3)
        assert "truncated" in str(result)
        assert "3 of 10" in str(result)

    @pytest.mark.asyncio
    async def test_empty_dir(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ADKBOT_WORKSPACE", str(tmp_path))
        d = tmp_path / "empty"
        d.mkdir()
        result = await list_directory(path=str(d))
        assert "empty" in str(result).lower()

    @pytest.mark.asyncio
    async def test_not_found(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ADKBOT_WORKSPACE", str(tmp_path))
        result = await list_directory(path=str(tmp_path / "nope"))
        assert "error" in result


# ---------------------------------------------------------------------------
# Workspace restriction
# ---------------------------------------------------------------------------

class TestWorkspaceRestriction:

    @pytest.mark.asyncio
    async def test_read_blocked_outside_workspace(self, monkeypatch, tmp_path):
        workspace = tmp_path / "ws"
        workspace.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        secret = outside / "secret.txt"
        secret.write_text("top secret")

        monkeypatch.setenv("ADKBOT_RESTRICT_WORKSPACE", "1")
        monkeypatch.setenv("ADKBOT_WORKSPACE", str(workspace))

        result = await read_file(path=str(secret))
        assert "error" in result
        assert "outside" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_write_blocked_outside_workspace(self, monkeypatch, tmp_path):
        workspace = tmp_path / "ws"
        workspace.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()

        monkeypatch.setenv("ADKBOT_RESTRICT_WORKSPACE", "1")
        monkeypatch.setenv("ADKBOT_WORKSPACE", str(workspace))

        result = await write_file(path=str(outside / "hack.txt"), content="pwned")
        assert "error" in result
        assert "outside" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_edit_blocked_outside_workspace(self, monkeypatch, tmp_path):
        workspace = tmp_path / "ws"
        workspace.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        target = outside / "secret.txt"
        target.write_text("Original content.")

        monkeypatch.setenv("ADKBOT_RESTRICT_WORKSPACE", "1")
        monkeypatch.setenv("ADKBOT_WORKSPACE", str(workspace))

        result = await edit_file(
            path=str(target),
            old_text="Original content.",
            new_text="Hacked content.",
        )
        assert "error" in result
        assert "outside" in result["error"].lower()
        assert target.read_text() == "Original content."

    @pytest.mark.asyncio
    async def test_workspace_file_still_readable(self, monkeypatch, tmp_path):
        workspace = tmp_path / "ws"
        workspace.mkdir()
        ws_file = workspace / "README.md"
        ws_file.write_text("hello from workspace")

        monkeypatch.setenv("ADKBOT_WORKSPACE", str(workspace))

        result = await read_file(path=str(ws_file))
        assert "hello from workspace" in str(result)
        assert "error" not in result
