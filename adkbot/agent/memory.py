"""Memory system using ADK MemoryService patterns."""

from __future__ import annotations

import asyncio
import json
import weakref
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from loguru import logger

from adkbot.utils.helpers import ensure_dir, estimate_message_tokens

if TYPE_CHECKING:
    from google.adk.memory import BaseMemoryService

_SAVE_MEMORY_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": "Save the memory consolidation result to persistent storage.",
            "parameters": {
                "type": "object",
                "properties": {
                    "history_entry": {
                        "type": "string",
                        "description": "A paragraph summarizing key events/decisions/topics. "
                        "Start with [YYYY-MM-DD HH:MM]. Include detail useful for grep search.",
                    },
                    "memory_update": {
                        "type": "string",
                        "description": "Full updated long-term memory as markdown. Include all existing "
                        "facts plus new ones. Return unchanged if nothing new.",
                    },
                },
                "required": ["history_entry", "memory_update"],
            },
        },
    }
]


def _ensure_text(value: Any) -> str:
    """Normalize tool-call payload values to text for file storage."""
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def _normalize_save_memory_args(args: Any) -> dict[str, Any] | None:
    """Normalize provider tool-call arguments to the expected dict shape."""
    if isinstance(args, str):
        args = json.loads(args)
    if isinstance(args, list):
        return args[0] if args and isinstance(args[0], dict) else None
    return args if isinstance(args, dict) else None


