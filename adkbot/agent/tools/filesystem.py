"""File system tools: read, write, edit, list.

Converted to ADK function-tool pattern — plain functions with docstrings
and type annotations. ADK auto-wraps these via FunctionTool.
"""

from __future__ import annotations

import difflib
import mimetypes
import os
from pathlib import Path
from typing import Any

from loguru import logger


# ---------------------------------------------------------------------------
# Internal helpers (kept from original)
# ---------------------------------------------------------------------------

_MAX_READ_CHARS = 128_000
_DEFAULT_LIMIT = 2000
_DEFAULT_MAX_ENTRIES = 200
_IGNORE_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "dist", "build", ".tox", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", ".coverage", "htmlcov",
}


def _get_workspace() -> Path | None:
    """Get workspace from environment."""
    ws = os.environ.get("ADKBOT_WORKSPACE")
    if ws:
        return Path(ws).expanduser().resolve()
    return None


def _resolve_path(path: str) -> Path:
    """Resolve path against workspace and enforce directory restriction."""
    workspace = _get_workspace()
    restrict = os.environ.get("ADKBOT_RESTRICT_WORKSPACE", "").lower() in ("1", "true", "yes")

    p = Path(path).expanduser()
    if not p.is_absolute() and workspace:
        p = workspace / p
    resolved = p.resolve()

    if restrict and workspace:
        if not _is_under(resolved, workspace):
            raise PermissionError(f"Path {path} is outside workspace {workspace}")
    return resolved


def _is_under(path: Path, directory: Path) -> bool:
    try:
        path.relative_to(directory.resolve())
        return True
    except ValueError:
        return False


def _not_found_msg(old_text: str, content: str, path: str) -> str:
    """Build a helpful "not found" message with closest match diff."""
    lines = content.splitlines(keepends=True)
    old_lines = old_text.splitlines(keepends=True)
    window = len(old_lines)

    best_ratio, best_start = 0.0, 0
    for i in range(max(1, len(lines) - window + 1)):
        ratio = difflib.SequenceMatcher(None, old_lines, lines[i : i + window]).ratio()
        if ratio > best_ratio:
            best_ratio, best_start = ratio, i

    if best_ratio > 0.5:
        diff = "\n".join(difflib.unified_diff(
            old_lines, lines[best_start : best_start + window],
            fromfile="old_text (provided)",
            tofile=f"{path} (actual, line {best_start + 1})",
            lineterm="",
        ))
        return f"Error: old_text not found in {path}.\nBest match ({best_ratio:.0%} similar) at line {best_start + 1}:\n{diff}"
    return f"Error: old_text not found in {path}. No similar text found. Verify the file content."


def _find_match(content: str, old_text: str) -> tuple[str | None, int]:
    """Locate old_text in content: exact first, then line-trimmed sliding window."""
    if old_text in content:
        return old_text, content.count(old_text)

    old_lines = old_text.splitlines()
    if not old_lines:
        return None, 0
    stripped_old = [l.strip() for l in old_lines]
    content_lines = content.splitlines()

    candidates = []
    for i in range(len(content_lines) - len(stripped_old) + 1):
        window = content_lines[i : i + len(stripped_old)]
        if [l.strip() for l in window] == stripped_old:
            candidates.append("\n".join(window))

    if candidates:
        return candidates[0], len(candidates)
    return None, 0


# ---------------------------------------------------------------------------
# ✅ ADK Function Tools
# ---------------------------------------------------------------------------

async def read_file(path: str, offset: int = 1, limit: int = 2000) -> dict:
    """Read the contents of a file. Returns numbered lines.

    Use offset and limit to paginate through large files.
    Supports text files (UTF-8) and image files.

    Args:
        path: The file path to read.
        offset: Line number to start reading from (1-indexed, default 1).
        limit: Maximum number of lines to read (default 2000).

    Returns:
        A dict with the file content or error message.
    """
    try:
        if not path:
            return {"error": "No path provided"}
        fp = _resolve_path(path)
        if not fp.exists():
            return {"error": f"File not found: {path}"}
        if not fp.is_file():
            return {"error": f"Not a file: {path}"}

        raw = fp.read_bytes()
        if not raw:
            return {"content": f"(Empty file: {path})", "lines": 0}

        # Image detection
        from adkbot.utils.helpers import detect_image_mime
        mime = detect_image_mime(raw) or mimetypes.guess_type(str(fp))[0]
        if mime and mime.startswith("image/"):
            return {"content": f"(Image file: {path}, type: {mime})", "type": "image", "mime": mime}

        try:
            text_content = raw.decode("utf-8")
        except UnicodeDecodeError:
            return {"error": f"Cannot read binary file {path} (MIME: {mime or 'unknown'}). Only UTF-8 text and images are supported."}

        all_lines = text_content.splitlines()
        total = len(all_lines)

        if offset < 1:
            offset = 1
        if offset > total:
            return {"error": f"offset {offset} is beyond end of file ({total} lines)"}

        start = offset - 1
        end = min(start + limit, total)
        numbered = [f"{start + i + 1}| {line}" for i, line in enumerate(all_lines[start:end])]
        result = "\n".join(numbered)

        if len(result) > _MAX_READ_CHARS:
            trimmed, chars = [], 0
            for line in numbered:
                chars += len(line) + 1
                if chars > _MAX_READ_CHARS:
                    break
                trimmed.append(line)
            end = start + len(trimmed)
            result = "\n".join(trimmed)

        if end < total:
            result += f"\n\n(Showing lines {offset}-{end} of {total}. Use offset={end + 1} to continue.)"
        else:
            result += f"\n\n(End of file — {total} lines total)"
        return {"content": result, "total_lines": total, "shown": f"{offset}-{end}"}

    except PermissionError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"Error reading file: {e}"}


