"""Liquid Glass Download Progress Card Widget (Emoji-Free)."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.models.download_models import DownloadStatus, DownloadTaskItem
from app.ui.liquid_glass import MONO_FONT_FAMILY, LiquidGlassPanel
from app.ui.widgets.status_badge import StatusBadge


class DownloadProgressCard(LiquidGlassPanel):
    """Displays real-time download progress, MB/s, ETA, and Pause/Resume/Cancel actions."""

    pause_clicked = pyqtSignal(str)
    resume_clicked = pyqtSignal(str)
    cancel_clicked = pyqtSignal(str)
    remove_clicked = pyqtSignal(str)

    def __init__(self, task: DownloadTaskItem, parent: QWidget | None = None) -> None:
        super().__init__(parent=parent, radius=14.0)
        self.task = task
        self._build_ui()
        self.update_task(task)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        top_row = QHBoxLayout()
        self.title_label = QLabel()
        self.title_label.setStyleSheet("font-size: 14px; font-weight: 700;")
        top_row.addWidget(self.title_label, 1)

        self.status_badge = StatusBadge("QUEUED", variant="info")
        top_row.addWidget(self.status_badge)
        layout.addLayout(top_row)

        self.file_label = QLabel()
        self.file_label.setStyleSheet(f"font-family: {MONO_FONT_FAMILY}; font-size: 11px; color: #94A3B8;")
        layout.addWidget(self.file_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)

        bottom_row = QHBoxLayout()
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet(f"font-family: {MONO_FONT_FAMILY}; font-size: 12px;")
        bottom_row.addWidget(self.stats_label, 1)

        self.pause_btn = QPushButton("Pause")
        self.pause_btn.clicked.connect(lambda: self.pause_clicked.emit(self.task.task_id))
        bottom_row.addWidget(self.pause_btn)

        self.resume_btn = QPushButton("Resume")
        self.resume_btn.setObjectName("primaryGlassButton")
        self.resume_btn.clicked.connect(lambda: self.resume_clicked.emit(self.task.task_id))
        bottom_row.addWidget(self.resume_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("dangerGlassButton")
        self.cancel_btn.clicked.connect(lambda: self.cancel_clicked.emit(self.task.task_id))
        bottom_row.addWidget(self.cancel_btn)

        self.remove_btn = QPushButton("Dismiss")
        self.remove_btn.clicked.connect(lambda: self.remove_clicked.emit(self.task.task_id))
        bottom_row.addWidget(self.remove_btn)

        layout.addLayout(bottom_row)

    def update_task(self, task: DownloadTaskItem) -> None:
        self.task = task
        self.title_label.setText(f"{task.display_name}  [{task.hf_repo}]")

        pct = int(round(task.progress_percent))
        self.progress_bar.setValue(pct)

        dl_gb = task.bytes_downloaded / (1024**3)
        tot_gb = max(0.01, task.total_bytes / (1024**3))
        eta_str = (
            f"{task.eta_seconds // 60}m {task.eta_seconds % 60}s"
            if task.eta_seconds is not None
            else "--"
        )
        self.stats_label.setText(
            f"{dl_gb:.2f} / {tot_gb:.2f} GB ({pct}%)  |  {task.speed_mb_s:.1f} MB/s  |  ETA: {eta_str}"
        )

        if task.error_message:
            self.file_label.setText(f"Error: {task.error_message}")
            self.file_label.setStyleSheet(f"font-family: {MONO_FONT_FAMILY}; font-size: 11px; color: #F87171;")
        else:
            cur = task.current_file or "Waiting in queue..."
            self.file_label.setText(f"Shard ({task.files_completed}/{task.files_total}): {cur}")
            self.file_label.setStyleSheet(f"font-family: {MONO_FONT_FAMILY}; font-size: 11px; color: #94A3B8;")

        st = task.status
        if st == DownloadStatus.COMPLETED:
            self.status_badge.set_variant("green", "COMPLETED")
        elif st in (DownloadStatus.DOWNLOADING, DownloadStatus.IMPORTING_GGUF):
            self.status_badge.set_variant("info", st.value.upper())
        elif st == DownloadStatus.PAUSED:
            self.status_badge.set_variant("yellow", "PAUSED")
        elif st in (DownloadStatus.FAILED, DownloadStatus.CANCELLED):
            self.status_badge.set_variant("red", st.value.upper())
        else:
            self.status_badge.set_variant("info", st.value.upper())

        self.pause_btn.setVisible(st in (DownloadStatus.DOWNLOADING, DownloadStatus.QUEUED))
        self.resume_btn.setVisible(st in (DownloadStatus.PAUSED, DownloadStatus.FAILED, DownloadStatus.CANCELLED))
        self.cancel_btn.setVisible(st in (DownloadStatus.DOWNLOADING, DownloadStatus.QUEUED, DownloadStatus.PAUSED))
        self.remove_btn.setVisible(st in (DownloadStatus.COMPLETED, DownloadStatus.FAILED, DownloadStatus.CANCELLED))
