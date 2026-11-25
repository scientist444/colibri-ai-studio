"""Tests for SQLite Database, Migrations, Repositories, and Export (`app/database/`)."""

from __future__ import annotations

from pathlib import Path

from app.database.database import DatabaseManager
from app.database.repositories import (
    BenchmarkRepository,
    ConversationRepository,
    DownloadTasksRepository,
    InstalledModelsRepository,
)
from app.models.download_models import DownloadStatus, DownloadTaskItem
from app.models.model_metadata import InstalledModelRecord
from app.services.conversation_service import ConversationService


def test_database_migrations_and_conversation_crud(tmp_path: Path) -> None:
    db = DatabaseManager(db_path=tmp_path / "studio.db")
    conv_repo = ConversationRepository(db)
    conv_service = ConversationService(conv_repo)

    conv = conv_repo.create_conversation(
        title="MoE Architecture Chat",
        model_id="qwen36-35b",
        system_prompt="You are a local AI engineer.",
    )
    cid = conv["id"]

    conv_repo.add_message(cid, role="user", content="How does 3-tier caching work?")
    conv_repo.add_message(
        cid,
        role="assistant",
        content="Colibri caches hot experts in VRAM and RAM while streaming cold experts from NVMe.",
        reasoning_content="Checking resource_plan.py...",
        model_id="qwen36-35b",
        tokens_per_sec=28.5,
        ttft_ms=140.0,
        token_count=18,
    )

    msgs = conv_repo.get_messages(cid)
    assert len(msgs) == 2
    assert msgs[1]["tokens_per_sec"] == 28.5

    # Search by message content
    found = conv_repo.list_conversations(search_query="NVMe")
    assert len(found) == 1
    assert found[0]["id"] == cid

    # Export Markdown and JSON
    md_out = conv_service.export_conversation_markdown(cid, tmp_path / "chat.md")
    json_out = conv_service.export_conversation_json(cid, tmp_path / "chat.json")
    assert md_out.exists()
    assert "Colibri caches hot experts" in md_out.read_text(encoding="utf-8")
    assert json_out.exists()

    # Delete last assistant message for regenerate flow
    conv_repo.delete_last_assistant_message(cid)
    assert len(conv_repo.get_messages(cid)) == 1


def test_installed_models_downloads_and_benchmarks_repositories(tmp_path: Path) -> None:
    db = DatabaseManager(db_path=tmp_path / "studio2.db")
    mod_repo = InstalledModelsRepository(db)
    dl_repo = DownloadTasksRepository(db)
    bench_repo = BenchmarkRepository(db)

    rec = InstalledModelRecord(
        model_id="qwen3-coder-30b",
        display_name="Qwen3-Coder 30B",
        hf_repo="Justvugg/Qwen3-Coder-30B-A3B-colibri-int4",
        local_path=str(tmp_path / "qwen3"),
        size_bytes=19400000000,
        verified=True,
    )
    mod_repo.upsert_model(rec)
    assert len(mod_repo.list_models()) == 1

    task = DownloadTaskItem(
        task_id="dl_qwen3",
        model_id="qwen3-coder-30b",
        display_name="Qwen3-Coder 30B",
        hf_repo="Justvugg/Qwen3-Coder-30B-A3B-colibri-int4",
        target_dir=str(tmp_path / "qwen3"),
        status=DownloadStatus.PAUSED,
        bytes_downloaded=5000,
        total_bytes=10000,
    )
    dl_repo.upsert_task(task)
    tasks = dl_repo.list_tasks()
    assert len(tasks) == 1
    assert tasks[0].progress_percent == 50.0

    bench = bench_repo.add_benchmark(
        model_id="qwen3-coder-30b",
        backend="vulkan",
        ctx_tokens=4096,
        threads=8,
        policy="balanced",
        prompt_name="Short Q&A",
        ttft_ms=112.5,
        decode_tok_s=31.4,
        prefill_tok_s=280.0,
        peak_ram_gb=14.2,
        peak_vram_gb=6.1,
    )
    assert bench["decode_tok_s"] == 31.4
    assert len(bench_repo.list_benchmarks()) == 1
