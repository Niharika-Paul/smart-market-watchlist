"""Data-access layer for users, watchlists, and per-stock checkpoints."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _parse_dt(value: str | None) -> datetime | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


@dataclass(frozen=True)
class User:
    id: int
    username: str
    created_at: datetime


@dataclass(frozen=True)
class Watchlist:
    id: int
    user_id: int
    name: str
    last_acknowledged_at: datetime | None
    created_at: datetime


@dataclass(frozen=True)
class WatchlistItem:
    id: int
    watchlist_id: int
    symbol: str
    added_at: datetime
    checkpoint_at: datetime


class DuplicateError(ValueError):
    """Raised when a unique constraint would be violated."""


class NotFoundError(LookupError):
    """Raised when a requested row does not exist."""


class WatchlistRepository:
    """SQL stays here so the rest of the backend can use objects, not queries."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def create_user(self, username: str, *, now: datetime | None = None) -> User:
        stamp = _iso(now or _utcnow())
        name = username.strip()
        if not name:
            raise ValueError("username is required")
        try:
            cursor = self._conn.execute(
                "INSERT INTO users (username, created_at) VALUES (?, ?)",
                (name, stamp),
            )
            self._conn.commit()
        except sqlite3.IntegrityError as exc:
            raise DuplicateError(f"user already exists: {name}") from exc
        return self.get_user(int(cursor.lastrowid))

    def get_user(self, user_id: int) -> User:
        row = self._conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if row is None:
            raise NotFoundError(f"user not found: {user_id}")
        return _user_from_row(row)

    def get_user_by_username(self, username: str) -> User:
        row = self._conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username.strip(),),
        ).fetchone()
        if row is None:
            raise NotFoundError(f"user not found: {username}")
        return _user_from_row(row)

    def create_watchlist(
        self,
        user_id: int,
        name: str,
        *,
        now: datetime | None = None,
    ) -> Watchlist:
        self.get_user(user_id)
        stamp = _iso(now or _utcnow())
        title = name.strip()
        if not title:
            raise ValueError("watchlist name is required")
        try:
            cursor = self._conn.execute(
                """
                INSERT INTO watchlists (user_id, name, last_acknowledged_at, created_at)
                VALUES (?, ?, NULL, ?)
                """,
                (user_id, title, stamp),
            )
            self._conn.commit()
        except sqlite3.IntegrityError as exc:
            raise DuplicateError(f"watchlist already exists for user {user_id}: {title}") from exc
        return self.get_watchlist(int(cursor.lastrowid))

    def get_watchlist(self, watchlist_id: int) -> Watchlist:
        row = self._conn.execute(
            "SELECT * FROM watchlists WHERE id = ?",
            (watchlist_id,),
        ).fetchone()
        if row is None:
            raise NotFoundError(f"watchlist not found: {watchlist_id}")
        return _watchlist_from_row(row)

    def get_watchlist_by_name(self, user_id: int, name: str) -> Watchlist:
        row = self._conn.execute(
            """
            SELECT * FROM watchlists
            WHERE user_id = ? AND name = ?
            """,
            (user_id, name.strip()),
        ).fetchone()
        if row is None:
            raise NotFoundError(f"watchlist not found for user {user_id}: {name}")
        return _watchlist_from_row(row)

    def add_stock(
        self,
        watchlist_id: int,
        symbol: str,
        *,
        now: datetime | None = None,
    ) -> WatchlistItem:
        """Add a symbol and set its initial baseline/checkpoint to ``now``."""
        self.get_watchlist(watchlist_id)
        ticker = symbol.strip()
        if not ticker:
            raise ValueError("symbol is required")
        stamp = _iso(now or _utcnow())
        try:
            cursor = self._conn.execute(
                """
                INSERT INTO watchlist_items (watchlist_id, symbol, added_at, checkpoint_at)
                VALUES (?, ?, ?, ?)
                """,
                (watchlist_id, ticker, stamp, stamp),
            )
            self._conn.commit()
        except sqlite3.IntegrityError as exc:
            raise DuplicateError(
                f"symbol already on watchlist {watchlist_id}: {ticker}"
            ) from exc
        return self.get_item(int(cursor.lastrowid))

    def remove_stock(self, watchlist_id: int, symbol: str) -> None:
        """Remove a symbol from a watchlist."""
        self.get_watchlist(watchlist_id)
        item = self.get_item_by_symbol(watchlist_id, symbol)
        self._conn.execute(
            "DELETE FROM watchlist_items WHERE id = ?",
            (item.id,),
        )
        self._conn.commit()

    def get_item(self, item_id: int) -> WatchlistItem:
        row = self._conn.execute(
            "SELECT * FROM watchlist_items WHERE id = ?",
            (item_id,),
        ).fetchone()
        if row is None:
            raise NotFoundError(f"watchlist item not found: {item_id}")
        return _item_from_row(row)

    def get_item_by_symbol(self, watchlist_id: int, symbol: str) -> WatchlistItem:
        row = self._conn.execute(
            """
            SELECT * FROM watchlist_items
            WHERE watchlist_id = ? AND symbol = ?
            """,
            (watchlist_id, symbol.strip()),
        ).fetchone()
        if row is None:
            raise NotFoundError(f"symbol {symbol!r} not on watchlist {watchlist_id}")
        return _item_from_row(row)

    def list_items(self, watchlist_id: int) -> list[WatchlistItem]:
        self.get_watchlist(watchlist_id)
        rows = self._conn.execute(
            """
            SELECT * FROM watchlist_items
            WHERE watchlist_id = ?
            ORDER BY added_at, id
            """,
            (watchlist_id,),
        ).fetchall()
        return [_item_from_row(row) for row in rows]

    def acknowledge_stock(
        self,
        watchlist_id: int,
        symbol: str,
        *,
        now: datetime | None = None,
    ) -> WatchlistItem:
        """Record an explicit user acknowledgement; does not run on data refresh."""
        item = self.get_item_by_symbol(watchlist_id, symbol)
        stamp = _iso(now or _utcnow())
        self._conn.execute(
            "UPDATE watchlist_items SET checkpoint_at = ? WHERE id = ?",
            (stamp, item.id),
        )
        self._conn.commit()
        return self.get_item(item.id)

    def set_stock_checkpoint(
        self,
        watchlist_id: int,
        symbol: str,
        checkpoint_at: datetime,
    ) -> WatchlistItem:
        item = self.get_item_by_symbol(watchlist_id, symbol)
        stamp = _iso(checkpoint_at)
        self._conn.execute(
            "UPDATE watchlist_items SET checkpoint_at = ? WHERE id = ?",
            (stamp, item.id),
        )
        self._conn.commit()
        return self.get_item(item.id)

    def acknowledge_watchlist(
        self,
        watchlist_id: int,
        *,
        now: datetime | None = None,
    ) -> list[WatchlistItem]:
        """Mark a watchlist visit: every member's checkpoint moves to ``now``."""
        self.get_watchlist(watchlist_id)
        stamp = _iso(now or _utcnow())
        self._conn.execute(
            "UPDATE watchlists SET last_acknowledged_at = ? WHERE id = ?",
            (stamp, watchlist_id),
        )
        self._conn.execute(
            "UPDATE watchlist_items SET checkpoint_at = ? WHERE watchlist_id = ?",
            (stamp, watchlist_id),
        )
        self._conn.commit()
        return self.list_items(watchlist_id)


def _user_from_row(row: sqlite3.Row) -> User:
    created = _parse_dt(row["created_at"])
    assert created is not None
    return User(id=int(row["id"]), username=row["username"], created_at=created)


def _watchlist_from_row(row: sqlite3.Row) -> Watchlist:
    created = _parse_dt(row["created_at"])
    assert created is not None
    return Watchlist(
        id=int(row["id"]),
        user_id=int(row["user_id"]),
        name=row["name"],
        last_acknowledged_at=_parse_dt(row["last_acknowledged_at"]),
        created_at=created,
    )


def _item_from_row(row: sqlite3.Row) -> WatchlistItem:
    added = _parse_dt(row["added_at"])
    checkpoint = _parse_dt(row["checkpoint_at"])
    assert added is not None and checkpoint is not None
    return WatchlistItem(
        id=int(row["id"]),
        watchlist_id=int(row["watchlist_id"]),
        symbol=row["symbol"],
        added_at=added,
        checkpoint_at=checkpoint,
    )
