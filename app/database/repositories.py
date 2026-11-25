"""Repositories for conversations, messages, installed models, downloads, and benchmarks."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.database.database import DatabaseManager
from app.models.download_models import DownloadStatus, DownloadTaskItem
from app.models.model_metadata import InstalledModelRecord


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ConversationRepository:
    """CRUD operations for chat conversations and messages."""

    def __init__(self, db: DatabaseManager) -> None:
        self.db = db

    def create_conversation(
        self,
        title: str = "New Conversation",
        model_id: str = "",
        system_prompt: str = "",
    ) -> dict[str, Any]:
        conv_id = str(uuid.uuid4())
        now = _utc_now()
        with self.db.connection() as conn:
            conn.execute(
                """
                INSERT INTO conversations (id, title, model_id, system_prompt, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (conv_id, title, model_id, system_prompt, now, now),
            )
        return {
            "id": conv_id,
            "title": title,
            "model_id": model_id,
            "system_prompt": system_prompt,
            "created_at": now,
            "updated_at": now,
        }

    def list_conversations(self, search_query: str = "") -> list[dict[str, Any]]:
        with self.db.connection() as conn:
            if search_query.strip():
                pattern = f"%{search_query.strip()}%"
                rows = conn.execute(
                    """
                    SELECT DISTINCT c.*
                    FROM conversations c
                    LEFT JOIN messages m ON m.conversation_id = c.id
                    WHERE c.title LIKE ? OR m.content LIKE ?
                    ORDER BY c.updated_at DESC;
                    """,
                    (pattern, pattern),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM conversations ORDER BY updated_at DESC;"
                ).fetchall()
        return [dict(r) for r in rows]

    def get_conversation(self, conv_id: str) -> dict[str, Any] | None:
        with self.db.connection() as conn:
            row = conn.execute(
                "SELECT * FROM conversations WHERE id = ?;",
                (conv_id,),
            ).fetchone()
        return dict(row) if row else None

    def rename_conversation(self, conv_id: str, new_title: str) -> None:
        now = _utc_now()
        with self.db.connection() as conn:
            conn.execute(
                "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?;",
                (new_title.strip() or "Untitled Conversation", now, conv_id),
            )

    def update_conversation_settings(
        self,
        conv_id: str,
        model_id: str | None = None,
        system_prompt: str | None = None,
    ) -> None:
        now = _utc_now()
        with self.db.connection() as conn:
            if model_id is not None:
                conn.execute(
                    "UPDATE conversations SET model_id = ?, updated_at = ? WHERE id = ?;",
                    (model_id, now, conv_id),
                )
            if system_prompt is not None:
                conn.execute(
                    "UPDATE conversations SET system_prompt = ?, updated_at = ? WHERE id = ?;",
                    (system_prompt, now, conv_id),
                )

    def delete_conversation(self, conv_id: str) -> None:
        with self.db.connection() as conn:
            conn.execute("DELETE FROM conversations WHERE id = ?;", (conv_id,))

    def clear_all_conversations(self) -> None:
        with self.db.connection() as conn:
            conn.execute("DELETE FROM messages;")
            conn.execute("DELETE FROM conversations;")

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        reasoning_content: str = "",
        model_id: str = "",
        tokens_per_sec: float = 0.0,
        ttft_ms: float = 0.0,
        token_count: int = 0,
    ) -> dict[str, Any]:
        msg_id = str(uuid.uuid4())
        now = _utc_now()
        with self.db.connection() as conn:
            conn.execute(
                """
                INSERT INTO messages (
                    id, conversation_id, role, content, reasoning_content,
                    model_id, tokens_per_sec, ttft_ms, token_count, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    msg_id,
                    conversation_id,
                    role,
                    content,
                    reasoning_content,
                    model_id,
                    tokens_per_sec,
                    ttft_ms,
                    token_count,
                    now,
                ),
            )
            conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?;",
                (now, conversation_id),
            )
        return {
            "id": msg_id,
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "reasoning_content": reasoning_content,
            "model_id": model_id,
            "tokens_per_sec": tokens_per_sec,
            "ttft_ms": ttft_ms,
            "token_count": token_count,
            "created_at": now,
        }

    def get_messages(self, conversation_id: str) -> list[dict[str, Any]]:
        with self.db.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC;",
                (conversation_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_last_assistant_message(self, conversation_id: str) -> None:
        with self.db.connection() as conn:
            row = conn.execute(
                """
                SELECT id FROM messages
                WHERE conversation_id = ? AND role = 'assistant'
                ORDER BY created_at DESC LIMIT 1;
                """,
                (conversation_id,),
            ).fetchone()
            if row:
                conn.execute("DELETE FROM messages WHERE id = ?;", (row["id"],))


class InstalledModelsRepository:
    """CRUD operations for locally installed Colibri models."""

    def __init__(self, db: DatabaseManager) -> None:
        self.db = db

    def upsert_model(self, record: InstalledModelRecord) -> None:
        installed_at = record.installed_at or _utc_now()
        with self.db.connection() as conn:
            conn.execute(
                """
                INSERT INTO installed_models (
                    model_id, display_name, hf_repo, local_path, family,
                    architecture, quantization, size_bytes, installed_at,
                    verified, source_type, notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(model_id) DO UPDATE SET
                    display_name = excluded.display_name,
                    hf_repo = excluded.hf_repo,
                    local_path = excluded.local_path,
                    family = excluded.family,
                    architecture = excluded.architecture,
                    quantization = excluded.quantization,
                    size_bytes = excluded.size_bytes,
                    installed_at = excluded.installed_at,
                    verified = excluded.verified,
                    source_type = excluded.source_type,
                    notes = excluded.notes;
                """,
                (
                    record.model_id,
                    record.display_name,
                    record.hf_repo,
                    record.local_path,
                    record.family,
                    record.architecture,
                    record.quantization,
                    record.size_bytes,
                    installed_at,
                    1 if record.verified else 0,
                    record.source_type,
                    record.notes,
                ),
            )

    def list_models(self) -> list[InstalledModelRecord]:
        with self.db.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM installed_models ORDER BY installed_at DESC;"
            ).fetchall()
        return [
            InstalledModelRecord(
                model_id=r["model_id"],
                display_name=r["display_name"],
                hf_repo=r["hf_repo"],
                local_path=r["local_path"],
                family=r["family"],
                architecture=r["architecture"],
                quantization=r["quantization"],
                size_bytes=int(r["size_bytes"]),
                installed_at=r["installed_at"],
                verified=bool(r["verified"]),
                source_type=r["source_type"],
                notes=r["notes"],
            )
            for r in rows
        ]

    def get_model(self, model_id: str) -> InstalledModelRecord | None:
        with self.db.connection() as conn:
            r = conn.execute(
                "SELECT * FROM installed_models WHERE model_id = ?;",
                (model_id,),
            ).fetchone()
        if not r:
            return None
        return InstalledModelRecord(
            model_id=r["model_id"],
            display_name=r["display_name"],
            hf_repo=r["hf_repo"],
            local_path=r["local_path"],
            family=r["family"],
            architecture=r["architecture"],
            quantization=r["quantization"],
            size_bytes=int(r["size_bytes"]),
            installed_at=r["installed_at"],
            verified=bool(r["verified"]),
            source_type=r["source_type"],
            notes=r["notes"],
        )

    def remove_model(self, model_id: str) -> None:
        with self.db.connection() as conn:
            conn.execute("DELETE FROM installed_models WHERE model_id = ?;", (model_id,))


class DownloadTasksRepository:
    """Persistence for download tasks across application restarts."""

    def __init__(self, db: DatabaseManager) -> None:
        self.db = db

    def upsert_task(self, task: DownloadTaskItem) -> None:
        now = _utc_now()
        with self.db.connection() as conn:
            conn.execute(
                """
                INSERT INTO download_tasks (
                    task_id, model_id, display_name, hf_repo, target_dir,
                    status, bytes_downloaded, total_bytes, error_message,
                    requires_gguf_import, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                    status = excluded.status,
                    bytes_downloaded = excluded.bytes_downloaded,
                    total_bytes = excluded.total_bytes,
                    error_message = excluded.error_message,
                    updated_at = excluded.updated_at;
                """,
                (
                    task.task_id,
                    task.model_id,
                    task.display_name,
                    task.hf_repo,
                    task.target_dir,
                    task.status.value,
                    task.bytes_downloaded,
                    task.total_bytes,
                    task.error_message,
                    1 if task.requires_gguf_import else 0,
                    now,
                ),
            )

    def list_tasks(self) -> list[DownloadTaskItem]:
        with self.db.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM download_tasks ORDER BY updated_at DESC;"
            ).fetchall()
        result: list[DownloadTaskItem] = []
        for r in rows:
            status_val = r["status"]
            try:
                status = DownloadStatus(status_val)
            except ValueError:
                status = DownloadStatus.FAILED
            result.append(
                DownloadTaskItem(
                    task_id=r["task_id"],
                    model_id=r["model_id"],
                    display_name=r["display_name"],
                    hf_repo=r["hf_repo"],
                    target_dir=r["target_dir"],
                    status=status,
                    bytes_downloaded=int(r["bytes_downloaded"]),
                    total_bytes=int(r["total_bytes"]),
                    error_message=r["error_message"],
                    requires_gguf_import=bool(r["requires_gguf_import"]),
                )
            )
        return result

    def delete_task(self, task_id: str) -> None:
        with self.db.connection() as conn:
            conn.execute("DELETE FROM download_tasks WHERE task_id = ?;", (task_id,))


class BenchmarkRepository:
    """Persistence for Performance Lab benchmark runs."""

    def __init__(self, db: DatabaseManager) -> None:
        self.db = db

    def add_benchmark(
        self,
        model_id: str,
        backend: str,
        ctx_tokens: int,
        threads: int,
        policy: str,
        prompt_name: str,
        ttft_ms: float,
        decode_tok_s: float,
        prefill_tok_s: float,
        peak_ram_gb: float,
        peak_vram_gb: float,
        storage_seq_mb_s: float = 0.0,
        notes: str = "",
    ) -> dict[str, Any]:
        bench_id = str(uuid.uuid4())
        now = _utc_now()
        with self.db.connection() as conn:
            conn.execute(
                """
                INSERT INTO benchmarks (
                    id, model_id, backend, ctx_tokens, threads, policy, prompt_name,
                    ttft_ms, decode_tok_s, prefill_tok_s, peak_ram_gb, peak_vram_gb,
                    storage_seq_mb_s, created_at, notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    bench_id,
                    model_id,
                    backend,
                    ctx_tokens,
                    threads,
                    policy,
                    prompt_name,
                    ttft_ms,
                    decode_tok_s,
                    prefill_tok_s,
                    peak_ram_gb,
                    peak_vram_gb,
                    storage_seq_mb_s,
                    now,
                    notes,
                ),
            )
        return {
            "id": bench_id,
            "model_id": model_id,
            "backend": backend,
            "ctx_tokens": ctx_tokens,
            "threads": threads,
            "policy": policy,
            "prompt_name": prompt_name,
            "ttft_ms": ttft_ms,
            "decode_tok_s": decode_tok_s,
            "prefill_tok_s": prefill_tok_s,
            "peak_ram_gb": peak_ram_gb,
            "peak_vram_gb": peak_vram_gb,
            "storage_seq_mb_s": storage_seq_mb_s,
            "created_at": now,
            "notes": notes,
        }

    def list_benchmarks(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.db.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM benchmarks ORDER BY created_at DESC LIMIT ?;",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
