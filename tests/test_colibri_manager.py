"""Tests for Colibri Backend Adapter & Process Manager (`backend_adapter.py`, `colibri_manager.py`)."""

from __future__ import annotations

from pathlib import Path

from app.core.backend_adapter import ColibriBackendAdapter
from app.core.colibri_manager import BackendState, ColibriProcessManager
from app.models.settings_models import AppSettings


def test_backend_adapter_provisioning_and_version(tmp_path: Path) -> None:
    engine_dir = tmp_path / "engine"
    adapter = ColibriBackendAdapter(engine_dir=engine_dir)

    assert (engine_dir / "coli").exists()
    assert (engine_dir / "version.py").exists()
    assert (engine_dir / "setup_catalog.py").exists()

    ver = adapter.get_version()
    assert ver != "unknown"
    assert len(ver) >= 3

    info = adapter.detect_installed_engine_binaries()
    assert info["control_plane_ready"] is True
    assert info["has_native_binaries"] is False


def test_coli_setup_list_json_invocation(tmp_path: Path) -> None:
    adapter = ColibriBackendAdapter(engine_dir=tmp_path / "engine")
    res = adapter.run_coli_json(["setup", "--list", "--all", "--json"], timeout=20.0)
    # `coli setup --list --json` returns hardware + catalog models JSON
    assert isinstance(res, dict)
    assert "models" in res or "items" in res or "hardware" in res


def test_process_manager_state_machine_and_missing_binary_guard(tmp_path: Path) -> None:
    adapter = ColibriBackendAdapter(engine_dir=tmp_path / "engine")
    pm = ColibriProcessManager(adapter)

    assert pm.state == BackendState.NOT_INSTALLED

    # Attempting to start server when model path does not exist transitions to FAILED
    settings = AppSettings(engine_dir=str(tmp_path / "engine"), models_dir=str(tmp_path / "models"))
    ok, msg = pm.start_server("missing", tmp_path / "nonexistent_model", settings)
    assert ok is False
    assert pm.state == BackendState.FAILED
    assert "does not exist" in msg

    # Attempting to start server when model dir exists but C binaries are not yet downloaded
    fake_model_dir = tmp_path / "models" / "qwen3-coder-30b"
    fake_model_dir.mkdir(parents=True)
    ok2, msg2 = pm.start_server("qwen3-coder-30b", fake_model_dir, settings)
    assert ok2 is False
    assert pm.state == BackendState.NOT_INSTALLED
    assert "Install Colibri Engine" in msg2

    # Stopping server when nothing is running transitions cleanly to STOPPED
    pm.stop_server()
    assert pm.state == BackendState.STOPPED
