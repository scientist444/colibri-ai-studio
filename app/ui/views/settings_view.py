"""Liquid Glass Settings View (`settings_view.py`) — Multi-Theme & Emoji-Free."""

from __future__ import annotations

from pathlib import Path
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.application_state import ApplicationState
from app.constants import APP_NAME, APP_VERSION
from app.controllers.backend_controller import BackendController
from app.services.settings_service import SettingsService
from app.ui.liquid_glass import LIQUID_GLASS_THEMES, LiquidGlassPanel
from app.ui.widgets.brand_logo import ColibriLogoWidget
from app.utils.logging_config import get_recent_logs
from app.utils.windows_shortcut import create_desktop_shortcut, get_windows_desktop_dir


class SettingsView(QWidget):
    """Comprehensive Liquid Glass Settings and Diagnostics center."""

    theme_changed = pyqtSignal(str)

    def __init__(
        self,
        app_state: ApplicationState,
        backend_controller: BackendController,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.app_state = app_state
        self.backend_controller = backend_controller

        self._build_ui()
        self._load_current_settings()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Header
        header = LiquidGlassPanel(self, radius=16.0, elevated=True)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(18, 12, 18, 12)

        title_col = QVBoxLayout()
        title_lbl = QLabel("Workstation Settings & Diagnostics")
        title_lbl.setObjectName("viewTitle")
        sub_lbl = QLabel(
            "Configure Liquid Glass themes, typography scaling, Colibri inference parameters, security tokens, and diagnostics"
        )
        sub_lbl.setObjectName("viewSubtitle")
        title_col.addWidget(title_lbl)
        title_col.addWidget(sub_lbl)
        h_layout.addLayout(title_col, 1)

        save_all_btn = QPushButton("Save All Settings")
        save_all_btn.setObjectName("primaryGlassButton")
        save_all_btn.clicked.connect(self._save_all_settings)
        h_layout.addWidget(save_all_btn)
        layout.addWidget(header)

        # 6 Liquid Glass Settings Tabs
        self.tabs = QTabWidget()
        self.tab_general = QWidget()
        self.tab_hardware = QWidget()
        self.tab_storage = QWidget()
        self.tab_inference = QWidget()
        self.tab_privacy = QWidget()
        self.tab_diagnostics = QWidget()

        self.tabs.addTab(self.tab_general, "01. General & Themes")
        self.tabs.addTab(self.tab_hardware, "02. Hardware")
        self.tabs.addTab(self.tab_storage, "03. Storage")
        self.tabs.addTab(self.tab_inference, "04. Inference")
        self.tabs.addTab(self.tab_privacy, "05. Privacy & Security")
        self.tabs.addTab(self.tab_diagnostics, "06. Diagnostics")

        self._build_general_tab()
        self._build_hardware_tab()
        self._build_storage_tab()
        self._build_inference_tab()
        self._build_privacy_tab()
        self._build_diagnostics_tab()

        layout.addWidget(self.tabs, 1)

    def _build_general_tab(self) -> None:
        layout = QVBoxLayout(self.tab_general)
        card = LiquidGlassPanel(self.tab_general, radius=14.0)
        grid = QGridLayout(card)
        grid.setContentsMargins(16, 14, 16, 14)
        grid.setVerticalSpacing(12)

        grid.addWidget(QLabel("Liquid Glass Visual Theme:"), 0, 0)
        self.theme_combo = QComboBox()
        for t_key, t_meta in LIQUID_GLASS_THEMES.items():
            self.theme_combo.addItem(str(t_meta["label"]), t_key)
        self.theme_combo.currentIndexChanged.connect(self._on_theme_selected)
        grid.addWidget(self.theme_combo, 0, 1)

        grid.addWidget(QLabel("Default Startup Screen:"), 1, 0)
        self.startup_combo = QComboBox()
        self.startup_combo.addItems(["chat", "model_hub", "my_models", "hardware", "performance"])
        grid.addWidget(self.startup_combo, 1, 1)

        grid.addWidget(QLabel("Typography & UI Scale Percentage:"), 2, 0)
        self.scale_spin = QSpinBox()
        self.scale_spin.setRange(75, 200)
        self.scale_spin.setSingleStep(5)
        self.scale_spin.setSuffix("%")
        grid.addWidget(self.scale_spin, 2, 1)

        self.confirm_dl_chk = QCheckBox("Always ask for confirmation before downloading large multi-GB models")
        grid.addWidget(self.confirm_dl_chk, 3, 0, 1, 2)

        shortcut_btn = QPushButton("Create / Repair Desktop Shortcut (`Colibri AI Studio.lnk`)")
        shortcut_btn.clicked.connect(self._create_shortcut_now)
        grid.addWidget(shortcut_btn, 4, 0, 1, 2, alignment=Qt.AlignmentFlag.AlignLeft)

        layout.addWidget(card)
        layout.addStretch(1)

    def _on_theme_selected(self, _idx: int) -> None:
        t_key = str(self.theme_combo.currentData() or "obsidian_glass")
        self.theme_changed.emit(t_key)

    def set_selected_theme_key(self, theme_key: str) -> None:
        self.theme_combo.blockSignals(True)
        for i in range(self.theme_combo.count()):
            if self.theme_combo.itemData(i) == theme_key:
                self.theme_combo.setCurrentIndex(i)
                break
        self.theme_combo.blockSignals(False)

    def _build_hardware_tab(self) -> None:
        layout = QVBoxLayout(self.tab_hardware)
        card = LiquidGlassPanel(self.tab_hardware, radius=14.0)
        grid = QGridLayout(card)
        grid.setContentsMargins(16, 14, 16, 14)
        grid.setVerticalSpacing(12)

        grid.addWidget(QLabel("Preferred Compute Backend:"), 0, 0)
        self.hw_backend_combo = QComboBox()
        self.hw_backend_combo.addItems(["auto", "cpu", "vulkan", "cuda"])
        grid.addWidget(self.hw_backend_combo, 0, 1)

        grid.addWidget(QLabel("GPU Offload Mode (`--gpu`):"), 1, 0)
        self.gpu_mode_combo = QComboBox()
        self.gpu_mode_combo.addItems(["auto", "off", "full", "hybrid"])
        grid.addWidget(self.gpu_mode_combo, 1, 1)

        grid.addWidget(QLabel("System RAM Safety Reserve (GB):"), 2, 0)
        self.hw_ram_reserve_spin = QDoubleSpinBox()
        self.hw_ram_reserve_spin.setRange(1.0, 128.0)
        self.hw_ram_reserve_spin.setSingleStep(0.5)
        grid.addWidget(self.hw_ram_reserve_spin, 2, 1)

        grid.addWidget(QLabel("GPU VRAM Headroom Reserve (GB):"), 3, 0)
        self.hw_vram_reserve_spin = QDoubleSpinBox()
        self.hw_vram_reserve_spin.setRange(0.0, 64.0)
        self.hw_vram_reserve_spin.setSingleStep(0.5)
        grid.addWidget(self.hw_vram_reserve_spin, 3, 1)

        layout.addWidget(card)
        layout.addStretch(1)

    def _build_storage_tab(self) -> None:
        layout = QVBoxLayout(self.tab_storage)
        card = LiquidGlassPanel(self.tab_storage, radius=14.0)
        grid = QGridLayout(card)
        grid.setContentsMargins(16, 14, 16, 14)
        grid.setVerticalSpacing(12)

        grid.addWidget(QLabel("Models Storage Directory:"), 0, 0)
        self.models_dir_edit = QLineEdit()
        grid.addWidget(self.models_dir_edit, 0, 1)
        browse_models_btn = QPushButton("Browse...")
        browse_models_btn.clicked.connect(self._browse_models_dir)
        grid.addWidget(browse_models_btn, 0, 2)

        grid.addWidget(QLabel("Colibri Engine Directory:"), 1, 0)
        self.engine_dir_edit = QLineEdit()
        grid.addWidget(self.engine_dir_edit, 1, 1)
        browse_engine_btn = QPushButton("Browse...")
        browse_engine_btn.clicked.connect(self._browse_engine_dir)
        grid.addWidget(browse_engine_btn, 1, 2)

        layout.addWidget(card)
        layout.addStretch(1)

    def _build_inference_tab(self) -> None:
        layout = QVBoxLayout(self.tab_inference)
        card = LiquidGlassPanel(self.tab_inference, radius=14.0)
        grid = QGridLayout(card)
        grid.setContentsMargins(16, 14, 16, 14)
        grid.setVerticalSpacing(10)

        grid.addWidget(QLabel("Local Server Host:"), 0, 0)
        self.host_edit = QLineEdit()
        grid.addWidget(self.host_edit, 0, 1)

        grid.addWidget(QLabel("Local Server Port:"), 1, 0)
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1024, 65535)
        grid.addWidget(self.port_spin, 1, 1)

        grid.addWidget(QLabel("Default Context Length (`--ctx`):"), 2, 0)
        self.inf_ctx_spin = QSpinBox()
        self.inf_ctx_spin.setRange(512, 262144)
        self.inf_ctx_spin.setSingleStep(1024)
        grid.addWidget(self.inf_ctx_spin, 2, 1)

        grid.addWidget(QLabel("Default Temperature:"), 3, 0)
        self.inf_temp_spin = QDoubleSpinBox()
        self.inf_temp_spin.setRange(0.0, 2.0)
        self.inf_temp_spin.setSingleStep(0.05)
        grid.addWidget(self.inf_temp_spin, 3, 1)

        grid.addWidget(QLabel("Default System Prompt:"), 4, 0)
        self.inf_sys_prompt = QPlainTextEdit()
        self.inf_sys_prompt.setFixedHeight(70)
        grid.addWidget(self.inf_sys_prompt, 4, 1)

        self.auto_tier_chk = QCheckBox("Enable Colibri Automatic 3-Tier Placement (`--auto-tier`)")
        grid.addWidget(self.auto_tier_chk, 5, 0, 1, 2)

        layout.addWidget(card)
        layout.addStretch(1)

    def _build_privacy_tab(self) -> None:
        layout = QVBoxLayout(self.tab_privacy)
        card = LiquidGlassPanel(self.tab_privacy, radius=14.0)
        grid = QGridLayout(card)
        grid.setContentsMargins(16, 14, 16, 14)
        grid.setVerticalSpacing(12)

        grid.addWidget(QLabel("Hugging Face Read Token (Windows Credential Manager):"), 0, 0)
        self.hf_token_edit = QLineEdit()
        self.hf_token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.hf_token_edit.setPlaceholderText("hf_... (Stored encrypted in Windows Credential Manager)")
        grid.addWidget(self.hf_token_edit, 0, 1)

        save_tok_btn = QPushButton("Save Token")
        save_tok_btn.clicked.connect(self._save_credentials)
        grid.addWidget(save_tok_btn, 0, 2)

        grid.addWidget(QLabel("Optional Local Server API Key (`--api-key`):"), 1, 0)
        self.local_key_edit = QLineEdit()
        self.local_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.local_key_edit.setPlaceholderText("Optional Bearer token for local HTTP server")
        grid.addWidget(self.local_key_edit, 1, 1)

        self.req_api_key_chk = QCheckBox("Require API Key on Local Server")
        grid.addWidget(self.req_api_key_chk, 2, 0, 1, 2)

        self.offline_chk = QCheckBox("Offline Mode (Disable all external GitHub / Hugging Face network calls)")
        grid.addWidget(self.offline_chk, 3, 0, 1, 2)

        self.sanitize_chk = QCheckBox("Automatically redact tokens & secrets in logs and diagnostic bundles")
        grid.addWidget(self.sanitize_chk, 4, 0, 1, 2)

        clear_hist_btn = QPushButton("Clear All Local Conversation History")
        clear_hist_btn.setObjectName("dangerGlassButton")
        clear_hist_btn.clicked.connect(self._clear_all_conversations)
        grid.addWidget(clear_hist_btn, 5, 0, 1, 2, alignment=Qt.AlignmentFlag.AlignLeft)

        layout.addWidget(card)
        layout.addStretch(1)

    def _build_diagnostics_tab(self) -> None:
        layout = QVBoxLayout(self.tab_diagnostics)
        layout.setSpacing(10)

        brand_card = LiquidGlassPanel(self.tab_diagnostics, radius=14.0, elevated=True)
        brand_row = QHBoxLayout(brand_card)
        brand_row.setContentsMargins(16, 12, 16, 12)
        brand_row.setSpacing(16)

        brand_logo = ColibriLogoWidget(brand_card, size=60, draw_medallion=True)
        brand_row.addWidget(brand_logo)

        brand_info = QVBoxLayout()
        brand_info.setSpacing(3)
        brand_title = QLabel(f"{APP_NAME} v{APP_VERSION} — Intelligent Local AI Workstation")
        brand_title.setStyleSheet("font-size: 15px; font-weight: 800; letter-spacing: 0.2px;")
        brand_desc = QLabel(
            "Powered by the Official Colibri Inference Engine  |  3-Tier VRAM / RAM / NVMe MoE Streaming  |  Windows 10/11 x64"
        )
        brand_desc.setStyleSheet("font-size: 12px; color: #94A3B8;")
        brand_info.addWidget(brand_title)
        brand_info.addWidget(brand_desc)
        brand_row.addLayout(brand_info, 1)
        layout.addWidget(brand_card)

        btn_bar = LiquidGlassPanel(self.tab_diagnostics, radius=14.0)
        b_row = QHBoxLayout(btn_bar)
        b_row.setContentsMargins(12, 8, 12, 8)

        refresh_logs_btn = QPushButton("Refresh Logs")
        refresh_logs_btn.clicked.connect(self._refresh_logs_view)
        b_row.addWidget(refresh_logs_btn)

        doctor_btn = QPushButton("Run Colibri Doctor")
        doctor_btn.clicked.connect(self._run_doctor_check)
        b_row.addWidget(doctor_btn)

        update_btn = QPushButton("Check Colibri Updates")
        update_btn.clicked.connect(self._check_updates)
        b_row.addWidget(update_btn)

        install_btn = QPushButton("Install / Repair Colibri Engine")
        install_btn.setObjectName("primaryGlassButton")
        install_btn.clicked.connect(self._install_or_repair_engine)
        b_row.addWidget(install_btn)

        export_diag_btn = QPushButton("Export Redacted Diagnostic Bundle")
        export_diag_btn.clicked.connect(self._export_diagnostics)
        b_row.addWidget(export_diag_btn)

        layout.addWidget(btn_bar)

        self.logs_viewer = QPlainTextEdit()
        self.logs_viewer.setReadOnly(True)
        layout.addWidget(self.logs_viewer, 1)

    def _load_current_settings(self) -> None:
        s = self.app_state.settings
        self.set_selected_theme_key(s.theme)
        self.startup_combo.setCurrentText(s.startup_view)
        self.scale_spin.setValue(s.ui_scale_percent)
        self.confirm_dl_chk.setChecked(s.confirm_before_large_downloads)

        self.hw_backend_combo.setCurrentText(s.preferred_backend)
        self.gpu_mode_combo.setCurrentText(s.gpu_offload_mode)
        self.hw_ram_reserve_spin.setValue(s.system_ram_reserve_gb)
        self.hw_vram_reserve_spin.setValue(s.vram_headroom_gb)

        self.models_dir_edit.setText(s.models_dir)
        self.engine_dir_edit.setText(s.engine_dir)

        self.host_edit.setText(s.server_host)
        self.port_spin.setValue(s.server_port)
        self.inf_ctx_spin.setValue(s.context_length)
        self.inf_temp_spin.setValue(s.default_temperature)
        self.inf_sys_prompt.setPlainText(s.default_system_prompt)
        self.auto_tier_chk.setChecked(s.auto_tier)

        hf_tok = SettingsService.get_huggingface_token()
        if hf_tok:
            self.hf_token_edit.setText(hf_tok)
        local_key = SettingsService.get_local_api_key()
        if local_key:
            self.local_key_edit.setText(local_key)

        self.req_api_key_chk.setChecked(s.require_local_api_key)
        self.offline_chk.setChecked(s.offline_mode)
        self.sanitize_chk.setChecked(s.sanitize_logs)
        self._refresh_logs_view()

    def _save_all_settings(self) -> None:
        self._save_credentials(silent=True)
        chosen_theme = str(self.theme_combo.currentData() or "obsidian_glass")
        self.app_state.update_settings(
            theme=chosen_theme,
            startup_view=self.startup_combo.currentText(),
            ui_scale_percent=self.scale_spin.value(),
            confirm_before_large_downloads=self.confirm_dl_chk.isChecked(),
            preferred_backend=self.hw_backend_combo.currentText(),
            gpu_offload_mode=self.gpu_mode_combo.currentText(),
            system_ram_reserve_gb=self.hw_ram_reserve_spin.value(),
            vram_headroom_gb=self.hw_vram_reserve_spin.value(),
            models_dir=self.models_dir_edit.text().strip(),
            engine_dir=self.engine_dir_edit.text().strip(),
            server_host=self.host_edit.text().strip() or "127.0.0.1",
            server_port=self.port_spin.value(),
            context_length=self.inf_ctx_spin.value(),
            default_temperature=self.inf_temp_spin.value(),
            default_system_prompt=self.inf_sys_prompt.toPlainText().strip(),
            auto_tier=self.auto_tier_chk.isChecked(),
            require_local_api_key=self.req_api_key_chk.isChecked(),
            offline_mode=self.offline_chk.isChecked(),
            sanitize_logs=self.sanitize_chk.isChecked(),
        )
        self.theme_changed.emit(chosen_theme)
        QMessageBox.information(self, "Settings Saved", "All workstation settings and theme preferences have been saved.")

    def _save_credentials(self, silent: bool = False) -> None:
        SettingsService.set_huggingface_token(self.hf_token_edit.text().strip() or None)
        SettingsService.set_local_api_key(self.local_key_edit.text().strip() or None)
        if not silent:
            QMessageBox.information(
                self,
                "Credentials Saved",
                "Credentials securely updated in Windows Credential Manager.",
            )

    def _browse_models_dir(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Select Models Directory", self.models_dir_edit.text())
        if chosen:
            self.models_dir_edit.setText(str(Path(chosen).resolve()))

    def _browse_engine_dir(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Select Engine Directory", self.engine_dir_edit.text())
        if chosen:
            self.engine_dir_edit.setText(str(Path(chosen).resolve()))

    def _clear_all_conversations(self) -> None:
        reply = QMessageBox.question(
            self,
            "Clear All Conversations",
            "Permanently delete all local conversations and messages from SQLite?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.app_state.conversations_repo.clear_all_conversations()
            QMessageBox.information(self, "History Cleared", "All conversation history has been deleted.")

    def _refresh_logs_view(self) -> None:
        self.logs_viewer.setPlainText(get_recent_logs(max_lines=300))

    def _run_doctor_check(self) -> None:
        res = self.app_state.adapter.run_doctor(
            model_dir=self.app_state.settings.active_model_path or None
        )
        import json

        self.logs_viewer.appendPlainText("\n--- COLIBRI DOCTOR REPORT ---\n" + json.dumps(res, indent=2))

    def _check_updates(self) -> None:
        info = self.app_state.update_service.check_for_updates()
        import json

        self.logs_viewer.appendPlainText("\n--- UPDATE CHECK ---\n" + json.dumps(info, indent=2))

    def _install_or_repair_engine(self) -> None:
        reply = QMessageBox.question(
            self,
            "Install / Repair Colibri Engine",
            "Download and extract the latest official Colibri Windows x86_64 release from GitHub into your engine directory?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.backend_controller.install_colibri_engine_async(
                include_cuda=self.app_state.hardware.cuda_available
            )

    def _export_diagnostics(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Redacted Diagnostic Bundle",
            "colibri_diagnostics.json",
            "JSON Files (*.json)",
        )
        if not file_path:
            return
        out = self.app_state.diagnostics_service.export_diagnostic_bundle(
            output_path=Path(file_path),
            hardware=self.app_state.hardware,
            settings=self.app_state.settings,
            active_model_path=self.app_state.settings.active_model_path,
        )
        QMessageBox.information(self, "Diagnostics Exported", f"Redacted diagnostic bundle saved to:\n{out}")

    def _create_shortcut_now(self) -> None:
        import sys
        from app.utils.paths import get_assets_dir

        exe_target = Path(sys.executable).resolve()
        icon_file = get_assets_dir() / "icons" / "app_icon.ico"
        try:
            lnk = create_desktop_shortcut(
                target_exe=exe_target,
                working_dir=exe_target.parent,
                icon_path=icon_file if icon_file.exists() else exe_target,
                desktop_dir=get_windows_desktop_dir(),
            )
            QMessageBox.information(self, "Desktop Shortcut Created", f"Shortcut created at:\n{lnk}")
        except Exception as exc:
            QMessageBox.warning(self, "Shortcut Error", str(exc))
