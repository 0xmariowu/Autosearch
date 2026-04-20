# Source: crawl4ai/crawl4ai/async_database.py:L230-L249 (adapted)
import asyncio
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Self

from pydantic import BaseModel

from autosearch.core.models import Evidence, EvidenceDigest

try:
    import aiosqlite
except ImportError:  # pragma: no cover - compatibility path for blocked installs

    class _FallbackCursor:
        def __init__(self, cursor: sqlite3.Cursor) -> None:
            self._cursor = cursor

        @property
        def lastrowid(self) -> int | None:
            return self._cursor.lastrowid

        async def fetchone(self) -> sqlite3.Row | None:
            return self._cursor.fetchone()

        async def fetchall(self) -> list[sqlite3.Row]:
            return self._cursor.fetchall()

        async def close(self) -> None:
            self._cursor.close()

    class _FallbackConnection:
        def __init__(self, database: str) -> None:
            self._connection = sqlite3.connect(database, check_same_thread=False)

        @property
        def row_factory(self) -> Any:
            return self._connection.row_factory

        @row_factory.setter
        def row_factory(self, value: Any) -> None:
            self._connection.row_factory = value

        async def execute(
            self,
            query: str,
            params: tuple[Any, ...] = (),
        ) -> _FallbackCursor:
            return _FallbackCursor(self._connection.execute(query, params))

        async def executescript(self, script: str) -> None:
            self._connection.executescript(script)

        async def commit(self) -> None:
            self._connection.commit()

        async def close(self) -> None:
            self._connection.close()

    class _FallbackAioSqliteModule:
        Connection = _FallbackConnection
        Row = sqlite3.Row

        @staticmethod
        async def connect(database: str) -> _FallbackConnection:
            return _FallbackConnection(database)

    aiosqlite = _FallbackAioSqliteModule()


def _utc_now() -> datetime:
    return datetime.now(UTC)


