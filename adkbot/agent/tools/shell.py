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


async def _read_stream(stream: asyncio.StreamReader | None, parts: list[str]) -> None:
    """Read a stream in chunks to safely capture partial output."""
    if not stream:
        return
    try:
        while True:
            chunk = await stream.read(8192)
            if not chunk:
                break
            parts.append(chunk.decode("utf-8", errors="replace"))
    except Exception:
        pass


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

        stdout_parts: list[str] = []
        stderr_parts: list[str] = []
        
        # Read streams concurrently so we capture partial output even if it times out
        stdout_task = asyncio.create_task(_read_stream(process.stdout, stdout_parts))
        stderr_task = asyncio.create_task(_read_stream(process.stderr, stderr_parts))

        timed_out = False
        try:
            # wait() instead of communicate() avoids Termux broken pipe hangs
            await asyncio.wait_for(process.wait(), timeout=effective_timeout)
        except asyncio.TimeoutError:
            timed_out = True
            try:
                process.kill()
                await asyncio.wait_for(process.wait(), timeout=3.0)
            except (asyncio.TimeoutError, ProcessLookupError, ChildProcessError, OSError):
                pass
            finally:
                if sys.platform != "win32":
                    try:
                        os.waitpid(process.pid, os.WNOHANG)
                    except (ProcessLookupError, ChildProcessError, OSError) as e:
                        logger.debug("Process already reaped or not found: {}", e)
        except (ChildProcessError, ProcessLookupError, OSError) as e:
            # Termux / proot aggressive OS reaping (Errno 10)
            logger.debug("Process reaped early by OS (Termux/Proot): {}", e)

        # Allow stream readers a brief moment to flush the final bytes
        try:
            await asyncio.wait_for(asyncio.gather(stdout_task, stderr_task), timeout=2.0)
        except Exception:
            pass

        # Cleanup transport for Windows to prevent pipe leaks
        if hasattr(process, "_transport") and process._transport is not None:
            process._transport.close()

        stdout_text = "".join(stdout_parts)
        stderr_text = "".join(stderr_parts)
        
        output_parts_final = []
        if stdout_text:
            output_parts_final.append(stdout_text)
        if stderr_text:
            if stderr_text.strip():
                output_parts_final.append(f"STDERR:\n{stderr_text}")

        if timed_out:
            output_parts_final.append(f"\n[Error: Command timed out after {effective_timeout} seconds. Partial output captured above.]")
            exit_code = -1
        else:
            exit_code = process.returncode if process.returncode is not None else 0
            output_parts_final.append(f"\nExit code: {exit_code}")

        result = "\n".join(output_parts_final) if output_parts_final else "(no output)"

        # Head + tail truncation to preserve both start and end of output
        if len(result) > _MAX_OUTPUT:
            half = _MAX_OUTPUT // 2
            result = (
                result[:half]
                + f"\n\n... ({len(result) - _MAX_OUTPUT:,} chars truncated) ...\n\n"
                + result[-half:]
            )

        return {"output": result, "exit_code": exit_code}

    except Exception as e:
        return {"error": f"Error executing command: {e}"}