class MemoryStore:
    """Two-layer memory: MEMORY.md (long-term facts) + HISTORY.md (grep-searchable log).

    Optionally integrates with ADK MemoryService for semantic search capabilities.
    """

    _MAX_FAILURES_BEFORE_RAW_ARCHIVE = 3

    def __init__(
        self,
        workspace: Path,
        adk_memory_service: "BaseMemoryService | None" = None,
    ):
        self.memory_dir = ensure_dir(workspace / "memory")
        self.memory_file = self.memory_dir / "MEMORY.md"
        self.history_file = self.memory_dir / "HISTORY.md"
        self._consecutive_failures = 0
        self._adk_memory_service = adk_memory_service

    def read_long_term(self) -> str:
        """Read long-term memory from file."""
        if self.memory_file.exists():
            return self.memory_file.read_text(encoding="utf-8")
        return ""

    def write_long_term(self, content: str) -> None:
        """Write long-term memory to file."""
        self.memory_file.write_text(content, encoding="utf-8")

    def append_history(self, entry: str) -> None:
        """Append an entry to the history log."""
        with open(self.history_file, "a", encoding="utf-8") as f:
            f.write(entry.rstrip() + "\n\n")

    def get_memory_context(self) -> str:
        """Get memory context for prompt injection."""
        long_term = self.read_long_term()
        return f"## Long-term Memory\n{long_term}" if long_term else ""

    @staticmethod
    def _format_messages(messages: list[dict]) -> str:
        """Format messages for consolidation prompt."""
        lines = []
        for message in messages:
            if not message.get("content"):
                continue
            tools = (
                f" [tools: {', '.join(message['tools_used'])}]" if message.get("tools_used") else ""
            )
            lines.append(
                f"[{message.get('timestamp', '?')[:16]}] {message['role'].upper()}{tools}: {message['content']}"
            )
        return "\n".join(lines)

    async def consolidate_with_llm(
        self,
        messages: list[dict],
        chat_fn: Callable[[list[dict], list[dict], str], Any],
        model: str,
    ) -> bool:
        """Consolidate messages using provided chat function."""
        if not messages:
            return True

        current_memory = self.read_long_term()
        prompt = f"""Process this conversation and call the save_memory tool with your consolidation.

## Current Long-term Memory
{current_memory or "(empty)"}

## Conversation to Process
{self._format_messages(messages)}"""

        chat_messages = [
            {
                "role": "system",
                "content": "You are a memory consolidation agent. Call the save_memory tool with your consolidation of the conversation.",
            },
            {"role": "user", "content": prompt},
        ]

        try:
            response = await chat_fn(chat_messages, _SAVE_MEMORY_TOOL, model)

            has_tool_calls = False
            tool_calls = []
            finish_reason = None
            content = None

            if hasattr(response, "has_tool_calls"):
                has_tool_calls = response.has_tool_calls
                tool_calls = response.tool_calls if has_tool_calls else []
                finish_reason = getattr(response, "finish_reason", None)
                content = response.content
            elif isinstance(response, dict):
                has_tool_calls = bool(response.get("tool_calls"))
                tool_calls = response.get("tool_calls", [])
                finish_reason = response.get("finish_reason")
                content = response.get("content")

            if not has_tool_calls:
                logger.warning(
                    "Memory consolidation: LLM did not call save_memory (finish_reason={}, content_len={})",
                    finish_reason,
                    len(content or ""),
                )
                return self._fail_or_raw_archive(messages)

            if not tool_calls:
                return self._fail_or_raw_archive(messages)

            # Handle both dict and ToolCallRequest object formats
            first_tool = tool_calls[0]
            if hasattr(first_tool, "arguments"):
                raw_args = first_tool.arguments
            elif isinstance(first_tool, dict):
                raw_args = first_tool.get("arguments", first_tool)
            else:
                raw_args = first_tool

            args = _normalize_save_memory_args(raw_args)
            if args is None:
                logger.warning("Memory consolidation: unexpected save_memory arguments")
                return self._fail_or_raw_archive(messages)

            if "history_entry" not in args or "memory_update" not in args:
                logger.warning("Memory consolidation: save_memory payload missing required fields")
                return self._fail_or_raw_archive(messages)

            entry = args["history_entry"]
            update = args["memory_update"]

            if entry is None or update is None:
                return self._fail_or_raw_archive(messages)

            entry = _ensure_text(entry).strip()
            if not entry:
                return self._fail_or_raw_archive(messages)

            self.append_history(entry)
            update = _ensure_text(update)

            if update != current_memory:
                self.write_long_term(update)

            self._consecutive_failures = 0
            logger.info("Memory consolidation done for {} messages", len(messages))
            return True

        except Exception:
            logger.exception("Memory consolidation failed")
            return self._fail_or_raw_archive(messages)

    async def consolidate(
        self,
        messages: list[dict],
        provider: Any,
        model: str,
    ) -> bool:
        """Consolidate messages with legacy provider interface."""

        async def chat_fn(msgs, tools, mdl):
            return await provider.chat_with_retry(
                messages=msgs,
                tools=tools,
                model=mdl,
                tool_choice={"type": "function", "function": {"name": "save_memory"}},
            )

        return await self.consolidate_with_llm(messages, chat_fn, model)

    def _fail_or_raw_archive(self, messages: list[dict]) -> bool:
        """Increment failure count; after threshold, raw-archive messages."""
        self._consecutive_failures += 1
        if self._consecutive_failures < self._MAX_FAILURES_BEFORE_RAW_ARCHIVE:
            return False
        self._raw_archive(messages)
        self._consecutive_failures = 0
        return True

    def _raw_archive(self, messages: list[dict]) -> None:
        """Fallback: dump raw messages to HISTORY.md without LLM summarization."""
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.append_history(
            f"[{ts}] [RAW] {len(messages)} messages\n{self._format_messages(messages)}"
        )
        logger.warning("Memory consolidation degraded: raw-archived {} messages", len(messages))

    async def search_adk_memory(
        self,
        app_name: str,
        user_id: str,
        query: str,
    ) -> list[dict[str, Any]]:
        """Search memory using ADK MemoryService if available."""
        if self._adk_memory_service is None:
            return self._search_local(query)

        try:
            response = await self._adk_memory_service.search_memory(
                app_name=app_name,
                user_id=user_id,
                query=query,
            )
            if response is None:
                return self._search_local(query)

            memories = getattr(response, "memories", None)
            if memories is None:
                return self._search_local(query)

            results = []
            for memory in memories:
                if memory.content:
                    for part in memory.content.parts:
                        if part.text:
                            results.append(
                                {"text": part.text, "score": getattr(memory, "score", 1.0)}
                            )
            return results
        except Exception as e:
            logger.warning("ADK memory search failed, falling back to local: {}", e)
            return self._search_local(query)

    def _search_local(self, query: str) -> list[dict[str, Any]]:
        """Simple local keyword search in memory files."""
        results = []
        query_lower = query.lower()

        long_term = self.read_long_term()
        if query_lower in long_term.lower():
            results.append({"text": long_term, "score": 1.0})

        if self.history_file.exists():
            history = self.history_file.read_text(encoding="utf-8")
            for line in history.split("\n\n"):
                if query_lower in line.lower():
                    results.append({"text": line, "score": 0.8})

        return results


