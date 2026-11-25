"""Liquid Glass Model Hub View (`model_hub_view.py`) — Emoji-Free Professional Workstation Design."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
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
from app.core.storage_manager import StorageManager
from app.models.model_metadata import CompatibilityBadge, ModelCandidate
from app.ui.liquid_glass import LiquidGlassPanel
from app.ui.widgets.model_card import ModelHubCard, PreDownloadConfirmDialog


class ModelHubView(QWidget):
    """Liquid Glass Model Hub for discovering and downloading compatible local AI models."""

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

        self._hf_candidates: list[ModelCandidate] = []
        self._build_ui()
        self._connect_signals()
        self.render_catalog_list()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Header Glass Panel
        header = LiquidGlassPanel(self, radius=16.0, elevated=True)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(18, 12, 18, 12)

        title_col = QVBoxLayout()
        title_lbl = QLabel("Intelligent Model Hub")
        title_lbl.setObjectName("viewTitle")
        sub_lbl = QLabel(
            "Discover Official Colibri MoE Models and Verified Compatible Hugging Face Repositories Tailored to Your Workstation"
        )
        sub_lbl.setObjectName("viewSubtitle")
        title_col.addWidget(title_lbl)
        title_col.addWidget(sub_lbl)
        h_layout.addLayout(title_col, 1)

        refresh_btn = QPushButton("Refresh Compatibility")
        refresh_btn.clicked.connect(self._refresh_all)
        h_layout.addWidget(refresh_btn)
        layout.addWidget(header)

        # Filter & Sort Liquid Glass Bar
        filter_bar = LiquidGlassPanel(self, radius=14.0)
        f_layout = QHBoxLayout(filter_bar)
        f_layout.setContentsMargins(14, 10, 14, 10)
        f_layout.setSpacing(12)

        self.filter_text = QLineEdit()
        self.filter_text.setPlaceholderText("Filter catalog by name, family, or description...")
        self.filter_text.textChanged.connect(self.render_catalog_list)
        f_layout.addWidget(self.filter_text, 1)

        f_layout.addWidget(QLabel("Compatibility:"))
        self.compat_combo = QComboBox()
        self.compat_combo.addItems(["All Models", "Recommended (Green)", "Runs with Streaming (Green + Yellow)"])
        self.compat_combo.currentIndexChanged.connect(self.render_catalog_list)
        f_layout.addWidget(self.compat_combo)

        f_layout.addWidget(QLabel("Sort By:"))
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Compatibility First", "Smallest Download Size", "Lowest Minimum RAM"])
        self.sort_combo.currentIndexChanged.connect(self.render_catalog_list)
        f_layout.addWidget(self.sort_combo)

        layout.addWidget(filter_bar)

        # Liquid Glass Tabs: Official Catalog vs Live Hugging Face Search
        self.tabs = QTabWidget()

        # Tab 1: Official Colibri Catalog
        self.catalog_tab = QWidget()
        c_layout = QVBoxLayout(self.catalog_tab)
        c_layout.setContentsMargins(6, 6, 6, 6)

        self.catalog_scroll = QScrollArea()
        self.catalog_scroll.setWidgetResizable(True)
        self.catalog_container = QWidget()
        self.catalog_cards_layout = QVBoxLayout(self.catalog_container)
        self.catalog_cards_layout.setContentsMargins(6, 6, 6, 6)
        self.catalog_cards_layout.setSpacing(12)
        self.catalog_cards_layout.addStretch(1)
        self.catalog_scroll.setWidget(self.catalog_container)
        c_layout.addWidget(self.catalog_scroll, 1)
        self.tabs.addTab(self.catalog_tab, "Official Colibri Model Catalog")

        # Tab 2: Hugging Face Hub Live Search
        self.hf_tab = QWidget()
        hf_layout = QVBoxLayout(self.hf_tab)
        hf_layout.setContentsMargins(6, 6, 6, 6)
        hf_layout.setSpacing(10)

        hf_search_row = QHBoxLayout()
        self.hf_search_edit = QLineEdit("colibri qwen3 moe")
        self.hf_search_edit.setPlaceholderText(
            "Search Hugging Face repositories (e.g. 'colibri', 'qwen3 moe gguf', 'deepseek-v4', 'glm-5')..."
        )
        self.hf_search_edit.returnPressed.connect(self._trigger_hf_search)
        hf_search_row.addWidget(self.hf_search_edit, 1)

        self.hf_search_btn = QPushButton("Search Hugging Face Hub")
        self.hf_search_btn.setObjectName("primaryGlassButton")
        self.hf_search_btn.clicked.connect(self._trigger_hf_search)
        hf_search_row.addWidget(self.hf_search_btn)
        hf_layout.addLayout(hf_search_row)

        self.hf_status_lbl = QLabel(
            "Architecture verification active: repositories are validated against Colibri's supported `model_type` and GGUF architecture registry."
        )
        self.hf_status_lbl.setStyleSheet("font-size: 12px; color: #94A3B8;")
        hf_layout.addWidget(self.hf_status_lbl)

        self.hf_scroll = QScrollArea()
        self.hf_scroll.setWidgetResizable(True)
        self.hf_container = QWidget()
        self.hf_cards_layout = QVBoxLayout(self.hf_container)
        self.hf_cards_layout.setContentsMargins(6, 6, 6, 6)
        self.hf_cards_layout.setSpacing(12)
        self.hf_cards_layout.addStretch(1)
        self.hf_scroll.setWidget(self.hf_container)
        hf_layout.addWidget(self.hf_scroll, 1)

        self.tabs.addTab(self.hf_tab, "Hugging Face Hub Live Discovery")
        layout.addWidget(self.tabs, 1)

    def _connect_signals(self) -> None:
        self.app_state.catalog_updated.connect(lambda _: self.render_catalog_list())
        self.model_controller.hf_search_started.connect(self._on_hf_started)
        self.model_controller.hf_search_results.connect(self._on_hf_results)
        self.model_controller.hf_search_error.connect(self._on_hf_error)

    def _refresh_all(self) -> None:
        self.app_state.refresh_installed_models()
        self.app_state.refresh_catalog()

    def _filter_and_sort(self, items: list[ModelCandidate]) -> list[ModelCandidate]:
        q = self.filter_text.text().strip().lower()
        compat_idx = self.compat_combo.currentIndex()
        sort_idx = self.sort_combo.currentIndex()

        filtered: list[ModelCandidate] = []
        for c in items:
            if q and not (
                q in c.display_name.lower()
                or q in c.hf_repo.lower()
                or q in c.family.lower()
                or q in c.description.lower()
            ):
                continue
            if compat_idx == 1 and c.compatibility.badge != CompatibilityBadge.GREEN:
                continue
            if compat_idx == 2 and c.compatibility.badge == CompatibilityBadge.RED:
                continue
            filtered.append(c)

        badge_rank = {
            CompatibilityBadge.GREEN: 0,
            CompatibilityBadge.YELLOW: 1,
            CompatibilityBadge.RED: 2,
        }
        if sort_idx == 0:
            filtered.sort(key=lambda c: (badge_rank.get(c.compatibility.badge, 3), c.download_size_gb))
        elif sort_idx == 1:
            filtered.sort(key=lambda c: c.download_size_gb)
        else:
            filtered.sort(key=lambda c: c.ram_min_gb)

        return filtered

    def render_catalog_list(self) -> None:
        while self.catalog_cards_layout.count() > 1:
            item = self.catalog_cards_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        items = self._filter_and_sort(self.app_state.catalog_candidates)
        for cand in items:
            card = ModelHubCard(cand, parent=self.catalog_container)
            card.download_requested.connect(self.confirm_and_enqueue_download)
            card.launch_requested.connect(self._launch_installed_candidate)
            self.catalog_cards_layout.insertWidget(self.catalog_cards_layout.count() - 1, card)

    def _trigger_hf_search(self) -> None:
        q = self.hf_search_edit.text().strip()
        self.model_controller.search_huggingface_async(q)

    def _on_hf_started(self) -> None:
        self.hf_search_btn.setEnabled(False)
        self.hf_status_lbl.setText("Searching live Hugging Face Hub API and verifying Colibri architectures...")

    def _on_hf_results(self, results: list[ModelCandidate]) -> None:
        self.hf_search_btn.setEnabled(True)
        self._hf_candidates = results
        self.hf_status_lbl.setText(f"Found {len(results)} repositories on Hugging Face.")

        while self.hf_cards_layout.count() > 1:
            item = self.hf_cards_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        for cand in self._filter_and_sort(results):
            card = ModelHubCard(cand, parent=self.hf_container)
            card.download_requested.connect(self.confirm_and_enqueue_download)
            card.launch_requested.connect(self._launch_installed_candidate)
            self.hf_cards_layout.insertWidget(self.hf_cards_layout.count() - 1, card)

    def _on_hf_error(self, title: str, body: str) -> None:
        self.hf_search_btn.setEnabled(True)
        self.hf_status_lbl.setText(f"{title}: {body.splitlines()[0]}")
        QMessageBox.warning(self, title, body)

    def confirm_and_enqueue_download(self, candidate: ModelCandidate) -> None:
        models_dir = self.app_state.settings.models_dir
        free_gb = StorageManager.get_free_space_gb(models_dir)

        if self.app_state.settings.confirm_before_large_downloads:
            dlg = PreDownloadConfirmDialog(
                candidate=candidate,
                target_dir=models_dir,
                free_space_gb=free_gb,
                parent=self,
            )
            if dlg.exec() != PreDownloadConfirmDialog.DialogCode.Accepted:
                return

        try:
            self.app_state.download_manager.enqueue_download(candidate, models_dir)
            self.app_state.navigation_requested.emit("my_models")
        except Exception as exc:
            QMessageBox.critical(self, "Cannot Start Download", str(exc))

    def _launch_installed_candidate(self, candidate: ModelCandidate) -> None:
        if candidate.local_path:
            self.backend_controller.start_model_async(candidate.model_id, candidate.local_path)
            self.app_state.navigation_requested.emit("chat")
