"""Smart First-Launch Setup Wizard (`onboarding_view.py`) with Liquid Glass UI (Emoji-Free)."""

from __future__ import annotations

from pathlib import Path
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.application_state import ApplicationState
from app.controllers.backend_controller import BackendController
from app.models.model_metadata import CompatibilityBadge, ModelCandidate
from app.ui.liquid_glass import LiquidGlassDialog, LiquidGlassPanel
from app.ui.widgets.brand_logo import ColibriLogoWidget
from app.ui.widgets.status_badge import StatusBadge


class OnboardingWizardDialog(LiquidGlassDialog):
    """First-run Liquid Glass wizard performing 10-point hardware, backend, and catalog setup."""

    download_recommended_requested = pyqtSignal(object)  # ModelCandidate

    def __init__(
        self,
        app_state: ApplicationState,
        backend_controller: BackendController,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent=parent, title="Colibri AI Studio — System & Engine Setup Wizard")
        self.app_state = app_state
        self.backend_controller = backend_controller
        self._recommended_model: ModelCandidate | None = None

        self.setMinimumSize(820, 610)
        self._build_ui()
        self._populate_data()

        self.backend_controller.install_progress.connect(self._on_install_progress)
        self.backend_controller.install_finished.connect(self._on_install_finished)

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(24, 20, 24, 20)
        root_layout.setSpacing(14)

        # Header
        header_panel = LiquidGlassPanel(self, radius=14.0, elevated=True)
        h_layout = QHBoxLayout(header_panel)
        h_layout.setContentsMargins(16, 12, 16, 12)
        h_layout.setSpacing(14)

        self.wizard_logo = ColibriLogoWidget(header_panel, size=54, draw_medallion=True)
        h_layout.addWidget(self.wizard_logo)

        title_col = QVBoxLayout()
        title_lbl = QLabel("Welcome to Colibri AI Studio")
        title_lbl.setObjectName("viewTitle")
        sub_lbl = QLabel(
            "Intelligent Local AI Workstation for Windows — Automatic Hardware Profiling, Backend Setup & Model Selection"
        )
        sub_lbl.setObjectName("viewSubtitle")
        title_col.addWidget(title_lbl)
        title_col.addWidget(sub_lbl)
        h_layout.addLayout(title_col, 1)

        self.engine_badge = StatusBadge("CHECKING ENGINE...", variant="info")
        h_layout.addWidget(self.engine_badge)
        root_layout.addWidget(header_panel)

        # Liquid Glass Wizard Tabs
        self.tabs = QTabWidget()
        self.tab_hw = QWidget()
        self.tab_engine = QWidget()
        self.tab_models = QWidget()

        self.tabs.addTab(self.tab_hw, "01. Hardware & System Scan")
        self.tabs.addTab(self.tab_engine, "02. Colibri Engine & Storage")
        self.tabs.addTab(self.tab_models, "03. Recommended Starting Model")

        self._build_hw_tab()
        self._build_engine_tab()
        self._build_models_tab()

        root_layout.addWidget(self.tabs, 1)

        # Navigation Footer
        footer_row = QHBoxLayout()
        self.rescan_btn = QPushButton("Re-Scan Hardware")
        self.rescan_btn.clicked.connect(self._rescan_hardware)
        footer_row.addWidget(self.rescan_btn)

        footer_row.addStretch(1)

        self.prev_btn = QPushButton("Previous")
        self.prev_btn.clicked.connect(self._go_prev_tab)
        footer_row.addWidget(self.prev_btn)

        self.next_btn = QPushButton("Next Step")
        self.next_btn.setObjectName("primaryGlassButton")
        self.next_btn.clicked.connect(self._go_next_tab)
        footer_row.addWidget(self.next_btn)

        self.finish_btn = QPushButton("Complete Setup & Enter Studio")
        self.finish_btn.setObjectName("primaryGlassButton")
        self.finish_btn.clicked.connect(self._finish_wizard)
        footer_row.addWidget(self.finish_btn)

        root_layout.addLayout(footer_row)

    def _build_hw_tab(self) -> None:
        layout = QVBoxLayout(self.tab_hw)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        card = LiquidGlassPanel(self.tab_hw, radius=14.0)
        grid = QGridLayout(card)
        grid.setContentsMargins(16, 14, 16, 14)
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(10)

        self.hw_labels: dict[str, QLabel] = {}
        rows = [
            ("os", "01. Operating System & Arch:"),
            ("cpu", "02. Processor & Cores:"),
            ("isa", "03. CPU Instruction Sets:"),
            ("ram", "04. Installed & Safe Allocatable RAM:"),
            ("gpu", "05. Primary GPU & Dedicated VRAM:"),
            ("backends", "06. Available Inference Backends:"),
            ("storage", "07. Accessible Storage Volumes:"),
        ]
        for idx, (key, caption) in enumerate(rows):
            cap_lbl = QLabel(caption)
            cap_lbl.setStyleSheet("font-weight: 700; color: #38BDF8;")
            val_lbl = QLabel("Scanning...")
            val_lbl.setWordWrap(True)
            val_lbl.setStyleSheet("font-weight: 600;")
            grid.addWidget(cap_lbl, idx, 0)
            grid.addWidget(val_lbl, idx, 1)
            self.hw_labels[key] = val_lbl

        layout.addWidget(card)
        layout.addStretch(1)

    def _build_engine_tab(self) -> None:
        layout = QVBoxLayout(self.tab_engine)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Colibri Installation Card
        eng_card = LiquidGlassPanel(self.tab_engine, radius=14.0)
        eng_layout = QVBoxLayout(eng_card)
        eng_layout.setContentsMargins(16, 14, 16, 14)
        eng_layout.setSpacing(8)

        eng_title = QLabel("Colibri Inference Engine Status")
        eng_title.setObjectName("sectionHeader")
        eng_layout.addWidget(eng_title)

        self.engine_status_text = QLabel()
        self.engine_status_text.setWordWrap(True)
        eng_layout.addWidget(self.engine_status_text)

        self.cuda_checkbox = QCheckBox(
            "Also download optional CUDA GPU backend plugin (`colibri-windows-x86_64-cuda.zip`)"
        )
        self.cuda_checkbox.setChecked(self.app_state.hardware.cuda_available)
        eng_layout.addWidget(self.cuda_checkbox)

        self.install_progress_bar = QProgressBar()
        self.install_progress_bar.setRange(0, 100)
        self.install_progress_bar.setVisible(False)
        eng_layout.addWidget(self.install_progress_bar)

        btn_row = QHBoxLayout()
        self.install_engine_btn = QPushButton("Install Official Colibri Release from GitHub")
        self.install_engine_btn.setObjectName("primaryGlassButton")
        self.install_engine_btn.clicked.connect(self._confirm_and_install_engine)
        btn_row.addWidget(self.install_engine_btn)

        self.diag_btn = QPushButton("Run Colibri Diagnostics")
        self.diag_btn.clicked.connect(self._run_diagnostics)
        btn_row.addWidget(self.diag_btn)
        btn_row.addStretch(1)
        eng_layout.addLayout(btn_row)
        layout.addWidget(eng_card)

        # Model Storage Directory Selection Card
        storage_card = LiquidGlassPanel(self.tab_engine, radius=14.0)
        st_layout = QVBoxLayout(storage_card)
        st_layout.setContentsMargins(16, 14, 16, 14)
        st_layout.setSpacing(8)

        st_title = QLabel("Recommended Model Storage Directory")
        st_title.setObjectName("sectionHeader")
        st_layout.addWidget(st_title)

        st_sub = QLabel(
            "Colibri streams massive MoE experts directly from NVMe/SSD storage. Select a fast drive with ample free space:"
        )
        st_sub.setStyleSheet("color: #94A3B8; font-size: 12px;")
        st_layout.addWidget(st_sub)

        dir_row = QHBoxLayout()
        self.models_dir_edit = QLineEdit(self.app_state.settings.models_dir)
        dir_row.addWidget(self.models_dir_edit, 1)

        browse_btn = QPushButton("Browse Folder...")
        browse_btn.clicked.connect(self._browse_models_dir)
        dir_row.addWidget(browse_btn)
        st_layout.addLayout(dir_row)

        layout.addWidget(storage_card)
        layout.addStretch(1)

    def _build_models_tab(self) -> None:
        layout = QVBoxLayout(self.tab_models)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        rec_card = LiquidGlassPanel(self.tab_models, radius=14.0, elevated=True)
        r_layout = QVBoxLayout(rec_card)
        r_layout.setContentsMargins(16, 14, 16, 14)
        r_layout.setSpacing(8)

        title = QLabel("Recommended Starting Model for Your Hardware")
        title.setObjectName("sectionHeader")
        r_layout.addWidget(title)

        self.rec_model_summary = QLabel()
        self.rec_model_summary.setWordWrap(True)
        self.rec_model_summary.setStyleSheet("font-size: 13px;")
        r_layout.addWidget(self.rec_model_summary)

        action_row = QHBoxLayout()
        self.dl_rec_btn = QPushButton("Queue Recommended Model Download")
        self.dl_rec_btn.setObjectName("primaryGlassButton")
        self.dl_rec_btn.clicked.connect(self._request_recommended_download)
        action_row.addWidget(self.dl_rec_btn)
        action_row.addStretch(1)
        r_layout.addLayout(action_row)

        layout.addWidget(rec_card)

        catalog_note = QLabel(
            "Note: You can explore all 12 official Colibri models and search compatible Hugging Face GGUF / MoE models anytime in the Model Hub section."
        )
        catalog_note.setWordWrap(True)
        catalog_note.setStyleSheet("color: #94A3B8; font-size: 12px;")
        layout.addWidget(catalog_note)
        layout.addStretch(1)

    def _populate_data(self) -> None:
        hw = self.app_state.hardware
        self.hw_labels["os"].setText(f"{hw.os_name} {hw.os_release} ({hw.os_version}) — {hw.cpu.architecture}")
        self.hw_labels["cpu"].setText(
            f"{hw.cpu.name} — {hw.cpu.physical_cores} Physical ({hw.cpu.performance_cores} P-Cores) / {hw.cpu.logical_cores} Threads"
        )
        self.hw_labels["isa"].setText(", ".join(hw.cpu.instruction_sets) or "Standard x86_64")
        self.hw_labels["ram"].setText(
            f"{hw.ram.total_gb:.1f} GB Installed  |  {hw.ram.available_gb:.1f} GB Available  |  "
            f"{hw.ram.safe_allocatable_gb:.1f} GB Safe Inference Budget ({hw.ram.safety_reserve_gb:.1f} GB Reserved for Windows)"
        )

        gpu = hw.primary_gpu
        if gpu:
            kind = "Discrete GPU" if gpu.is_discrete else "Integrated GPU"
            self.hw_labels["gpu"].setText(
                f"{gpu.name} ({kind}) — {gpu.dedicated_vram_gb:.1f} GB Dedicated VRAM"
            )
        else:
            self.hw_labels["gpu"].setText("No Dedicated GPU Detected (CPU Inference Ready)")

        backends = ["CPU (AVX2/VNNI)"]
        if hw.vulkan_available:
            backends.append("Vulkan Compute (vulkan-1.dll)")
        if hw.cuda_available:
            backends.append("NVIDIA CUDA (nvcuda.dll)")
        self.hw_labels["backends"].setText(
            f"{' + '.join(backends)}  ->  Recommended: {hw.recommended_backend.upper()}"
        )

        vol_strs = [
            f"{v.drive_letter} ({v.free_gb:.1f} GB free / {v.total_gb:.1f} GB, {'NVMe' if v.is_nvme else ('SSD' if v.is_ssd else 'HDD')})"
            for v in hw.volumes
        ]
        self.hw_labels["storage"].setText("  |  ".join(vol_strs) if vol_strs else "Standard Local Volume")

        eng_info = self.app_state.adapter.detect_installed_engine_binaries()
        ver = eng_info.get("version", "unknown")
        bins = eng_info.get("native_binaries", [])
        if eng_info.get("has_native_binaries"):
            self.engine_badge.set_variant("green", f"COLIBRI {ver} INSTALLED")
            self.engine_status_text.setText(
                f"[OK] Colibri {ver} is installed at {eng_info.get('engine_dir')} "
                f"with {len(bins)} native inference binaries ({', '.join(bins[:4])})."
            )
        else:
            self.engine_badge.set_variant("yellow", f"CONTROL PLANE v{ver} READY")
            self.engine_status_text.setText(
                f"Colibri Python control plane (v{ver}) is bundled and ready at {eng_info.get('engine_dir')}.\n"
                "To run local model inference, click 'Install Official Colibri Release from GitHub' below to download "
                "the prebuilt Windows C inference binaries (`colibri.exe`, `qwen36.exe`, Vulkan shaders)."
            )

        candidates = self.app_state.catalog_candidates
        green_cands = [
            c for c in candidates if c.compatibility.badge == CompatibilityBadge.GREEN and c.modality == "text"
        ]
        yellow_cands = [
            c for c in candidates if c.compatibility.badge == CompatibilityBadge.YELLOW and c.modality == "text"
        ]
        best = (
            min(green_cands, key=lambda c: c.download_size_gb)
            if green_cands
            else (min(yellow_cands, key=lambda c: c.download_size_gb) if yellow_cands else (candidates[0] if candidates else None))
        )
        self._recommended_model = best
        if best:
            self.rec_model_summary.setText(
                f"RECOMMENDED: {best.display_name} ({best.hf_repo})\n\n"
                f"- Architecture: {best.family} ({best.parameter_count}, {best.active_parameters})\n"
                f"- Download Size: {best.download_size_gb:.1f} GB  |  Minimum RAM: {best.ram_min_gb:.1f} GB (Recommended: {best.ram_good_gb:.1f} GB)\n"
                f"- Assessment on Your PC: {best.compatibility.badge_label} — {best.compatibility.expected_mode}\n"
                f"- Summary: {best.description}"
            )
            self.dl_rec_btn.setEnabled(best.compatibility.can_download)
        else:
            self.rec_model_summary.setText("No catalog models available.")
            self.dl_rec_btn.setEnabled(False)

    def _rescan_hardware(self) -> None:
        self.app_state.hardware = self.app_state.hardware_profiler.scan_system(
            workload_profile=self.app_state.settings.workload_profile,
            safety_reserve_gb=self.app_state.settings.system_ram_reserve_gb,
        )
        self.app_state.refresh_catalog()
        self._populate_data()

    def _confirm_and_install_engine(self) -> None:
        reply = QMessageBox.question(
            self,
            "Permission to Download Colibri Engine",
            "Colibri AI Studio will download the official Colibri Windows x86_64 release archive from "
            "https://github.com/JustVugg/colibri/releases and extract it into your local application directory:\n\n"
            f"{self.app_state.adapter.engine_dir}\n\n"
            "No system-wide packages will be installed and your system PATH will not be modified.\n\n"
            "Do you want to proceed?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.install_engine_btn.setEnabled(False)
        self.install_progress_bar.setVisible(True)
        self.install_progress_bar.setValue(0)
        self.backend_controller.install_colibri_engine_async(
            include_cuda=self.cuda_checkbox.isChecked()
        )

    def _on_install_progress(self, msg: str, pct: float) -> None:
        self.engine_status_text.setText(msg)
        self.install_progress_bar.setValue(int(round(pct)))

    def _on_install_finished(self, ok: bool, msg: str) -> None:
        self.install_engine_btn.setEnabled(True)
        self.install_progress_bar.setVisible(False)
        self._populate_data()
        if ok:
            QMessageBox.information(self, "Colibri Engine Installed", msg)
        else:
            QMessageBox.warning(self, "Colibri Engine Installation Notice", msg)

    def _run_diagnostics(self) -> None:
        info = self.app_state.adapter.detect_installed_engine_binaries()
        lines = [
            f"Engine Directory: {info.get('engine_dir')}",
            f"Colibri Version: {info.get('version')}",
            f"Control Plane Ready: {info.get('control_plane_ready')}",
            f"Native Engine Executables: {', '.join(info.get('native_binaries', [])) or 'None installed yet'}",
            f"Vulkan SPIR-V Shaders: {'Present' if info.get('has_vulkan_shaders') else 'Not present'}",
            f"CUDA Plugin (coli_cuda.dll): {'Present' if info.get('has_cuda_plugin') else 'Not present'}",
        ]
        QMessageBox.information(self, "Colibri Engine Diagnostics", "\n".join(lines))

    def _browse_models_dir(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self,
            "Select Model Storage Directory",
            self.models_dir_edit.text(),
        )
        if chosen:
            self.models_dir_edit.setText(str(Path(chosen).resolve()))

    def _request_recommended_download(self) -> None:
        if not self._recommended_model:
            return
        self._save_wizard_choices()
        self.download_recommended_requested.emit(self._recommended_model)
        self.accept()

    def _go_prev_tab(self) -> None:
        idx = self.tabs.currentIndex()
        if idx > 0:
            self.tabs.setCurrentIndex(idx - 1)

    def _go_next_tab(self) -> None:
        idx = self.tabs.currentIndex()
        if idx + 1 < self.tabs.count():
            self.tabs.setCurrentIndex(idx + 1)

    def _save_wizard_choices(self) -> None:
        chosen_dir = self.models_dir_edit.text().strip()
        if chosen_dir:
            Path(chosen_dir).mkdir(parents=True, exist_ok=True)
            self.app_state.update_settings(
                first_run_completed=True,
                models_dir=chosen_dir,
            )
        else:
            self.app_state.update_settings(first_run_completed=True)

    def _finish_wizard(self) -> None:
        self._save_wizard_choices()
        self.accept()
