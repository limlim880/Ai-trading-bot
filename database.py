"""
database.py

SQLite persistence layer. Deliberately plain sqlite3 (no ORM) -- the schema
is simple enough that SQLAlchemy would add ceremony without real benefit
right now, per the project's "SQLAlchemy only if it materially improves
the code" rule. If we later migrate to Postgres, this module is the only
place that needs to change (every other module goes through these
functions, never touches sqlite3 directly).

A new connection is opened per call rather than shared across threads.
FastAPI runs sync route handlers in a thread pool, and SQLite connections
are not safe to share across threads without extra locking -- opening a
short-lived connection per call sidesteps that entirely and is more than
fast enough at this system's (single-user, low-frequency) volume.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator, Optional

from config import get_settings

logger = logging.getLogger(__name__)

_ACTIVE_STATUSES = ("ALERT_SENT", "ACTIVE")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    settings = get_settings()
    conn = sqlite3.connect(settings.DATABASE_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create tables if they don't exist yet. Safe to call on every startup."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_uid TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                strategy TEXT NOT NULL DEFAULT 'four_hour_trend_pullback',
                timeframe_trend TEXT,
                timeframe_setup TEXT,
                price_at_signal REAL,
                entry REAL NOT NULL,
                stop_loss REAL NOT NULL,
                take_profit REAL NOT NULL,
                risk_reward REAL,
                account_balance REAL,
                risk_percent REAL,
                risk_amount REAL,
                position_size REAL,
                potential_profit REAL,
                score INTEGER,
                score_breakdown TEXT,
                indicators TEXT,
                qualification_reasons TEXT,
                rejection_reasons TEXT,
                news_note TEXT,
                spread_note TEXT,
                status TEXT NOT NULL DEFAULT 'ALERT_SENT',
                activated_at TEXT,
                exit_at TEXT,
                exit_price REAL,
                result TEXT,
                profit_loss REAL,
                mfe REAL,
                mae REAL,
                duration_minutes REAL,
                session TEXT,
                user_took_trade INTEGER,
                last_checked_price REAL
            );
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_symbol ON signals(symbol);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_status ON signals(status);")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS latest_prices (
                symbol TEXT PRIMARY KEY,
                price REAL NOT NULL,
                bid REAL,
                ask REAL,
                updated_at TEXT NOT NULL
            );
            """
        )
    logger.info("Database initialised")


def has_active_duplicate(symbol: str, direction: str) -> bool:
    """True if a non-terminal signal already exists for this symbol+direction.

    This is the whole of "duplicate-signal protection": an active EURUSD BUY
    blocks another EURUSD BUY from being created while it's still open.
    """
    with get_connection() as conn:
        row = conn.execute(
            f"""
            SELECT 1 FROM signals
            WHERE symbol = ? AND direction = ? AND status IN ({','.join('?' * len(_ACTIVE_STATUSES))})
            LIMIT 1;
            """,
            (symbol, direction, *_ACTIVE_STATUSES),
        ).fetchone()
        return row is not None


def insert_signal(data: dict[str, Any]) -> str:
    """Insert a new signal record. Returns the generated signal_uid."""
    signal_uid = str(uuid.uuid4())
    now = _now()
    row = {
        "signal_uid": signal_uid,
        "created_at": now,
        "updated_at": now,
        "status": "ALERT_SENT",
        **data,
    }
    # JSON-encode any dict/list values so sqlite3 can store them as TEXT.
    for key, value in list(row.items()):
        if isinstance(value, (dict, list)):
            row[key] = json.dumps(value)

    columns = ", ".join(row.keys())
    placeholders = ", ".join("?" for _ in row)
    with get_connection() as conn:
        conn.execute(
            f"INSERT INTO signals ({columns}) VALUES ({placeholders});",
            tuple(row.values()),
        )
    return signal_uid


_JSON_FIELDS = {"score_breakdown", "indicators", "qualification_reasons", "rejection_reasons"}


def _deserialize(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    for field in _JSON_FIELDS:
        if result.get(field):
            try:
                result[field] = json.loads(result[field])
            except (json.JSONDecodeError, TypeError):
                pass
    return result


def get_signal(signal_uid: str) -> Optional[dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM signals WHERE signal_uid = ?;", (signal_uid,)).fetchone()
        return _deserialize(row) if row else None


def get_active_signals() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT * FROM signals WHERE status IN ({','.join('?' * len(_ACTIVE_STATUSES))});",
            _ACTIVE_STATUSES,
        ).fetchall()
        return [_deserialize(r) for r in rows]


def list_recent_signals(limit: int = 20) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM signals ORDER BY created_at DESC LIMIT ?;", (limit,)
        ).fetchall()
        return [_deserialize(r) for r in rows]


def update_signal(signal_uid: str, **fields: Any) -> None:
    """Generic partial update. Pass column=value kwargs, e.g.
    update_signal(uid, status="ACTIVE", activated_at=now)
    """
    if not fields:
        return
    fields["updated_at"] = _now()
    for key, value in list(fields.items()):
        if isinstance(value, (dict, list)):
            fields[key] = json.dumps(value)

    set_clause = ", ".join(f"{k} = ?" for k in fields)
    with get_connection() as conn:
        conn.execute(
            f"UPDATE signals SET {set_clause} WHERE signal_uid = ?;",
            (*fields.values(), signal_uid),
        )


def upsert_latest_price(symbol: str, price: float, bid: Optional[float], ask: Optional[float]) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO latest_prices (symbol, price, bid, ask, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                price = excluded.price,
                bid = excluded.bid,
                ask = excluded.ask,
                updated_at = excluded.updated_at;
            """,
            (symbol, price, bid, ask, _now()),
        )


def get_latest_price(symbol: str) -> Optional[dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM latest_prices WHERE symbol = ?;", (symbol,)).fetchone()
        return dict(row) if row else None