class SessionStore:
    def __init__(self, connection: aiosqlite.Connection, db_path: str | Path) -> None:
        self._connection: aiosqlite.Connection | None = connection
        self.db_path = db_path
        self._write_lock = asyncio.Lock()

    @classmethod
    async def open(cls, db_path: str | Path) -> Self:
        database = str(db_path)
        if database != ":memory:":
            Path(database).parent.mkdir(parents=True, exist_ok=True)

        connection = await aiosqlite.connect(database)
        connection.row_factory = aiosqlite.Row

        store = cls(connection=connection, db_path=db_path)
        await store._initialize()
        return store

    async def close(self) -> None:
        if self._connection is None:
            return
        await self._connection.close()
        self._connection = None

    async def create_session(self, session_id: str, query: str, mode: str) -> None:
        async with self._write_lock:
            await self._connection_or_raise().execute(
                """
                INSERT INTO sessions (
                    id,
                    query,
                    mode,
                    started_at,
                    finished_at,
                    status,
                    markdown,
                    cost
                ) VALUES (?, ?, ?, ?, NULL, ?, NULL, 0.0)
                """,
                (session_id, query, mode, _utc_now().isoformat(), "started"),
            )
            await self._connection_or_raise().commit()

    async def finish_session(
        self,
        session_id: str,
        status: str,
        markdown: str | None,
        cost: float,
    ) -> None:
        async with self._write_lock:
            await self._connection_or_raise().execute(
                """
                UPDATE sessions
                SET finished_at = ?, status = ?, markdown = ?, cost = ?
                WHERE id = ?
                """,
                (_utc_now().isoformat(), status, markdown, cost, session_id),
            )
            await self._connection_or_raise().commit()

    async def add_evidence(self, session_id: str, rank: int, evidence: Evidence) -> None:
        async with self._write_lock:
            await self._connection_or_raise().execute(
                """
                INSERT OR REPLACE INTO evidence (
                    session_id,
                    rank,
                    url,
                    title,
                    snippet,
                    source_channel,
                    score
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    rank,
                    evidence.url,
                    evidence.title,
                    evidence.snippet,
                    evidence.source_channel,
                    evidence.score,
                ),
            )
            await self._connection_or_raise().commit()

    async def add_query_log(
        self,
        session_id: str,
        subquery: str,
        channel: str,
        results: int,
    ) -> None:
        async with self._write_lock:
            await self._connection_or_raise().execute(
                """
                INSERT INTO query_log (session_id, subquery, issued_at, channel, results)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, subquery, _utc_now().isoformat(), channel, results),
            )
            await self._connection_or_raise().commit()

    async def store_artifact(
        self,
        *,
        session_id: str,
        kind: str,
        payload: BaseModel,
    ) -> int:
        payload_json = payload.model_dump_json()
        if isinstance(payload, Evidence):
            payload_json = Evidence.model_validate(payload.to_slim_dict()).model_dump_json()

        async with self._write_lock:
            cursor = await self._connection_or_raise().execute(
                """
                INSERT INTO evidence_artifacts (session_id, kind, payload_json)
                VALUES (?, ?, ?)
                """,
                (session_id, kind, payload_json),
            )
            try:
                row_id = cursor.lastrowid
            finally:
                await cursor.close()

            await self._connection_or_raise().commit()
            if row_id is None:
                raise RuntimeError("Failed to determine inserted artifact row id.")
            return int(row_id)

    async def load_artifacts(
        self,
        *,
        session_id: str,
        kind: str | None = None,
    ) -> list[dict[str, Any]]:
        connection = self._connection_or_raise()
        if kind is None:
            rows = await self._fetch_all(
                connection,
                """
                SELECT id, kind, payload_json, created_at
                FROM evidence_artifacts
                WHERE session_id = ?
                ORDER BY id ASC
                """,
                (session_id,),
            )
        else:
            rows = await self._fetch_all(
                connection,
                """
                SELECT id, kind, payload_json, created_at
                FROM evidence_artifacts
                WHERE session_id = ? AND kind = ?
                ORDER BY id ASC
                """,
                (session_id, kind),
            )
        return [dict(row) for row in rows]

    async def load_digests(
        self,
        *,
        session_id: str,
    ) -> list[EvidenceDigest]:
        artifacts = await self.load_artifacts(
            session_id=session_id,
            kind="compacted_digest",
        )
        return [
            EvidenceDigest.model_validate_json(artifact["payload_json"]) for artifact in artifacts
        ]

    async def fetch_session(self, session_id: str) -> dict[str, Any] | None:
        connection = self._connection_or_raise()
        session = await self._fetch_one(
            connection,
            """
            SELECT id, query, mode, started_at, finished_at, status, markdown, cost
            FROM sessions
            WHERE id = ?
            """,
            (session_id,),
        )
        if session is None:
            return None

        evidence_rows = await self._fetch_all(
            connection,
            """
            SELECT session_id, rank, url, title, snippet, source_channel, score
            FROM evidence
            WHERE session_id = ?
            ORDER BY rank ASC
            """,
            (session_id,),
        )
        query_log_rows = await self._fetch_all(
            connection,
            """
            SELECT session_id, subquery, issued_at, channel, results
            FROM query_log
            WHERE session_id = ?
            ORDER BY issued_at ASC
            """,
            (session_id,),
        )

        payload = dict(session)
        payload["evidence"] = [dict(row) for row in evidence_rows]
        payload["query_log"] = [dict(row) for row in query_log_rows]
        return payload

    async def list_recent(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = await self._fetch_all(
            self._connection_or_raise(),
            """
            SELECT id, query, mode, started_at, finished_at, status, markdown, cost
            FROM sessions
            ORDER BY started_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(row) for row in rows]

    async def _initialize(self) -> None:
        async with self._write_lock:
            connection = self._connection_or_raise()
            await connection.execute("PRAGMA foreign_keys = ON")
            await connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    query TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT NULL,
                    status TEXT NOT NULL,
                    markdown TEXT NULL,
                    cost REAL DEFAULT 0.0
                );

                CREATE TABLE IF NOT EXISTS evidence (
                    session_id TEXT NOT NULL,
                    rank INTEGER NOT NULL,
                    url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    snippet TEXT NULL,
                    source_channel TEXT NOT NULL,
                    score REAL NULL,
                    PRIMARY KEY (session_id, rank),
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS query_log (
                    session_id TEXT NOT NULL,
                    subquery TEXT NOT NULL,
                    issued_at TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    results INTEGER NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS evidence_artifacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_evidence_artifacts_session
                ON evidence_artifacts(session_id);

                CREATE INDEX IF NOT EXISTS idx_evidence_artifacts_kind
                ON evidence_artifacts(session_id, kind);
                """
            )
            await connection.commit()

    def _connection_or_raise(self) -> aiosqlite.Connection:
        if self._connection is None:
            raise RuntimeError("SessionStore is not open.")
        return self._connection

    async def _fetch_one(
        self,
        connection: aiosqlite.Connection,
        query: str,
        params: tuple[Any, ...],
    ) -> aiosqlite.Row | None:
        cursor = await connection.execute(query, params)
        try:
            return await cursor.fetchone()
        finally:
            await cursor.close()

    async def _fetch_all(
        self,
        connection: aiosqlite.Connection,
        query: str,
        params: tuple[Any, ...],
    ) -> list[aiosqlite.Row]:
        cursor = await connection.execute(query, params)
        try:
            rows = await cursor.fetchall()
        finally:
            await cursor.close()
        return list(rows)
