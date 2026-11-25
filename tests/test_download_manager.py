"""Tests for Download Manager & Storage Manager (`app/core/download_manager.py`)."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from app.core.download_manager import DownloadManager
from app.core.storage_manager import StorageManager
from app.database.database import DatabaseManager
from app.database.repositories import DownloadTasksRepository, InstalledModelsRepository
from app.models.model_metadata import InstalledModelRecord


def test_storage_manager_bounded_benchmark_and_space_check(tmp_path: Path) -> None:
    ok, free_gb, msg = StorageManager.check_sufficient_space(tmp_path, required_gb=0.01, safety_margin_gb=0.01)
    assert ok is True
    assert free_gb > 0
    assert "available" in msg

    bench = StorageManager.run_bounded_read_benchmark(tmp_path, size_mb=16)
    assert bench["seq_read_mb_s"] > 0
    assert bench["rand_read_mb_s"] > 0
    # Ensure temporary file was cleaned up
    assert list(tmp_path.glob(".colibri_io_bench_*")) == []


def test_verify_model_integrity_and_sha256(tmp_path: Path) -> None:
    model_dir = tmp_path / "test_model"
    model_dir.mkdir()

    # Empty dir fails integrity check
    ok_empty, issues_empty = DownloadManager.verify_model_integrity(model_dir)
    assert ok_empty is False
    assert len(issues_empty) > 0

    # Create valid config.json, weight shard, and manifest
    cfg = model_dir / "config.json"
    cfg.write_text('{"model_type": "qwen3_moe"}', encoding="utf-8")
    shard = model_dir / "model.safetensors"
    payload = b"colibri_weight_tensor_data" * 100
    shard.write_bytes(payload)

    manifest = {
        "model_id": "test_model",
        "files": [
            {"path": "config.json", "size": cfg.stat().st_size},
            {"path": "model.safetensors", "size": shard.stat().st_size},
        ],
    }
    (model_dir / ".colibri-download.json").write_text(json.dumps(manifest), encoding="utf-8")

    ok_valid, issues_valid = DownloadManager.verify_model_integrity(model_dir)
    assert ok_valid is True
    assert issues_valid == []

    # Verify SHA256 helper
    digest = DownloadManager.compute_file_sha256(shard)
    assert len(digest) == 64

    # Incomplete .part file triggers integrity failure
    (model_dir / "extra.safetensors.part").write_bytes(b"partial")
    ok_part, issues_part = DownloadManager.verify_model_integrity(model_dir)
    assert ok_part is False
    assert any(".part" in i for i in issues_part)


def test_delete_installed_model_blocks_active_model(tmp_path: Path) -> None:
    db = DatabaseManager(db_path=tmp_path / "test.db")
    dl_repo = DownloadTasksRepository(db)
    mod_repo = InstalledModelsRepository(db)
    dm = DownloadManager(tasks_repo=dl_repo, models_repo=mod_repo)

    model_folder = tmp_path / "qwen3-coder-30b"
    model_folder.mkdir()
    (model_folder / "config.json").write_text("{}", encoding="utf-8")

    rec = InstalledModelRecord(
        model_id="qwen3-coder-30b",
        display_name="Qwen3 Coder",
        local_path=str(model_folder),
        size_bytes=100,
    )
    mod_repo.upsert_model(rec)

    # Deleting while active_model_id matches must raise RuntimeError
    with pytest.raises(RuntimeError, match="Cannot delete"):
        dm.delete_installed_model("qwen3-coder-30b", active_model_id="qwen3-coder-30b")

    # Deleting when inactive succeeds and removes directory
    dm.delete_installed_model("qwen3-coder-30b", active_model_id="", delete_files_on_disk=True)
    assert not model_folder.exists()
    assert mod_repo.get_model("qwen3-coder-30b") is None
