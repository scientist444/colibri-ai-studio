"""Application Bootstrap & Initialization (`bootstrap.py`)."""

from __future__ import annotations

import ctypes
import logging
import sys

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from app.application_state import ApplicationState
from app.constants import APP_NAME, APP_ORGANIZATION, APP_VERSION
from app.ui.liquid_glass import apply_theme_to_app
from app.ui.main_window import MainWindow
from app.ui.widgets.brand_logo import build_colibri_window_icon
from app.utils.logging_config import setup_logging
from app.utils.paths import get_assets_dir

logger = logging.getLogger(__name__)


def _set_windows_app_user_model_id() -> None:
    """Register explicit Windows AppUserModelID so Taskbar displays the Colibri AI Studio logo."""
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                f"{APP_ORGANIZATION}.ColibriAIStudio.{APP_VERSION}"
            )
        except Exception:
            pass


def run_gui_application(smoke_test: bool = False) -> int:
    """Initialize logging, QApplication, Liquid Glass theme, Brand Icon, ApplicationState, and MainWindow."""
    setup_logging()
    _set_windows_app_user_model_id()
    logger.info("Starting %s v%s (smoke_test=%s)", APP_NAME, APP_VERSION, smoke_test)

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_ORGANIZATION)
    app.setApplicationVersion(APP_VERSION)

    app_icon = build_colibri_window_icon()
    icon_path = get_assets_dir() / "icons" / "app_icon.ico"
    if icon_path.exists() and app_icon.isNull():
        app_icon = QIcon(str(icon_path))
    app.setWindowIcon(app_icon)

    app_state = ApplicationState()
    if smoke_test:
        app_state.settings_service.update(first_run_completed=True)

    apply_theme_to_app(
        app_state.settings.theme,
        scale_percent=app_state.settings.ui_scale_percent,
    )

    window = MainWindow(app_state=app_state)
    window.setWindowIcon(app_icon)
    window.show()

    if smoke_test:
        def _finish_smoke() -> None:
            logger.info("Smoke test verified all views, logo widgets, and themes cleanly; closing window.")
            for t_key in ("obsidian_glass", "arctic_aurora", "amethyst_nebula", "emerald_matrix", "alabaster_daylight"):
                window.apply_and_persist_theme(t_key)
            window.apply_and_persist_theme("obsidian_glass")
            for view_key in ("chat", "model_hub", "my_models", "hardware", "performance", "settings"):
                window.switch_view(view_key)
            window.close()
            app.quit()

        QTimer.singleShot(450, _finish_smoke)

    return int(app.exec())
