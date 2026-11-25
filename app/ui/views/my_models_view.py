"""Liquid Glass My Models & Download Queue View (`my_models_view.py`) — Emoji-Free."""

from __future__ import annotations

import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.application_state import ApplicationState
from app.controllers.backend_controller import BackendController
from app.controllers.model_controller import ModelController
from app.core.download_manager import DownloadManager
from app.models.download_models import DownloadTaskItem
from app.models.model_metadata import InstalledModelRecord
from app.ui.liquid_glass import MONO_FONT_FAMILY, LiquidGlassPanel
from app.ui.widgets.progress_card import DownloadProgressCard
from app.ui.widgets.status_badge import StatusBadge


class InstalledModelCard(LiquidGlassPanel):
    """Liquid Glass card representing a locally installed Colibri model."""

    def __init__(
        self,
        record: InstalledModelRecord,
        is_active: bool,
        on_launch: object,
        on_verify: object,
        on_open_folder: object,
        on_delete: object,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent=parent, radius=15.0, elevated=is_active)
        self.record = record
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        top_row = QHBoxLayout()
        title = QLabel(record.display_name)
        title.setStyleSheet("font-size: 15px; font-weight: 700;")
        top_row.addWidget(title)

        fam_badge = StatusBadge(record.family.upper(), variant="info")
        top_row.addWidget(fam_badge)

        if is_active:
            active_badge = StatusBadge("ACTIVE IN SERVER", variant="green")
            top_row.addWidget(active_badge)
        elif record.verified:
            ver_badge = StatusBadge("VERIFIED", variant="green")
            top_row.addWidget(ver_badge)

        top_row.addStretch(1)
        size_gb = record.size_bytes / (1024**3)
        size_lbl = QLabel(f"{size_gb:.2f} GB on disk")
        size_lbl.setStyleSheet(f"font-family: {MONO_FONT_FAMILY}; font-size: 13px; font-weight: 700; color: #38BDF8;")
        top_row.addWidget(size_lbl)
        layout.addLayout(top_row)

        path_lbl = QLabel(
            f"Path: {record.local_path}   |   Quantization: {record.quantization}   |   Source: {record.source_type}"
        )
        path_lbl.setWordWrap(True)
        path_lbl.setStyleSheet(f"font-family: {MONO_FONT_FAMILY}; font-size: 11px; color: #94A3B8;")
        layout.addWidget(path_lbl)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        open_btn = QPushButton("Open Folder")
        open_btn.clicked.connect(lambda: on_open_folder(record))  # type: ignore[misc]
        btn_row.addWidget(open_btn)

        verify_btn = QPushButton("Verify & Doctor")
        verify_btn.clicked.connect(lambda: on_verify(record))  # type: ignore[misc]
        btn_row.addWidget(verify_btn)

        del_btn = QPushButton("Delete")
        del_btn.setObjectName("dangerGlassButton")
        del_btn.setEnabled(not is_active)
        if is_active:
            del_btn.setToolTip("Stop the server before deleting the active model.")
        del_btn.clicked.connect(lambda: on_delete(record))  # type: ignore[misc]
        btn_row.addWidget(del_btn)

        launch_btn = QPushButton("Load & Chat")
        launch_btn.setObjectName("primaryGlassButton")
        launch_btn.clicked.connect(lambda: on_launch(record))  # type: ignore[misc]
        btn_row.addWidget(launch_btn)

        layout.addLayout(btn_row)