class AdkMemoryConsolidator:
    """Memory consolidation using ADK Agent pattern."""

    _MAX_CONSOLIDATION_ROUNDS = 5
    _SAFETY_BUFFER = 1024

    def __init__(
        self,
        workspace: Path,
        model: str,
        api_key: str | None = None,
        api_base: str | None = None,
        sessions: Any = None,
        context_window_tokens: int = 128000,
        max_completion_tokens: int = 4096,
        build_messages: Callable[..., list[dict[str, Any]]] | None = None,
        get_tool_definitions: Callable[[], list[dict[str, Any]]] | None = None,
        adk_memory_service: "BaseMemoryService | None" = None,
    ):
        self.store = MemoryStore(workspace, adk_memory_service=adk_memory_service)
        self.model = model
        self.api_key = api_key
        self.api_base = api_base
        self.sessions = sessions
        self.context_window_tokens = context_window_tokens
        self.max_completion_tokens = max_completion_tokens
        self._build_messages = build_messages
        self._get_tool_definitions = get_tool_definitions
        self._locks: weakref.WeakValueDictionary[str, asyncio.Lock] = weakref.WeakValueDictionary()

    def get_lock(self, session_key: str) -> asyncio.Lock:
        """Return the shared consolidation lock for one session."""
        return self._locks.setdefault(session_key, asyncio.Lock())

    async def consolidate_messages(
        self,
        messages: list[dict[str, object]],
        chat_fn: Callable | None = None,
    ) -> bool:
        """Archive a selected message chunk into persistent memory."""
        if chat_fn:
            return await self.store.consolidate_with_llm(messages, chat_fn, self.model)
        return await self._consolidate_with_adk_agent(messages)

    async def _consolidate_with_adk_agent(self, messages: list[dict]) -> bool:
        """Consolidate using ADK Agent pattern."""
        try:
            from google.adk.agents import LlmAgent
            from google.adk.models.lite_llm import LiteLlm
            from google.adk.runners import Runner
            from google.adk.sessions import InMemorySessionService
            from google.genai import types

            model_kwargs = {"model": self.model}
            if self.api_key:
                model_kwargs["api_key"] = self.api_key
            if self.api_base:
                model_kwargs["api_base"] = self.api_base

            llm_model = LiteLlm(**model_kwargs)

            current_memory = self.store.read_long_term()
            instruction = f"""You are a memory consolidation agent.
Given a conversation, extract key facts, decisions, and information.
Call the save_memory tool with:
- history_entry: A paragraph starting with [YYYY-MM-DD HH:MM] summarizing events.
- memory_update: Full updated memory markdown (existing facts + new ones).

Current Long-term Memory:
{current_memory or "(empty)"}
"""

            consolidation_agent = LlmAgent(
                name="memory_consolidator",
                model=llm_model,
                instruction=instruction,
            )

            session_service = InMemorySessionService()
            runner = Runner(
                agent=consolidation_agent,
                app_name="memory_consolidation",
                session_service=session_service,
            )

            _ = await session_service.create_session(
                app_name="memory_consolidation",
                user_id="system",
                session_id="consolidation_session",
            )

            formatted_messages = MemoryStore._format_messages(messages)
            user_message = types.Content(
                parts=[types.Part(text=f"Consolidate this conversation:\n\n{formatted_messages}")],
                role="user",
            )

            final_response = None
            async for event in runner.run_async(
                user_id="system",
                session_id="consolidation_session",
                new_message=user_message,
            ):
                if event.is_final_response():
                    if event.content and event.content.parts:
                        final_response = event.content.parts[0].text

            if final_response:
                ts = datetime.now().strftime("%Y-%m-%d %H:%M")
                self.store.append_history(f"[{ts}] {final_response}")
                self.store._consecutive_failures = 0
                return True

            return self.store._fail_or_raw_archive(messages)

        except ImportError:
            logger.warning("ADK not available, using fallback consolidation")
            return self.store._fail_or_raw_archive(messages)
        except Exception:
            logger.exception("ADK consolidation failed")
            return self.store._fail_or_raw_archive(messages)

    def pick_consolidation_boundary(
        self,
        session: Any,
        tokens_to_remove: int,
    ) -> tuple[int, int] | None:
        """Pick a user-turn boundary that removes enough old prompt tokens."""
        start = session.last_consolidated
        if start >= len(session.messages) or tokens_to_remove <= 0:
            return None

        removed_tokens = 0
        last_boundary: tuple[int, int] | None = None

        for idx in range(start, len(session.messages)):
            message = session.messages[idx]
            if idx > start and message.get("role") == "user":
                last_boundary = (idx, removed_tokens)
                if removed_tokens >= tokens_to_remove:
                    return last_boundary
            removed_tokens += estimate_message_tokens(message)

        return last_boundary

    def estimate_session_prompt_tokens(self, session: Any) -> tuple[int, str]:
        """Estimate current prompt size for the normal session history view."""
        history = session.get_history(max_messages=0)
        channel, chat_id = session.key.split(":", 1) if ":" in session.key else (None, None)

        if self._build_messages is None:
            return (0, "no_build_messages")

        probe_messages = self._build_messages(
            history=history,
            current_message="[token-probe]",
            channel=channel,
            chat_id=chat_id,
        )

        if self._get_tool_definitions is None:
            return (0, "no_tool_definitions")

        total = sum(estimate_message_tokens(msg) for msg in probe_messages)
        return (total, "local_estimation")

    async def archive_messages(self, messages: list[dict[str, object]]) -> bool:
        """Archive messages with guaranteed persistence."""
        if not messages:
            return True

        for _ in range(self.store._MAX_FAILURES_BEFORE_RAW_ARCHIVE):
            if await self.consolidate_messages(messages):
                return True
        return True

    async def maybe_consolidate_by_tokens(self, session: Any) -> None:
        """Archive old messages until prompt fits within safe budget."""
        if (
            not session.messages
            or self.context_window_tokens is None
            or self.context_window_tokens <= 0
        ):
            return

        lock = self.get_lock(session.key)
        async with lock:
            budget = self.context_window_tokens - self.max_completion_tokens - self._SAFETY_BUFFER
            target = budget // 2
            estimated, source = self.estimate_session_prompt_tokens(session)

            if estimated <= 0:
                return

            if estimated < budget:
                logger.debug(
                    "Token consolidation idle {}: {}/{} via {}",
                    session.key,
                    estimated,
                    self.context_window_tokens,
                    source,
                )
                return

            for round_num in range(self._MAX_CONSOLIDATION_ROUNDS):
                if estimated <= target:
                    return

                boundary = self.pick_consolidation_boundary(session, max(1, estimated - target))
                if boundary is None:
                    logger.debug(
                        "Token consolidation: no safe boundary for {} (round {})",
                        session.key,
                        round_num,
                    )
                    return

                end_idx = boundary[0]
                chunk = session.messages[session.last_consolidated : end_idx]

                if not chunk:
                    return

                logger.info(
                    "Token consolidation round {} for {}: {}/{} via {}, chunk={} msgs",
                    round_num,
                    session.key,
                    estimated,
                    self.context_window_tokens,
                    source,
                    len(chunk),
                )

                if not await self.consolidate_messages(chunk):
                    return

                session.last_consolidated = end_idx

                if self.sessions:
                    self.sessions.save(session)

                estimated, source = self.estimate_session_prompt_tokens(session)
                if estimated <= 0:
                    return


# Backward compatibility alias
MemoryConsolidator = AdkMemoryConsolidator
