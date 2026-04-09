"""Cron tool for scheduling reminders and tasks.

Converted to ADK function-tool pattern. Uses ToolContext to access
the CronService and session context stored in state.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from google.adk.tools import ToolContext
from loguru import logger


def _validate_timezone(tz: str) -> str | None:
    """Validate IANA timezone string."""
    from zoneinfo import ZoneInfo
    try:
        ZoneInfo(tz)
    except (KeyError, Exception):
        return f"Error: unknown timezone '{tz}'"
    return None


def _format_timestamp(ms: int, tz_name: str) -> str:
    """Format millisecond timestamp with timezone."""
    from zoneinfo import ZoneInfo
    dt = datetime.fromtimestamp(ms / 1000, tz=ZoneInfo(tz_name))
    return f"{dt.isoformat()} ({tz_name})"


def _format_timing(schedule: Any, default_tz: str) -> str:
    """Format schedule as a human-readable timing string."""
    if schedule.kind == "cron":
        tz = f" ({schedule.tz})" if schedule.tz else ""
        return f"cron: {schedule.expr}{tz}"
    if schedule.kind == "every" and schedule.every_ms:
        ms = schedule.every_ms
        if ms % 3_600_000 == 0:
            return f"every {ms // 3_600_000}h"
        if ms % 60_000 == 0:
            return f"every {ms // 60_000}m"
        if ms % 1000 == 0:
            return f"every {ms // 1000}s"
        return f"every {ms}ms"
    if schedule.kind == "at" and schedule.at_ms:
        display_tz = schedule.tz or default_tz
        return f"at {_format_timestamp(schedule.at_ms, display_tz)}"
    return schedule.kind


# ---------------------------------------------------------------------------
# ✅ ADK Function Tools
# ---------------------------------------------------------------------------

async def schedule_task(
    action: str,
    message: str = "",
    every_seconds: int = 0,
    cron_expr: str = "",
    tz: str = "",
    at: str = "",
    job_id: str = "",
    deliver: bool = True,
    tool_context: ToolContext = None,
) -> dict:
    """Schedule reminders and recurring tasks.

    Actions: add, list, remove.
    Supports interval scheduling, cron expressions, and one-time execution.

    Args:
        action: Action to perform - 'add', 'list', or 'remove'.
        message: Instruction for the agent when the job triggers (required for add).
        every_seconds: Interval in seconds for recurring tasks.
        cron_expr: Cron expression like '0 9 * * *' for scheduled tasks.
        tz: Optional IANA timezone for cron expressions (e.g. 'America/Vancouver').
        at: ISO datetime for one-time execution (e.g. '2026-02-12T10:30:00').
        job_id: Job ID (required for remove).
        deliver: Whether to deliver the execution result to the user channel (default true).

    Returns:
        A dict with the action result or error message.
    """
    from adkbot.cron.service import CronService
    from adkbot.cron.types import CronSchedule

    state = tool_context.state if tool_context else {}
    default_tz = state.get("_timezone", "UTC")
    channel = state.get("_channel", "")
    chat_id = state.get("_chat_id", "")

    # Get cron service from state (injected by gateway or CLI setup)
    cron_service = state.get("_cron_service")
    if not cron_service:
        return {"error": "Cron service not available"}

    if action == "add":
        if state.get("_in_cron_context"):
            return {"error": "Cannot schedule new jobs from within a cron job execution"}
        if not message:
            return {"error": "message is required for add"}
        if not channel or not chat_id:
            return {"error": "No session context (channel/chat_id)"}
        if tz and not cron_expr:
            return {"error": "tz can only be used with cron_expr"}
        if tz:
            if err := _validate_timezone(tz):
                return {"error": err}

        # Build schedule
        delete_after = False
        if every_seconds:
            schedule = CronSchedule(kind="every", every_ms=every_seconds * 1000)
        elif cron_expr:
            effective_tz = tz or default_tz
            if err := _validate_timezone(effective_tz):
                return {"error": err}
            schedule = CronSchedule(kind="cron", expr=cron_expr, tz=effective_tz)
        elif at:
            from zoneinfo import ZoneInfo
            try:
                dt = datetime.fromisoformat(at)
            except ValueError:
                return {"error": f"Invalid ISO datetime format '{at}'. Expected: YYYY-MM-DDTHH:MM:SS"}
            if dt.tzinfo is None:
                if err := _validate_timezone(default_tz):
                    return {"error": err}
                dt = dt.replace(tzinfo=ZoneInfo(default_tz))
            at_ms = int(dt.timestamp() * 1000)
            schedule = CronSchedule(kind="at", at_ms=at_ms)
            delete_after = True
        else:
            return {"error": "Either every_seconds, cron_expr, or at is required"}

        job = cron_service.add_job(
            name=message[:30],
            schedule=schedule,
            message=message,
            deliver=deliver,
            channel=channel,
            to=chat_id,
            delete_after_run=delete_after,
        )
        return {"result": f"Created job '{job.name}' (id: {job.id})"}

    elif action == "list":
        jobs = cron_service.list_jobs()
        if not jobs:
            return {"result": "No scheduled jobs."}
        lines = []
        for j in jobs:
            timing = _format_timing(j.schedule, default_tz)
            lines.append(f"- {j.name} (id: {j.id}, {timing})")
        return {"result": "Scheduled jobs:\n" + "\n".join(lines), "count": len(jobs)}

    elif action == "remove":
        if not job_id:
            return {"error": "job_id is required for remove"}
        if cron_service.remove_job(job_id):
            return {"result": f"Removed job {job_id}"}
        return {"error": f"Job {job_id} not found"}

    return {"error": f"Unknown action: {action}"}


