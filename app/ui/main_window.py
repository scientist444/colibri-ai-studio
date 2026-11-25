"""Main Application Window (`main_window.py`) with Multi-Theme Liquid Glass & Navigation."""

from __future__ import annotations

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QStackedWidget,
    QWidget,
)

from app.application_state import ApplicationState
from app.constants import APP_NAME, APP_VERSION
from app.controllers.backend_controller import BackendController
from app.controllers.chat_controller import ChatController
from app.controllers.model_controller import ModelController
from app.models.model_metadata import ModelCandidate
from app.ui.liquid_glass import (
    LiquidGlassBackdrop,
    apply_theme_to_app,
    apply_windows_liquid_glass,
)
from app.ui.views.chat_view import ChatView
from app.ui.views.hardware_view import HardwareMonitorView
from app.ui.views.model_hub_view import ModelHubView
from app.ui.views.my_models_view import MyModelsView
from app.ui.views.onboarding_view import OnboardingWizardDialog
from app.ui.views.performance_view import PerformanceLabView
from app.ui.views.settings_view import SettingsView
from app.ui.widgets.sidebar import NavigationSidebar


class MainWindow(QMainWindow):
    """Primary Liquid Glass Desktop Window for Colibri AI Studio."""

    def __init__(self, app_state: ApplicationState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.app_state = app_state

        # Controllers
        self.backend_controller = BackendController(app_state)
        self.chat_controller = ChatController(app_state)
        self.model_controller = ModelController(app_state)

        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION} — Intelligent Local AI Workstation")
        self.setMinimumSize(1180, 760)
        self.resize(1340, 840)

        apply_theme_to_app(
            self.app_state.settings.theme,
            scale_percent=self.app_state.settings.ui_scale_percent,
        )
        apply_windows_liquid_glass(self)
        self._build_ui()
        self._connect_signals()

        initial_view = self.app_state.settings.startup_view
        self.switch_view(initial_view if initial_view in self._view_indices else "chat")

        if not self.app_state.settings.first_run_completed:
            QTimer.singleShot(250, self.open_onboarding_wizard)

    def _build_ui(self) -> None:
        self.backdrop = LiquidGlassBackdrop(self)
        self.setCentralWidget(self.backdrop)

        root_layout = QHBoxLayout(self.backdrop)
        root_layout.setContentsMargins(14, 14, 14, 14)
        root_layout.setSpacing(14)

        self.sidebar = NavigationSidebar(self.backdrop)
        self.sidebar.set_selected_theme_key(self.app_state.settings.theme)
        root_layout.addWidget(self.sidebar)

        self.stack = QStackedWidget(self.backdrop)
        self.chat_view = ChatView(
            self.app_state, self.chat_controller, self.backend_controller, self.stack
        )
        self.model_hub_view = ModelHubView(
            self.app_state, self.model_controller, self.backend_controller, self.stack
        )
        self.my_models_view = MyModelsView(
            self.app_state, self.model_controller, self.backend_controller, self.stack
        )
        self.hardware_view = HardwareMonitorView(self.app_state, self.stack)
        self.performance_view = PerformanceLabView(self.app_state, self.stack)
        self.settings_view = SettingsView(
            self.app_state, self.backend_controller, self.stack
        )

        self._view_indices: dict[str, int] = {
            "chat": self.stack.addWidget(self.chat_view),
            "model_hub": self.stack.addWidget(self.model_hub_view),
            "my_models": self.stack.addWidget(self.my_models_view),
            "hardware": self.stack.addWidget(self.hardware_view),
            "performance": self.stack.addWidget(self.performance_view),
            "settings": self.stack.addWidget(self.settings_view),
        }

        root_layout.addWidget(self.stack, 1)

        pm = self.app_state.process_manager
        self.sidebar.update_backend_status(
            state=pm.state.value,
            detail=pm.state_detail,
            active_model=pm.active_model_id,
        )

    def _connect_signals(self) -> None:
        self.sidebar.view_selected.connect(self.switch_view)
        self.sidebar.wizard_requested.connect(self.open_onboarding_wizard)
        self.sidebar.theme_selected.connect(self.apply_and_persist_theme)
        self.settings_view.theme_changed.connect(self.apply_and_persist_theme)

        self.app_state.navigation_requested.connect(self.switch_view)
        self.app_state.process_manager.state_changed.connect(
            lambda st, det: self.sidebar.update_backend_status(
                state=st,
                detail=det,
                active_model=self.app_state.process_manager.active_model_id,
            )
        )
        self.app_state.active_model_changed.connect(
            lambda mid, _mpath: self.sidebar.update_backend_status(
                state=self.app_state.process_manager.state.value,
                detail=self.app_state.process_manager.state_detail,
                active_model=mid,
            )
        )

    def apply_and_persist_theme(self, theme_key: str) -> None:
        self.app_state.settings_service.update(theme=theme_key)
        apply_theme_to_app(
            theme_key,
            scale_percent=self.app_state.settings.ui_scale_percent,
        )
        apply_windows_liquid_glass(self)
        self.sidebar.set_selected_theme_key(theme_key)
        self.settings_view.set_selected_theme_key(theme_key)
        self.backdrop.update()

    def switch_view(self, view_key: str) -> None:
        idx = self._view_indices.get(view_key)
        if idx is not None:
            self.stack.setCurrentIndex(idx)
            self.sidebar.set_active_view(view_key, emit_signal=False)

    def open_onboarding_wizard(self) -> None:
        dlg = OnboardingWizardDialog(
            app_state=self.app_state,
            backend_controller=self.backend_controller,
            parent=self,
        )
        dlg.download_recommended_requested.connect(self._on_wizard_download_requested)
        dlg.exec()

    def _on_wizard_download_requested(self, candidate: ModelCandidate) -> None:
        self.switch_view("model_hub")
        self.model_hub_view.confirm_and_enqueue_download(candidate)

    def closeEvent(self, event: QCloseEvent | None) -> None:  # noqa: N802
        """Gracefully stop any owned Colibri server processes on window close."""
        try:
            self.hardware_view._timer.stop()
            self.chat_controller.stop_generation()
            self.app_state.process_manager.stop_server()
        except Exception:
            pass
        if event is not None:
            event.accept()
