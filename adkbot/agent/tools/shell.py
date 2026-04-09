"""Shell execution tool.

Converted to ADK function-tool pattern — plain function with docstring
and type annotations. ADK auto-wraps it via FunctionTool.
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
from pathlib import Path

from loguru import logger

# Safety: patterns that block dangerous commands
_DEFAULT_DENY_PATTERNS = [
    r"\brm\s+-[rf]{1,2}\b",          # rm -r, rm -rf, rm -fr
    r"\bdel\s+/[fq]\b",              # del /f, del /q
    r"\brmdir\s+/s\b",               # rmdir /s
    r"(?:^|[;&|]\s*)format\b",       # format (as standalone command only)
    r"\b(mkfs|diskpart)\b",          # disk operations
    r"\bdd\s+if=",                   # dd
    r">\s*/dev/sd",                  # write to disk
    r"\b(shutdown|reboot|poweroff)\b",  # system power
    r":\(\)\s*\{.*\};\s*:",          # fork bomb
]

_MAX_TIMEOUT = 600
_MAX_OUTPUT = 10_000


def _extract_absolute_paths(command: str) -> list[str]:
    """Extract absolute paths from a command string."""
    win_paths = re.findall(r"[A-Za-z]:\\[^\s\"'|><;]*", command)
    posix_paths = re.findall(r"(?:^|[\s|>'\"])(/[^\s\"'>;|<]+)", command)
    home_paths = re.findall(r"(?:^|[\s|>'\"])(~[^\s\"'>;|<]*)", command)
    return win_paths + posix_paths + home_paths


def _guard_command(command: str, cwd: str, restrict_to_workspace: bool = False) -> str | None:
    """Best-effort safety guard for potentially destructive commands."""
    cmd = command.strip()
    lower = cmd.lower()

    for pattern in _DEFAULT_DENY_PATTERNS:
        if re.search(pattern, lower):
            return "Error: Command blocked by safety guard (dangerous pattern detected)"

    from adkbot.security.network import contains_internal_url
    if contains_internal_url(cmd):
        return "Error: Command blocked by safety guard (internal/private URL detected)"

    if restrict_to_workspace:
        if "..\\" in cmd or "../" in cmd:
            return "Error: Command blocked by safety guard (path traversal detected)"

        cwd_path = Path(cwd).resolve()
        for raw in _extract_absolute_paths(cmd):
            try:
                expanded = os.path.expandvars(raw.strip())
                p = Path(expanded).expanduser().resolve()
            except Exception:
                continue
            if p.is_absolute() and cwd_path not in p.parents and p != cwd_path:
                return "Error: Command blocked by safety guard (path outside working dir)"

    return None


# ---------------------------------------------------------------------------
# ✅ ADK Function Tool
# ---------------------------------------------------------------------------

async def execute_command(command: str, working_dir: str = "", timeout: int = 60) -> dict:
    """Execute a shell command and return its output.

    Use with caution. Dangerous commands (rm -rf, format, shutdown, etc.)
    are automatically blocked. Output is truncated to 10,000 chars.

    Args:
        command: The shell command to execute.
        working_dir: Optional working directory for the command. Defaults to current directory.
        timeout: Timeout in seconds (default 60, max 600). Increase for compilation/installation.

    Returns:
        A dict with stdout, stderr, exit code, or error message.
    """
    cwd = working_dir or os.environ.get("ADKBOT_WORKSPACE") or os.getcwd()
    restrict = os.environ.get("ADKBOT_RESTRICT_WORKSPACE", "").lower() in ("1", "true", "yes")

    guard_error = _guard_command(command, cwd, restrict)
    if guard_error:
        return {"error": guard_error}

    effective_timeout = min(timeout, _MAX_TIMEOUT)

    env = os.environ.copy()
    path_append = os.environ.get("ADKBOT_PATH_APPEND", "")
    if path_append:
        env["PATH"] = env.get("PATH", "") + os.pathsep + path_append

    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=env,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=effective_timeout,
            )
        except asyncio.TimeoutError:
            process.kill()
            try:
                await asyncio.wait_for(process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                pass
            finally:
                if sys.platform != "win32":
                    try:
                        os.waitpid(process.pid, os.WNOHANG)
                    except (ProcessLookupError, ChildProcessError) as e:
                        logger.debug("Process already reaped or not found: {}", e)
            return {"error": f"Command timed out after {effective_timeout} seconds"}
        finally:
            # Force transport closure to prevent Windows Proactor pipe leaks in tests
            if hasattr(process, "_transport") and process._transport is not None:
                process._transport.close()

        output_parts = []

        if stdout:
            output_parts.append(stdout.decode("utf-8", errors="replace"))

        if stderr:
            stderr_text = stderr.decode("utf-8", errors="replace")
            if stderr_text.strip():
                output_parts.append(f"STDERR:\n{stderr_text}")

        output_parts.append(f"\nExit code: {process.returncode}")

        result = "\n".join(output_parts) if output_parts else "(no output)"

        # Head + tail truncation to preserve both start and end of output
        if len(result) > _MAX_OUTPUT:
            half = _MAX_OUTPUT // 2
            result = (
                result[:half]
                + f"\n\n... ({len(result) - _MAX_OUTPUT:,} chars truncated) ...\n\n"
                + result[-half:]
            )

        return {"output": result, "exit_code": process.returncode}

    except Exception as e:
        return {"error": f"Error executing command: {e}"}


