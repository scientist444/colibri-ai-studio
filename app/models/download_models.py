"""Download queue and task progress models."""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel


class DownloadStatus(str, Enum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    PAUSED = "paused"
    VERIFYING = "verifying"
    IMPORTING_GGUF = "importing_gguf"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DownloadTaskItem(BaseModel):
    """State of a model download task managed by DownloadManager."""

    task_id: str
    model_id: str
    display_name: str
    hf_repo: str
    target_dir: str
    status: DownloadStatus = DownloadStatus.QUEUED
    bytes_downloaded: int = 0
    total_bytes: int = 0
    speed_mb_s: float = 0.0
    eta_seconds: int | None = None
    current_file: str = ""
    files_completed: int = 0
    files_total: int = 0
    error_message: str = ""
    requires_gguf_import: bool = False

    @property
    def progress_percent(self) -> float:
        if self.total_bytes <= 0:
            return 0.0
        return min(100.0, (self.bytes_downloaded / self.total_bytes) * 100.0)
