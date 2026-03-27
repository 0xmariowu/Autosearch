"""Cache search results to avoid redundant API calls."""

name = "cache_results"
description = "Cache search results in local SQLite database. Avoids repeating the same search query within the TTL window (default 1 hour). Dramatically reduces API calls for iterative research."
when = "Wrap around search capabilities. Check cache before searching, store after."
input_type = "any"
output_type = "any"

import hashlib
import json
import sqlite3
import time
from pathlib import Path

_DB_PATH = Path(__file__).parent.parent / "sources" / "cache.sqlite"
_DEFAULT_TTL = 3600  # 1 hour


def _get_db():
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.execute(
        "CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT, expires_at REAL)"
    )
    return conn


def _cache_key(query, provider=""):
    raw = f"{str(query).strip().lower()}|{str(provider).strip().lower()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def run(input_data, **context):
    action = context.get("action", "get")  # get | put | clear
    query = context.get("query", str(input_data or ""))
    provider = context.get("provider", "")
    ttl = context.get("ttl", _DEFAULT_TTL)

    key = _cache_key(query, provider)
    conn = _get_db()

    try:
        if action == "get":
            row = conn.execute(
                "SELECT value, expires_at FROM cache WHERE key = ?", (key,)
            ).fetchone()
            if row and row[1] > time.time():
                return {"hit": True, "data": json.loads(row[0])}
            return {"hit": False, "data": None}

        elif action == "put":
            data = input_data
            conn.execute(
                "INSERT OR REPLACE INTO cache (key, value, expires_at) VALUES (?, ?, ?)",
                (key, json.dumps(data, default=str), time.time() + ttl),
            )
            conn.commit()
            return {"stored": True, "key": key, "ttl": ttl}

        elif action == "clear":
            if query:
                conn.execute("DELETE FROM cache WHERE key = ?", (key,))
            else:
                conn.execute("DELETE FROM cache WHERE expires_at < ?", (time.time(),))
            conn.commit()
            return {"cleared": True}
    finally:
        conn.close()

    return {}


def test():
    import tempfile
    global _DB_PATH
    original = _DB_PATH
    _DB_PATH = Path(tempfile.mktemp(suffix=".sqlite"))
    try:
        # Store
        run(["result1", "result2"], action="put", query="test query", provider="ddgs")
        # Retrieve
        result = run(None, action="get", query="test query", provider="ddgs")
        assert result["hit"], "Cache should hit"
        assert result["data"] == ["result1", "result2"]
        # Miss with different query
        result = run(None, action="get", query="other query", provider="ddgs")
        assert not result["hit"], "Cache should miss"
        return "ok"
    finally:
        _DB_PATH = original