class MyModelsView(QWidget):
    """Liquid Glass My Models & Active Downloads manager."""

    def __init__(
        self,
        app_state: ApplicationState,
        model_controller: ModelController,
        backend_controller: BackendController,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.app_state = app_state
        self.model_controller = model_controller
        self.backend_controller = backend_controller
        self._dl_cards: dict[str, DownloadProgressCard] = {}

        self._build_ui()
        self._connect_signals()
        self.refresh_installed_list()
        self.refresh_downloads_list()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Header
        header = LiquidGlassPanel(self, radius=16.0, elevated=True)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(18, 12, 18, 12)

        title_col = QVBoxLayout()
        title_lbl = QLabel("My Models & Downloads")
        title_lbl.setObjectName("viewTitle")
        sub_lbl = QLabel(
            "Manage locally installed Colibri models, import local GGUF weights, and control active downloads"
        )
        sub_lbl.setObjectName("viewSubtitle")
        title_col.addWidget(title_lbl)
        title_col.addWidget(sub_lbl)
        h_layout.addLayout(title_col, 1)

        import_gguf_btn = QPushButton("Import Local .GGUF File (`coli import`)")
        import_gguf_btn.setObjectName("primaryGlassButton")
        import_gguf_btn.clicked.connect(self._import_local_gguf)
        h_layout.addWidget(import_gguf_btn)

        scan_btn = QPushButton("Scan Models Folder")
        scan_btn.clicked.connect(self.app_state.refresh_installed_models)
        h_layout.addWidget(scan_btn)

        open_root_btn = QPushButton("Open Storage Root")
        open_root_btn.clicked.connect(self._open_models_root)
        h_layout.addWidget(open_root_btn)

        layout.addWidget(header)

        # Liquid Glass Tabs: Installed Models vs Download Queue
        self.tabs = QTabWidget()

        # Tab 1: Installed Models
        self.installed_tab = QWidget()
        i_layout = QVBoxLayout(self.installed_tab)
        i_layout.setContentsMargins(6, 6, 6, 6)

        self.installed_scroll = QScrollArea()
        self.installed_scroll.setWidgetResizable(True)
        self.installed_container = QWidget()
        self.installed_layout = QVBoxLayout(self.installed_container)
        self.installed_layout.setContentsMargins(6, 6, 6, 6)
        self.installed_layout.setSpacing(10)
        self.installed_layout.addStretch(1)
        self.installed_scroll.setWidget(self.installed_container)
        i_layout.addWidget(self.installed_scroll, 1)
        self.tabs.addTab(self.installed_tab, "Installed Local Models")

        # Tab 2: Active & Resumable Downloads
        self.downloads_tab = QWidget()
        d_layout = QVBoxLayout(self.downloads_tab)
        d_layout.setContentsMargins(6, 6, 6, 6)

        self.downloads_scroll = QScrollArea()
        self.downloads_scroll.setWidgetResizable(True)
        self.downloads_container = QWidget()
        self.downloads_layout = QVBoxLayout(self.downloads_container)
        self.downloads_layout.setContentsMargins(6, 6, 6, 6)
        self.downloads_layout.setSpacing(10)
        self.downloads_layout.addStretch(1)
        self.downloads_scroll.setWidget(self.downloads_container)
        d_layout.addWidget(self.downloads_scroll, 1)
        self.tabs.addTab(self.downloads_tab, "Download Queue & Resume Manager")

        layout.addWidget(self.tabs, 1)

    def _connect_signals(self) -> None:
        self.app_state.installed_models_changed.connect(lambda _: self.refresh_installed_list())
        self.app_state.download_manager.task_updated.connect(self._on_download_task_updated)
        self.app_state.download_manager.queue_changed.connect(self.refresh_downloads_list)
        self.model_controller.gguf_import_finished.connect(self._on_gguf_import_finished)

    def refresh_installed_list(self) -> None:
        while self.installed_layout.count() > 1:
            item = self.installed_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        records = self.app_state.models_repo.list_models()
        active_id = self.app_state.process_manager.active_model_id

        if not records:
            empty = LiquidGlassPanel(self.installed_container, radius=14.0)
            el = QVBoxLayout(empty)
            el.setContentsMargins(18, 16, 18, 16)
            lbl = QLabel(
                "No models are installed yet in your local model storage directory.\n"
                "Open the Model Hub to download an official Colibri model, or click 'Import Local .GGUF File' above."
            )
            lbl.setWordWrap(True)
            lbl.setStyleSheet("color: #94A3B8; font-size: 13px;")
            el.addWidget(lbl)
            self.installed_layout.insertWidget(0, empty)
            return

        for rec in records:
            card = InstalledModelCard(
                record=rec,
                is_active=(rec.model_id == active_id),
                on_launch=self._launch_model,
                on_verify=self._verify_model,
                on_open_folder=self._open_model_folder,
                on_delete=self._delete_model,
                parent=self.installed_container,
            )
            self.installed_layout.insertWidget(self.installed_layout.count() - 1, card)

    def refresh_downloads_list(self) -> None:
        self._dl_cards.clear()
        while self.downloads_layout.count() > 1:
            item = self.downloads_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        tasks = self.app_state.download_manager.list_tasks()
        if not tasks:
            empty = LiquidGlassPanel(self.downloads_container, radius=14.0)
            el = QVBoxLayout(empty)
            el.setContentsMargins(18, 16, 18, 16)
            lbl = QLabel("No active or paused downloads. Select a model in Model Hub to start downloading.")
            lbl.setStyleSheet("color: #94A3B8; font-size: 13px;")
            el.addWidget(lbl)
            self.downloads_layout.insertWidget(0, empty)
            return

        for t in tasks:
            card = DownloadProgressCard(t, parent=self.downloads_container)
            card.pause_clicked.connect(self.app_state.download_manager.pause_download)
            card.resume_clicked.connect(self.app_state.download_manager.resume_download)
            card.cancel_clicked.connect(
                lambda tid: self.app_state.download_manager.cancel_download(tid, remove_partial_files=False)
            )
            card.remove_clicked.connect(self.app_state.download_manager.remove_task_record)
            self._dl_cards[t.task_id] = card
            self.downloads_layout.insertWidget(self.downloads_layout.count() - 1, card)

    def _on_download_task_updated(self, task: DownloadTaskItem) -> None:
        if task.task_id in self._dl_cards:
            self._dl_cards[task.task_id].update_task(task)
        else:
            self.refresh_downloads_list()

    def _launch_model(self, record: InstalledModelRecord) -> None:
        self.backend_controller.start_model_async(record.model_id, record.local_path)
        self.app_state.navigation_requested.emit("chat")

    def _verify_model(self, record: InstalledModelRecord) -> None:
        ok, issues = DownloadManager.verify_model_integrity(record.local_path)
        doctor_res = self.app_state.adapter.run_doctor(model_dir=record.local_path)
        if ok:
            record.verified = True
            self.app_state.models_repo.upsert_model(record)
            self.refresh_installed_list()
            QMessageBox.information(
                self,
                "Model Integrity & Doctor Verified",
                f"[OK] Model '{record.display_name}' passed file integrity verification.\n\n"
                f"Colibri Doctor Summary:\n{doctor_res}",
            )
        else:
            QMessageBox.warning(
                self,
                "Model Integrity Issues Detected",
                "Issues found:\n- " + "\n- ".join(issues),
            )

    def _open_model_folder(self, record: InstalledModelRecord) -> None:
        p = Path(record.local_path)
        p.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(str(p))  # type: ignore[attr-defined]

    def _open_models_root(self) -> None:
        p = Path(self.app_state.settings.models_dir)
        p.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(str(p))  # type: ignore[attr-defined]

    def _delete_model(self, record: InstalledModelRecord) -> None:
        reply = QMessageBox.question(
            self,
            "Confirm Model Deletion",
            f"Permanently delete '{record.display_name}' and its files from:\n{record.local_path}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.app_state.download_manager.delete_installed_model(
                model_id=record.model_id,
                active_model_id=self.app_state.process_manager.active_model_id,
                delete_files_on_disk=True,
            )
            self.app_state.refresh_installed_models()
            self.app_state.refresh_catalog()
        except Exception as exc:
            QMessageBox.critical(self, "Delete Blocked", str(exc))

    def _import_local_gguf(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Local GGUF Model File to Import (`coli import`)",
            self.app_state.settings.models_dir,
            "GGUF Models (*.gguf)",
        )
        if not file_path:
            return
        self.model_controller.import_gguf_async(file_path, copy_mode="link")

    def _on_gguf_import_finished(self, ok: bool, msg: str) -> None:
        if ok:
            QMessageBox.information(self, "GGUF Import Complete", f"Successfully imported GGUF model:\n\n{msg}")
        else:
            QMessageBox.warning(self, "GGUF Import Failed", msg)
