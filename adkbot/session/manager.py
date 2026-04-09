"""Session management with ADK SessionService integration."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

from adkbot.config.paths import get_legacy_sessions_dir
from adkbot.utils.helpers import ensure_dir, find_legal_message_start, safe_filename

if TYPE_CHECKING:
    from google.adk.sessions import BaseSessionService
    from google.adk.sessions import Session as AdkSession


@dataclass
class Session:
    """A conversation session."""

    key: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)
    last_consolidated: int = 0

    def add_message(self, role: str, content: str, **kwargs: Any) -> None:
        msg = {"role": role, "content": content, "timestamp": datetime.now().isoformat(), **kwargs}
        self.messages.append(msg)
        self.updated_at = datetime.now()

    def get_history(self, max_messages: int = 500) -> list[dict[str, Any]]:
        unconsolidated = self.messages[self.last_consolidated :]
        sliced = unconsolidated[-max_messages:]

        for i, message in enumerate(sliced):
            if message.get("role") == "user":
                sliced = sliced[i:]
                break

        start = find_legal_message_start(sliced)
        if start:
            sliced = sliced[start:]

        out: list[dict[str, Any]] = []
        for message in sliced:
            entry: dict[str, Any] = {"role": message["role"], "content": message.get("content", "")}
            for key in ("tool_calls", "tool_call_id", "name"):
                if key in message:
                    entry[key] = message[key]
            out.append(entry)
        return out

    def clear(self) -> None:
        self.messages = []
        self.last_consolidated = 0
        self.updated_at = datetime.now()

    def retain_recent_legal_suffix(self, max_messages: int) -> None:
        if max_messages <= 0:
            self.clear()
            return
        if len(self.messages) <= max_messages:
            return

        start_idx = max(0, len(self.messages) - max_messages)
        while start_idx > 0 and self.messages[start_idx].get("role") != "user":
            start_idx -= 1

        retained = self.messages[start_idx:]
        start = find_legal_message_start(retained)
        if start:
            retained = retained[start:]

        dropped = len(self.messages) - len(retained)
        self.messages = retained
        self.last_consolidated = max(0, self.last_consolidated - dropped)
        self.updated_at = datetime.now()


class SessionManager:
    """Manages conversation sessions with optional ADK SessionService integration."""

    def __init__(
        self,
        workspace: Path,
        use_adk: bool = True,
        adk_session_service: "BaseSessionService | None" = None,
    ):
        self.workspace = workspace
        self.use_adk = use_adk
        self.sessions_dir = ensure_dir(self.workspace / "sessions")
        self.legacy_sessions_dir = get_legacy_sessions_dir()
        self._cache: dict[str, Session] = {}
        self._adk_service = adk_session_service
        self._adk_sessions: dict[str, Any] = {}

        if use_adk and adk_session_service is None:
            self._init_adk_service()

    def _init_adk_service(self) -> None:
        try:
            from google.adk.sessions import InMemorySessionService

            self._adk_service = InMemorySessionService()
        except ImportError:
            logger.warning("ADK not available, using file-based session management")
            self.use_adk = False

    def _get_session_path(self, key: str) -> Path:
        safe_key = safe_filename(key.replace(":", "_"))
        return self.sessions_dir / f"{safe_key}.jsonl"

    def _get_legacy_session_path(self, key: str) -> Path:
        safe_key = safe_filename(key.replace(":", "_"))
        return self.legacy_sessions_dir / f"{safe_key}.jsonl"

    def get_or_create(self, key: str) -> Session:
        if key in self._cache:
            return self._cache[key]

        session = self._load(key)
        if session is None:
            session = Session(key=key)

        self._cache[key] = session
        return session

    async def get_or_create_adk_session(
        self,
        app_name: str,
        user_id: str,
        session_id: str,
        initial_state: dict[str, Any] | None = None,
    ) -> "AdkSession | Session":
        """Get or create an ADK session, falling back to file-based sessions if unavailable."""
        cache_key = f"{app_name}:{user_id}:{session_id}"

        if cache_key in self._adk_sessions:
            return self._adk_sessions[cache_key]

        if self._adk_service is not None:
            try:
                session = await self._adk_service.create_session(
                    app_name=app_name,
                    user_id=user_id,
                    session_id=session_id,
                    state=initial_state or {},
                )
                self._adk_sessions[cache_key] = session
                return session
            except Exception as e:
                logger.warning("ADK session creation failed: {}, falling back", e)

        legacy_key = f"{app_name}:{user_id}:{session_id}"
        return self.get_or_create(legacy_key)

    def _load(self, key: str) -> Session | None:
        path = self._get_session_path(key)

        if not path.exists():
            legacy_path = self._get_legacy_session_path(key)
            if legacy_path.exists():
                try:
                    shutil.move(str(legacy_path), str(path))
                    logger.info("Migrated session {} from legacy path", key)
                except Exception:
                    logger.exception("Failed to migrate session {}", key)

        if not path.exists():
            return None

        try:
            messages = []
            metadata = {}
            created_at = None
            last_consolidated = 0

            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    if data.get("_type") == "metadata":
                        metadata = data.get("metadata", {})
                        created_at = (
                            datetime.fromisoformat(data["created_at"])
                            if data.get("created_at")
                            else None
                        )
                        last_consolidated = data.get("last_consolidated", 0)
                    else:
                        messages.append(data)

            return Session(
                key=key,
                messages=messages,
                created_at=created_at or datetime.now(),
                metadata=metadata,
                last_consolidated=last_consolidated,
            )
        except Exception as e:
            logger.warning("Failed to load session {}: {}", key, e)
            return None

    def save(self, session: Session) -> None:
        path = self._get_session_path(session.key)

        with open(path, "w", encoding="utf-8") as f:
            metadata_line = {
                "_type": "metadata",
                "key": session.key,
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
                "metadata": session.metadata,
                "last_consolidated": session.last_consolidated,
            }
            f.write(json.dumps(metadata_line, ensure_ascii=False) + "\n")
            for msg in session.messages:
                f.write(json.dumps(msg, ensure_ascii=False) + "\n")

        self._cache[session.key] = session

    async def save_adk_session(self, app_name: str, user_id: str, session_id: str) -> None:
        """Save ADK session state."""
        if self._adk_service is None:
            return

        cache_key = f"{app_name}:{user_id}:{session_id}"
        if cache_key not in self._adk_sessions:
            return

        try:
            session = await self._adk_service.get_session(
                app_name=app_name,
                user_id=user_id,
                session_id=session_id,
            )
            self._adk_sessions[cache_key] = session
        except Exception as e:
            logger.warning("Failed to save ADK session: {}", e)

    def invalidate(self, key: str) -> None:
        self._cache.pop(key, None)

    def list_sessions(self) -> list[dict[str, Any]]:
        sessions = []
        for path in self.sessions_dir.glob("*.jsonl"):
            try:
                with open(path, encoding="utf-8") as f:
                    first_line = f.readline().strip()
                    if first_line:
                        data = json.loads(first_line)
                        if data.get("_type") == "metadata":
                            key = data.get("key") or path.stem.replace("_", ":", 1)
                            sessions.append(
                                {
                                    "key": key,
                                    "created_at": data.get("created_at"),
                                    "updated_at": data.get("updated_at"),
                                    "path": str(path),
                                }
                            )
            except Exception:
                continue
        return sorted(sessions, key=lambda x: x.get("updated_at", ""), reverse=True)

    async def list_adk_sessions(self, app_name: str, user_id: str) -> list[dict[str, Any]]:
        """List ADK sessions for a user."""
        if self._adk_service is None:
            return []

        try:
            response = await self._adk_service.list_sessions(
                app_name=app_name,
                user_id=user_id,
            )
            return [
                {
                    "session_id": s.id,
                    "created_at": getattr(s, "created_at", None),
                    "updated_at": getattr(s, "updated_at", None),
                }
                for s in response.sessions
            ]
        except Exception as e:
            logger.warning("Failed to list ADK sessions: {}", e)
            return []

    async def delete_adk_session(self, app_name: str, user_id: str, session_id: str) -> bool:
        """Delete an ADK session."""
        if self._adk_service is None:
            return False

        try:
            await self._adk_service.delete_session(
                app_name=app_name,
                user_id=user_id,
                session_id=session_id,
            )
            cache_key = f"{app_name}:{user_id}:{session_id}"
            self._adk_sessions.pop(cache_key, None)
            return True
        except Exception as e:
            logger.warning("Failed to delete ADK session: {}", e)
            return False


class DatabaseSessionManager(SessionManager):
    """Session manager with database persistence using ADK DatabaseSessionService."""

    def __init__(
        self,
        workspace: Path,
        db_url: str = "sqlite+aiosqlite:///./sessions.db",
    ):
        self.db_url = db_url
        self._db_service = None
        super().__init__(workspace, use_adk=False)

    def _init_adk_service(self) -> None:
        try:
            from google.adk.sessions import DatabaseSessionService

            self._db_service = DatabaseSessionService(db_url=self.db_url)
            self._adk_service = self._db_service
            self.use_adk = True
        except ImportError:
            logger.warning("ADK database session service not available")
            super()._init_adk_service()
