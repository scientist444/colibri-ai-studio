"""SQLite connection manager with WAL mode and schema migration support."""

from __future__ import annotations

import logging
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.database.migrations import apply_migrations
from app.utils.paths import get_database_path

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Thread-safe SQLite database manager."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path: Path = db_path or get_database_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=15.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        return conn

    def initialize(self) -> None:
        """Initialize the database and run pending schema migrations."""
        with self.connection() as conn:
            apply_migrations(conn)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        """Yield a managed SQLite connection with commit/rollback semantics."""
        with self._lock:
            conn = self._connect()
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
