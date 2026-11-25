"""SQLite database migrations for conversations, models, downloads, and benchmarks."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

MIGRATIONS: list[tuple[int, str, str]] = [
    (
        1,
        "initial_schema",
        """
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            model_id TEXT DEFAULT '',
            system_prompt TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            reasoning_content TEXT DEFAULT '',
            model_id TEXT DEFAULT '',
            tokens_per_sec REAL DEFAULT 0.0,
            ttft_ms REAL DEFAULT 0.0,
            token_count INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, created_at);

        CREATE TABLE IF NOT EXISTS installed_models (
            model_id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            hf_repo TEXT DEFAULT '',
            local_path TEXT NOT NULL,
            family TEXT DEFAULT 'qwen36',
            architecture TEXT DEFAULT '',
            quantization TEXT DEFAULT 'INT4',
            size_bytes INTEGER DEFAULT 0,
            installed_at TEXT NOT NULL,
            verified INTEGER DEFAULT 0,
            source_type TEXT DEFAULT 'catalog',
            notes TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS download_tasks (
            task_id TEXT PRIMARY KEY,
            model_id TEXT NOT NULL,
            display_name TEXT NOT NULL,
            hf_repo TEXT NOT NULL,
            target_dir TEXT NOT NULL,
            status TEXT NOT NULL,
            bytes_downloaded INTEGER DEFAULT 0,
            total_bytes INTEGER DEFAULT 0,
            error_message TEXT DEFAULT '',
            requires_gguf_import INTEGER DEFAULT 0,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS benchmarks (
            id TEXT PRIMARY KEY,
            model_id TEXT NOT NULL,
            backend TEXT NOT NULL,
            ctx_tokens INTEGER DEFAULT 4096,
            threads INTEGER DEFAULT 4,
            policy TEXT DEFAULT 'balanced',
            prompt_name TEXT DEFAULT 'Standard Benchmark',
            ttft_ms REAL DEFAULT 0.0,
            decode_tok_s REAL DEFAULT 0.0,
            prefill_tok_s REAL DEFAULT 0.0,
            peak_ram_gb REAL DEFAULT 0.0,
            peak_vram_gb REAL DEFAULT 0.0,
            storage_seq_mb_s REAL DEFAULT 0.0,
            created_at TEXT NOT NULL,
            notes TEXT DEFAULT ''
        );
        """,
    ),
]


def apply_migrations(conn: sqlite3.Connection) -> None:
    """Apply all pending SQL migrations in order."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL
        );
        """
    )
    rows = conn.execute("SELECT version FROM schema_migrations;").fetchall()
    applied = {int(r["version"]) for r in rows}

    for version, name, sql in MIGRATIONS:
        if version not in applied:
            logger.info("Applying database migration v%d (%s)", version, name)
            conn.executescript(sql)
            now_iso = datetime.now(timezone.utc).isoformat()
            conn.execute(
                "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?);",
                (version, name, now_iso),
            )
