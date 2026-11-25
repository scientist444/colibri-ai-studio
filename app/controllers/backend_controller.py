"""Backend Controller for starting/stopping Colibri server and installing engine releases."""

from __future__ import annotations

from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal

from app.application_state import ApplicationState
from app.core.colibri_manager import BackendState
from app.services.settings_service import SettingsService
from app.utils.threading_utils import run_in_background


class BackendController(QObject):
    """Coordinates non-blocking Colibri server startup, shutdown, and installation."""

    install_progress = pyqtSignal(str, float)   # (status_text, percent)
    install_finished = pyqtSignal(bool, str)    # (success, message)
    server_action_finished = pyqtSignal(bool, str)

    def __init__(self, app_state: ApplicationState) -> None:
        super().__init__()
        self.app_state = app_state

    def install_colibri_engine_async(self, include_cuda: bool = False) -> None:
        self.app_state.process_manager._set_state(
            BackendState.INSTALLING, "Downloading official Colibri Windows engine..."
        )

        def _worker() -> dict[str, object]:
            return self.app_state.installation_service.install_colibri_release(
                include_cuda=include_cuda,
                on_progress=lambda msg, pct: self.install_progress.emit(msg, pct),
            )

        def _on_result(info: dict[str, object]) -> None:
            self.app_state.process_manager.refresh_installation_state()
            ver = info.get("version", "")
            bins = info.get("native_binaries", [])
            self.install_finished.emit(
                True,
                f"Colibri {ver} installed successfully ({len(bins)} native engines ready).",  # type: ignore[arg-type]
            )

        def _on_error(err: str, _tb: str) -> None:
            self.app_state.process_manager.refresh_installation_state()
            self.install_finished.emit(False, err)

        run_in_background(_worker, on_result=_on_result, on_error=_on_error)

    def start_model_async(self, model_id: str, model_path: Path | str) -> None:
        self.app_state.update_settings(
            active_model_id=model_id,
            active_model_path=str(model_path),
        )
        self.app_state.active_model_changed.emit(model_id, str(model_path))
        api_key = SettingsService.get_local_api_key()

        def _worker() -> tuple[bool, str]:
            return self.app_state.process_manager.start_server(
                model_id=model_id,
                model_path=model_path,
                settings=self.app_state.settings,
                api_key=api_key,
            )

        def _on_result(res: tuple[bool, str]) -> None:
            ok, msg = res
            self.server_action_finished.emit(ok, msg)

        def _on_error(err: str, _tb: str) -> None:
            self.server_action_finished.emit(False, err)

        run_in_background(_worker, on_result=_on_result, on_error=_on_error)

    def stop_server_async(self) -> None:
        def _worker() -> None:
            self.app_state.process_manager.stop_server()

        run_in_background(
            _worker,
            on_result=lambda _: self.server_action_finished.emit(True, "Server stopped."),
        )
