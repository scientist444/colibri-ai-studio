"""Model Download Manager (download_manager.py).

Features:
- Real-time bytes downloaded, total bytes, MB/s speed, and ETA
- Pause/interrupt and resume via `.part` files + HTTP `Range` headers
- `.colibri-download.json` manifest compatible with Colibri's `setup_download.py`
- Exponential backoff retry on transient network failures
- Disk-space verification before starting
- Optional SHA256 / size integrity verification
- Hugging Face token support for gated repositories
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import threading
import time
import urllib.parse
from pathlib import Path
from typing import Any, Callable

import httpx
from PyQt6.QtCore import QObject, pyqtSignal

from app.constants import HUGGINGFACE_API_BASE
from app.core.storage_manager import StorageManager
from app.database.repositories import DownloadTasksRepository, InstalledModelsRepository
from app.models.download_models import DownloadStatus, DownloadTaskItem
from app.models.model_metadata import InstalledModelRecord, ModelCandidate

logger = logging.getLogger(__name__)

_SKIP_EXTENSIONS = {".md", ".txt", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".gitattributes"}


class DownloadManager(QObject):
    """Manages queued, active, paused, and completed model downloads."""

    task_updated = pyqtSignal(object)     # DownloadTaskItem
    task_completed = pyqtSignal(object)   # InstalledModelRecord
    task_failed = pyqtSignal(str, str)    # (task_id, error_message)
    queue_changed = pyqtSignal()

    def __init__(
        self,
        tasks_repo: DownloadTasksRepository,
        models_repo: InstalledModelsRepository,
        hf_token_provider: Callable[[], str | None] | None = None,
        gguf_importer: Callable[[Path, Path], tuple[bool, str]] | None = None,
    ) -> None:
        super().__init__()
        self.tasks_repo = tasks_repo
        self.models_repo = models_repo
        self.hf_token_provider = hf_token_provider
        self.gguf_importer = gguf_importer

        self._lock = threading.RLock()
        self._tasks: dict[str, DownloadTaskItem] = {}
        self._cancel_flags: dict[str, str] = {}  # task_id -> "pause" | "cancel"
        self._worker_thread: threading.Thread | None = None

        self._load_persisted_tasks()

    def _load_persisted_tasks(self) -> None:
        for t in self.tasks_repo.list_tasks():
            if t.status in (DownloadStatus.DOWNLOADING, DownloadStatus.QUEUED, DownloadStatus.VERIFYING):
                t.status = DownloadStatus.PAUSED
                self.tasks_repo.upsert_task(t)
            self._tasks[t.task_id] = t

    def list_tasks(self) -> list[DownloadTaskItem]:
        with self._lock:
            return [t.model_copy() for t in self._tasks.values()]

    def enqueue_download(
        self,
        candidate: ModelCandidate,
        models_root_dir: Path | str,
    ) -> DownloadTaskItem:
        """Verify disk space and enqueue a model download task."""
        root_dir = Path(models_root_dir).resolve()
        root_dir.mkdir(parents=True, exist_ok=True)

        req_gb = max(candidate.disk_required_gb, candidate.download_size_gb)
        ok, free_gb, msg = StorageManager.check_sufficient_space(root_dir, required_gb=req_gb, safety_margin_gb=1.0)
        if not ok and req_gb > 0.1:
            raise RuntimeError(msg)

        safe_folder = candidate.model_id.replace("/", "--")
        target_dir = root_dir / safe_folder

        with self._lock:
            task_id = f"dl_{safe_folder}"
            existing = self._tasks.get(task_id)
            bytes_done = existing.bytes_downloaded if existing else 0
            total_b = int(candidate.download_size_gb * (1024**3))

            task = DownloadTaskItem(
                task_id=task_id,
                model_id=candidate.model_id,
                display_name=candidate.display_name,
                hf_repo=candidate.hf_repo,
                target_dir=str(target_dir),
                status=DownloadStatus.QUEUED,
                bytes_downloaded=bytes_done,
                total_bytes=total_b,
                requires_gguf_import=candidate.compatibility.requires_gguf_import,
            )
            self._tasks[task_id] = task
            self._cancel_flags.pop(task_id, None)
            self.tasks_repo.upsert_task(task)

        self.task_updated.emit(task.model_copy())
        self.queue_changed.emit()
        self._ensure_worker_running()
        return task

    def pause_download(self, task_id: str) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return
            if task.status == DownloadStatus.QUEUED:
                task.status = DownloadStatus.PAUSED
                self.tasks_repo.upsert_task(task)
                self.task_updated.emit(task.model_copy())
                self.queue_changed.emit()
            elif task.status == DownloadStatus.DOWNLOADING:
                self._cancel_flags[task_id] = "pause"

    def resume_download(self, task_id: str) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return
            if task.status in (DownloadStatus.PAUSED, DownloadStatus.FAILED, DownloadStatus.CANCELLED):
                task.status = DownloadStatus.QUEUED
                task.error_message = ""
                self._cancel_flags.pop(task_id, None)
                self.tasks_repo.upsert_task(task)
                self.task_updated.emit(task.model_copy())
                self.queue_changed.emit()
                self._ensure_worker_running()

    def cancel_download(self, task_id: str, remove_partial_files: bool = False) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return
            if task.status == DownloadStatus.DOWNLOADING:
                self._cancel_flags[task_id] = "cancel"
            else:
                task.status = DownloadStatus.CANCELLED
                self.tasks_repo.upsert_task(task)
                if remove_partial_files:
                    self._clean_partial_dir(Path(task.target_dir))
                self.task_updated.emit(task.model_copy())
                self.queue_changed.emit()

    def remove_task_record(self, task_id: str) -> None:
        with self._lock:
            self._tasks.pop(task_id, None)
            self._cancel_flags.pop(task_id, None)
            self.tasks_repo.delete_task(task_id)
        self.queue_changed.emit()

    @staticmethod
    def _clean_partial_dir(target_dir: Path) -> None:
        if target_dir.exists():
            for p in target_dir.rglob("*.part"):
                try:
                    p.unlink()
                except OSError:
                    pass

    def _ensure_worker_running(self) -> None:
        with self._lock:
            if self._worker_thread is not None and self._worker_thread.is_alive():
                return
            self._worker_thread = threading.Thread(
                target=self._process_queue_loop,
                name="ColibriDownloadWorker",
                daemon=True,
            )
            self._worker_thread.start()

    def _next_queued_task(self) -> DownloadTaskItem | None:
        with self._lock:
            for t in self._tasks.values():
                if t.status == DownloadStatus.QUEUED:
                    return t
        return None

    def _process_queue_loop(self) -> None:
        while True:
            task = self._next_queued_task()
            if task is None:
                break
            try:
                self._execute_download_task(task)
            except Exception as exc:
                logger.exception("Unhandled error in download task %s: %s", task.task_id, exc)
                with self._lock:
                    task.status = DownloadStatus.FAILED
                    task.error_message = str(exc)
                    self.tasks_repo.upsert_task(task)
                self.task_updated.emit(task.model_copy())
                self.task_failed.emit(task.task_id, str(exc))

    def _get_headers(self) -> dict[str, str]:
        headers = {"User-Agent": "ColibriAIStudio/1.0"}
        if self.hf_token_provider:
            token = self.hf_token_provider()
            if token:
                headers["Authorization"] = f"Bearer {token.strip()}"
        return headers

    def _fetch_repo_files(self, hf_repo: str, headers: dict[str, str]) -> list[dict[str, Any]]:
        """Query Hugging Face repository tree API for file paths, sizes, and SHA256 OIDs."""
        api_url = f"{HUGGINGFACE_API_BASE}/api/models/{hf_repo}/tree/main?recursive=true"
        with httpx.Client(timeout=30.0, headers=headers, follow_redirects=True) as client:
            resp = client.get(api_url)
            resp.raise_for_status()
            entries = resp.json()

        files: list[dict[str, Any]] = []
        for entry in entries:
            if not isinstance(entry, dict) or entry.get("type") != "file":
                continue
            rpath = str(entry.get("path") or "")
            if not rpath or rpath.startswith("."):
                continue
            ext = Path(rpath).suffix.lower()
            if ext in _SKIP_EXTENSIONS:
                continue
            lfs = entry.get("lfs")
            size = int(lfs["size"]) if isinstance(lfs, dict) and "size" in lfs else int(entry.get("size") or 0)
            sha256_oid = str(lfs["oid"]) if isinstance(lfs, dict) and "oid" in lfs else ""
            files.append({"path": rpath, "size": size, "sha256": sha256_oid})

        files.sort(key=lambda f: int(f["size"]))
        return files

    def _execute_download_task(self, task: DownloadTaskItem) -> None:
        target_dir = Path(task.target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        headers = self._get_headers()

        with self._lock:
            task.status = DownloadStatus.DOWNLOADING
            task.error_message = ""
            self.tasks_repo.upsert_task(task)
        self.task_updated.emit(task.model_copy())

        files = self._fetch_repo_files(task.hf_repo, headers)
        if not files:
            raise RuntimeError(f"No downloadable model files found in repository '{task.hf_repo}'.")

        total_bytes = sum(int(f["size"]) for f in files)
        completed_bytes = 0
        for f in files:
            dest_file = target_dir / str(f["path"])
            part_file = dest_file.with_name(dest_file.name + ".part")
            if dest_file.exists() and dest_file.stat().st_size == int(f["size"]):
                completed_bytes += int(f["size"])
            elif part_file.exists():
                completed_bytes += min(part_file.stat().st_size, int(f["size"]))

        with self._lock:
            task.total_bytes = total_bytes
            task.bytes_downloaded = completed_bytes
            task.files_total = len(files)
            self.tasks_repo.upsert_task(task)
        self.task_updated.emit(task.model_copy())

        start_time = time.perf_counter()
        bytes_at_start = completed_bytes
        last_emit_time = 0.0

        for idx, file_info in enumerate(files):
            rel_path = str(file_info["path"])
            expected_size = int(file_info["size"])
            dest_file = target_dir / rel_path
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            part_file = dest_file.with_name(dest_file.name + ".part")

            if dest_file.exists() and dest_file.stat().st_size == expected_size:
                with self._lock:
                    task.files_completed = idx + 1
                continue

            with self._lock:
                task.current_file = rel_path

            quoted_path = "/".join(urllib.parse.quote(seg, safe="") for seg in rel_path.split("/"))
            file_url = f"{HUGGINGFACE_API_BASE}/{task.hf_repo}/resolve/main/{quoted_path}"

            max_retries = 4
            for attempt in range(max_retries):
                cancel_action = self._cancel_flags.get(task.task_id)
                if cancel_action:
                    self._finalize_interrupted_task(task, cancel_action)
                    return

                existing_part_size = part_file.stat().st_size if part_file.exists() else 0
                req_headers = dict(headers)
                if existing_part_size > 0:
                    req_headers["Range"] = f"bytes={existing_part_size}-"

                try:
                    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
                        with client.stream("GET", file_url, headers=req_headers) as resp:
                            if resp.status_code == 416:
                                # Range already satisfied
                                break
                            resp.raise_for_status()
                            mode = "ab" if (existing_part_size > 0 and resp.status_code == 206) else "wb"
                            if mode == "wb" and existing_part_size > 0:
                                completed_bytes = max(0, completed_bytes - existing_part_size)

                            with open(part_file, mode) as out_f:
                                for chunk in resp.iter_bytes(chunk_size=1024 * 1024):
                                    cancel_action = self._cancel_flags.get(task.task_id)
                                    if cancel_action:
                                        out_f.flush()
                                        self._finalize_interrupted_task(task, cancel_action)
                                        return
                                    if not chunk:
                                        continue
                                    out_f.write(chunk)
                                    completed_bytes += len(chunk)

                                    now = time.perf_counter()
                                    if now - last_emit_time >= 0.25:
                                        elapsed = max(0.001, now - start_time)
                                        delta_b = max(0, completed_bytes - bytes_at_start)
                                        speed_mbs = round((delta_b / (1024 * 1024)) / elapsed, 2)
                                        rem_b = max(0, total_bytes - completed_bytes)
                                        eta_s = (
                                            int(rem_b / (speed_mbs * 1024 * 1024))
                                            if speed_mbs > 0.05
                                            else None
                                        )
                                        with self._lock:
                                            task.bytes_downloaded = completed_bytes
                                            task.speed_mb_s = speed_mbs
                                            task.eta_seconds = eta_s
                                        self.task_updated.emit(task.model_copy())
                                        last_emit_time = now
                    break
                except httpx.HTTPError as exc:
                    if attempt + 1 >= max_retries:
                        raise RuntimeError(f"Failed downloading {rel_path}: {exc}") from exc
                    backoff = 1.5 * (2**attempt)
                    logger.warning("Transient error on %s (attempt %d/%d), retrying in %.1fs", rel_path, attempt + 1, max_retries, backoff)
                    time.sleep(backoff)

            # Verify size of downloaded part file before atomic rename
            if part_file.exists():
                actual_size = part_file.stat().st_size
                if expected_size > 0 and actual_size != expected_size:
                    raise RuntimeError(
                        f"Integrity mismatch for {rel_path}: expected {expected_size} bytes, got {actual_size} bytes."
                    )
                part_file.replace(dest_file)

            with self._lock:
                task.files_completed = idx + 1
                task.bytes_downloaded = completed_bytes
                self.tasks_repo.upsert_task(task)
            self.task_updated.emit(task.model_copy())

        # Write Colibri-compatible download manifest (.colibri-download.json)
        manifest_path = target_dir / ".colibri-download.json"
        manifest_data = {
            "model_id": task.model_id,
            "hf_repo": task.hf_repo,
            "total_bytes": total_bytes,
            "completed": True,
            "files": [{"path": f["path"], "size": f["size"]} for f in files],
        }
        manifest_path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

        # Run automatic GGUF import if required
        final_model_path = target_dir
        if task.requires_gguf_import and self.gguf_importer is not None:
            gguf_files = sorted(target_dir.glob("*.gguf"))
            if gguf_files:
                with self._lock:
                    task.status = DownloadStatus.IMPORTING_GGUF
                    task.current_file = f"Importing {gguf_files[0].name} via coli import..."
                self.task_updated.emit(task.model_copy())
                imported_dir = target_dir / "colibri_imported"
                ok, msg = self.gguf_importer(gguf_files[0], imported_dir)
                if ok and imported_dir.exists():
                    final_model_path = imported_dir

        with self._lock:
            task.status = DownloadStatus.COMPLETED
            task.bytes_downloaded = total_bytes
            task.speed_mb_s = 0.0
            task.eta_seconds = 0
            task.current_file = "Completed"
            self.tasks_repo.upsert_task(task)

        record = InstalledModelRecord(
            model_id=task.model_id,
            display_name=task.display_name,
            hf_repo=task.hf_repo,
            local_path=str(final_model_path),
            family="qwen36",
            quantization="INT4 / FP8",
            size_bytes=total_bytes,
            verified=True,
            source_type="huggingface" if "--" in task.model_id else "catalog",
        )
        self.models_repo.upsert_model(record)
        self.task_updated.emit(task.model_copy())
        self.task_completed.emit(record)
        self.queue_changed.emit()

    def _finalize_interrupted_task(self, task: DownloadTaskItem, action: str) -> None:
        with self._lock:
            self._cancel_flags.pop(task.task_id, None)
            if action == "pause":
                task.status = DownloadStatus.PAUSED
                task.speed_mb_s = 0.0
                task.eta_seconds = None
            else:
                task.status = DownloadStatus.CANCELLED
                task.speed_mb_s = 0.0
                task.eta_seconds = None
            self.tasks_repo.upsert_task(task)
        self.task_updated.emit(task.model_copy())
        self.queue_changed.emit()

    @staticmethod
    def verify_model_integrity(model_dir: Path | str) -> tuple[bool, list[str]]:
        """Verify that a local model directory has valid config/weights and matches its manifest."""
        root = Path(model_dir)
        issues: list[str] = []
        if not root.exists():
            return False, [f"Model directory does not exist: {root}"]

        part_files = list(root.rglob("*.part"))
        if part_files:
            issues.append(f"Found {len(part_files)} incomplete `.part` file(s).")

        has_config = (root / "config.json").exists() or (root / "model_index.json").exists()
        has_weights = bool(list(root.glob("*.safetensors")) or list(root.glob("*.gguf")) or list(root.glob("*.bin")))
        if not has_config and not has_weights:
            issues.append("Missing both `config.json` and model weight files (`.safetensors` / `.gguf`).")

        manifest_file = root / ".colibri-download.json"
        if manifest_file.exists():
            try:
                manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
                for f_entry in manifest.get("files", []):
                    fpath = root / str(f_entry["path"])
                    expected = int(f_entry.get("size") or 0)
                    if not fpath.exists():
                        issues.append(f"Missing expected file: {f_entry['path']}")
                    elif expected > 0 and fpath.stat().st_size != expected:
                        issues.append(
                            f"Size mismatch for {f_entry['path']}: expected {expected}, found {fpath.stat().st_size}"
                        )
            except Exception as exc:
                issues.append(f"Corrupted `.colibri-download.json` manifest: {exc}")

        return len(issues) == 0, issues

    @staticmethod
    def compute_file_sha256(file_path: Path, max_bytes: int | None = None) -> str:
        """Compute SHA256 digest of a file."""
        h = hashlib.sha256()
        read_so_far = 0
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                if max_bytes is not None and read_so_far + len(chunk) > max_bytes:
                    h.update(chunk[: max_bytes - read_so_far])
                    break
                h.update(chunk)
                read_so_far += len(chunk)
        return h.hexdigest()

    def delete_installed_model(
        self,
        model_id: str,
        active_model_id: str = "",
        delete_files_on_disk: bool = True,
    ) -> None:
        """Delete an installed model, refusing if it is currently loaded by the running server."""
        if active_model_id and model_id == active_model_id:
            raise RuntimeError(
                f"Cannot delete '{model_id}' while it is the active running model. Stop the server or switch models first."
            )
        rec = self.models_repo.get_model(model_id)
        if rec and delete_files_on_disk:
            p = Path(rec.local_path)
            if p.exists() and p.is_dir():
                shutil.rmtree(p, ignore_errors=False)
        self.models_repo.remove_model(model_id)
