"""Colibri Backend Lifecycle & Process Manager (colibri_manager.py).

Implements the strict state machine:
NOT_INSTALLED -> INSTALLING -> READY -> STARTING -> RUNNING -> STOPPING -> STOPPED / FAILED / RECOVERING
Tracks owned server and engine PIDs so switching models or exiting the application
terminates only processes started by Colibri AI Studio, without console window flashes.
"""

from __future__ import annotations

import enum
import logging
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

import psutil
from PyQt6.QtCore import QObject, pyqtSignal

from app.core.backend_adapter import CREATE_NO_WINDOW, ColibriBackendAdapter
from app.core.colibri_api import ColibriApiClient
from app.models.settings_models import AppSettings

logger = logging.getLogger(__name__)


class BackendState(str, enum.Enum):
    NOT_INSTALLED = "NOT_INSTALLED"
    INSTALLING = "INSTALLING"
    READY = "READY"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    FAILED = "FAILED"
    RECOVERING = "RECOVERING"
    CANCELLED = "CANCELLED"


class ColibriProcessManager(QObject):
    """Manages the Colibri HTTP inference server process and lifecycle state machine."""

    state_changed = pyqtSignal(str, str)  # (BackendState.value, detail_message)
    server_log_line = pyqtSignal(str)
    health_updated = pyqtSignal(dict)

    def __init__(self, adapter: ColibriBackendAdapter) -> None:
        super().__init__()
        self.adapter = adapter
        self._lock = threading.RLock()
        self._state: BackendState = BackendState.READY
        self._state_detail: str = "Colibri control plane ready"
        self._active_model_id: str = ""
        self._active_model_path: str = ""
        self._server_proc: subprocess.Popen[str] | None = None
        self._owned_pids: set[int] = set()
        self._host: str = "127.0.0.1"
        self._port: int = 8000
        self._api_key: str | None = None

        self.refresh_installation_state()

    @property
    def state(self) -> BackendState:
        with self._lock:
            return self._state

    @property
    def state_detail(self) -> str:
        with self._lock:
            return self._state_detail

    @property
    def active_model_id(self) -> str:
        with self._lock:
            return self._active_model_id

    @property
    def active_model_path(self) -> str:
        with self._lock:
            return self._active_model_path

    def get_api_client(self) -> ColibriApiClient:
        return ColibriApiClient(host=self._host, port=self._port, api_key=self._api_key)

    def _set_state(self, new_state: BackendState, detail: str = "") -> None:
        with self._lock:
            self._state = new_state
            if detail:
                self._state_detail = detail
        logger.info("Colibri state -> %s (%s)", new_state.value, detail)
        self.state_changed.emit(new_state.value, detail)

    def refresh_installation_state(self) -> dict[str, Any]:
        """Inspect engine directory and update state if not currently running."""
        info = self.adapter.detect_installed_engine_binaries()
        with self._lock:
            if self._state in (BackendState.RUNNING, BackendState.STARTING, BackendState.INSTALLING):
                return info
            if info.get("has_native_binaries"):
                self._set_state(
                    BackendState.READY,
                    f"Colibri {info.get('version', '')} installed ({len(info.get('native_binaries', []))} engines)",
                )
            elif info.get("control_plane_ready"):
                self._set_state(
                    BackendState.NOT_INSTALLED,
                    "Control plane ready — Native C inference engines not yet downloaded",
                )
            else:
                self._set_state(BackendState.NOT_INSTALLED, "Colibri engine not installed")
        return info

    def start_server(
        self,
        model_id: str,
        model_path: Path | str,
        settings: AppSettings,
        api_key: str | None = None,
        startup_timeout_s: float = 45.0,
    ) -> tuple[bool, str]:
        """Start `coli serve` for `model_path` and wait until `/health` responds."""
        mpath = Path(model_path).resolve()
        if not mpath.exists():
            msg = f"Model path does not exist: {mpath}"
            self._set_state(BackendState.FAILED, msg)
            return False, msg

        info = self.adapter.detect_installed_engine_binaries()
        if not info.get("has_native_binaries"):
            msg = (
                "Colibri native Windows inference binaries (e.g. qwen36.exe / colibri.exe) are not installed yet. "
                "Click 'Install Colibri Engine' in Onboarding or Settings → Diagnostics first."
            )
            self._set_state(BackendState.NOT_INSTALLED, msg)
            return False, msg

        # Stop any previously running owned server first
        if self.state in (BackendState.RUNNING, BackendState.STARTING):
            self.stop_server()

        self._host = settings.server_host
        self._port = settings.server_port
        self._api_key = api_key if settings.require_local_api_key else None

        self._set_state(BackendState.STARTING, f"Starting {model_id} on {self._host}:{self._port}...")

        args = [
            "serve",
            "--model",
            str(mpath),
            "--host",
            self._host,
            "--port",
            str(self._port),
            "--model-id",
            model_id,
            "--ctx",
            str(settings.context_length),
            "--policy",
            settings.retention_policy,
        ]
        if settings.auto_tier:
            args.append("--auto-tier")
        if settings.custom_ram_budget_gb and settings.custom_ram_budget_gb > 0:
            args.extend(["--ram", str(settings.custom_ram_budget_gb)])
        if settings.custom_vram_budget_gb is not None and settings.custom_vram_budget_gb >= 0:
            args.extend(["--vram", str(settings.custom_vram_budget_gb)])
        if settings.gpu_offload_mode in ("off", "full", "hybrid"):
            args.extend(["--gpu", settings.gpu_offload_mode])
        if self._api_key:
            args.extend(["--api-key", self._api_key])

        cmd = self.adapter.build_coli_command(args)
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        if settings.cpu_threads > 0:
            env["OMP_NUM_THREADS"] = str(settings.cpu_threads)

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(self.adapter.engine_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                creationflags=CREATE_NO_WINDOW,
            )
        except Exception as exc:
            msg = f"Failed to launch Colibri server: {exc}"
            self._set_state(BackendState.FAILED, msg)
            return False, msg

        with self._lock:
            self._server_proc = proc
            self._owned_pids.add(proc.pid)
            self._active_model_id = model_id
            self._active_model_path = str(mpath)

        # Stream stdout/stderr in background daemon thread
        threading.Thread(
            target=self._read_process_output,
            args=(proc,),
            name="ColibriServerLogReader",
            daemon=True,
        ).start()

        # Poll /health until ready or process exits
        client = self.get_api_client()
        deadline = time.perf_counter() + startup_timeout_s
        while time.perf_counter() < deadline:
            if proc.poll() is not None:
                msg = f"Colibri server exited prematurely (exit code {proc.returncode})."
                self._set_state(BackendState.FAILED, msg)
                return False, msg

            ok, health_data = client.check_health(timeout=1.5)
            if ok:
                self._record_child_pids(proc.pid)
                self._set_state(
                    BackendState.RUNNING,
                    f"Running {model_id} on {self._host}:{self._port}",
                )
                self.health_updated.emit(health_data)
                return True, f"Model '{model_id}' is ready."
            time.sleep(0.6)

        # Startup timed out
        self.stop_server()
        msg = f"Timed out waiting for Colibri server to become healthy after {startup_timeout_s:.0f}s."
        self._set_state(BackendState.FAILED, msg)
        return False, msg

    def _record_child_pids(self, parent_pid: int) -> None:
        try:
            parent = psutil.Process(parent_pid)
            for child in parent.children(recursive=True):
                with self._lock:
                    self._owned_pids.add(child.pid)
        except psutil.NoSuchProcess:
            pass

    def _read_process_output(self, proc: subprocess.Popen[str]) -> None:
        try:
            if proc.stdout:
                for line in proc.stdout:
                    clean = line.rstrip("\r\n")
                    if clean:
                        self.server_log_line.emit(clean)
        except Exception:
            pass
        finally:
            # If process exited unexpectedly while in RUNNING state, transition to FAILED
            with self._lock:
                if self._server_proc is proc and self._state == BackendState.RUNNING:
                    rc = proc.poll()
                    self._set_state(
                        BackendState.FAILED,
                        f"Colibri server terminated unexpectedly (code {rc}).",
                    )

    def stop_server(self) -> None:
        """Gracefully stop only owned Colibri server and child engine processes."""
        with self._lock:
            proc = self._server_proc
            pids_to_stop = set(self._owned_pids)
            if proc is None and not pids_to_stop:
                self._set_state(BackendState.STOPPED, "Server stopped")
                return

        self._set_state(BackendState.STOPPING, "Stopping Colibri inference server...")

        if proc is not None and proc.poll() is None:
            self._record_child_pids(proc.pid)
            pids_to_stop.update(self._owned_pids)
            try:
                proc.terminate()
                proc.wait(timeout=4.0)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

        for pid in pids_to_stop:
            try:
                p = psutil.Process(pid)
                p_name = p.name().lower()
                # Verify process identity before terminating
                if any(
                    k in p_name
                    for k in (
                        "python",
                        "colibri",
                        "qwen",
                        "deepseek",
                        "glm",
                        "mimo",
                        "inkling",
                        "kimi",
                        "olmoe",
                    )
                ):
                    p.terminate()
                    try:
                        p.wait(timeout=2.0)
                    except psutil.TimeoutExpired:
                        p.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        with self._lock:
            self._server_proc = None
            self._owned_pids.clear()
            self._active_model_id = ""
            self._active_model_path = ""
        self._set_state(BackendState.STOPPED, "Server stopped")