async def write_file(path: str, content: str) -> dict:
    """Write content to a file at the given path.

    Creates parent directories if needed. Overwrites existing files.

    Args:
        path: The file path to write to.
        content: The content to write.

    Returns:
        A dict with success message or error.
    """
    try:
        if not path:
            return {"error": "No path provided"}
        fp = _resolve_path(path)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content, encoding="utf-8")
        return {"result": f"Successfully wrote {len(content)} bytes to {fp}"}
    except PermissionError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"Error writing file: {e}"}


async def edit_file(path: str, old_text: str, new_text: str, replace_all: bool = False) -> dict:
    """Edit a file by replacing old_text with new_text.

    Supports minor whitespace/line-ending differences via fuzzy matching.
    Set replace_all=true to replace every occurrence.

    Args:
        path: The file path to edit.
        old_text: The text to find and replace.
        new_text: The text to replace with.
        replace_all: Replace all occurrences (default false).

    Returns:
        A dict with success message, warning, or error.
    """
    try:
        if not path:
            return {"error": "No path provided"}

        fp = _resolve_path(path)
        if not fp.exists():
            return {"error": f"File not found: {path}"}

        raw = fp.read_bytes()
        uses_crlf = b"\r\n" in raw
        content = raw.decode("utf-8").replace("\r\n", "\n")
        match, count = _find_match(content, old_text.replace("\r\n", "\n"))

        if match is None:
            return {"error": _not_found_msg(old_text, content, path)}
        if count > 1 and not replace_all:
            return {
                "warning": f"old_text appears {count} times. "
                "Provide more context to make it unique, or set replace_all=true."
            }

        norm_new = new_text.replace("\r\n", "\n")
        new_content = content.replace(match, norm_new) if replace_all else content.replace(match, norm_new, 1)
        if uses_crlf:
            new_content = new_content.replace("\n", "\r\n")

        fp.write_bytes(new_content.encode("utf-8"))
        return {"result": f"Successfully edited {fp}"}
    except PermissionError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"Error editing file: {e}"}


async def list_directory(path: str, recursive: bool = False, max_entries: int = 200) -> dict:
    """List the contents of a directory.

    Set recursive=true to explore nested structure.
    Common noise directories (.git, node_modules, __pycache__, etc.) are auto-ignored.

    Args:
        path: The directory path to list.
        recursive: Recursively list all files (default false).
        max_entries: Maximum entries to return (default 200).

    Returns:
        A dict with the directory listing or error.
    """
    try:
        if not path:
            return {"error": "No path provided"}
        dp = _resolve_path(path)
        if not dp.exists():
            return {"error": f"Directory not found: {path}"}
        if not dp.is_dir():
            return {"error": f"Not a directory: {path}"}

        cap = max_entries
        items: list[str] = []
        total = 0

        if recursive:
            for item in sorted(dp.rglob("*")):
                if any(p in _IGNORE_DIRS for p in item.parts):
                    continue
                total += 1
                if len(items) < cap:
                    rel = item.relative_to(dp)
                    items.append(f"{rel}/" if item.is_dir() else str(rel))
        else:
            for item in sorted(dp.iterdir()):
                if item.name in _IGNORE_DIRS:
                    continue
                total += 1
                if len(items) < cap:
                    pfx = "📁 " if item.is_dir() else "📄 "
                    items.append(f"{pfx}{item.name}")

        if not items and total == 0:
            return {"content": f"Directory {path} is empty", "total": 0}

        result = "\n".join(items)
        if total > cap:
            result += f"\n\n(truncated, showing first {cap} of {total} entries)"
        return {"content": result, "total": total, "shown": len(items)}
    except PermissionError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"Error listing directory: {e}"}


