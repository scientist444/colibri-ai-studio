"""Model Controller for searching Hugging Face, downloading, and importing GGUF models."""

from __future__ import annotations

from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal

from app.application_state import ApplicationState
from app.core.error_handler import classify_exception
from app.models.model_metadata import InstalledModelRecord, ModelCandidate
from app.utils.threading_utils import run_in_background


class ModelController(QObject):
    """Coordinates model discovery, downloads, and local GGUF imports."""

    hf_search_started = pyqtSignal()
    hf_search_results = pyqtSignal(list)          # list[ModelCandidate]
    hf_search_error = pyqtSignal(str, str)        # (title, body)
    gguf_import_finished = pyqtSignal(bool, str)  # (success, message)

    def __init__(self, app_state: ApplicationState) -> None:
        super().__init__()
        self.app_state = app_state

    def search_huggingface_async(self, query: str) -> None:
        if self.app_state.settings.offline_mode:
            self.hf_search_error.emit(
                "Offline Mode Enabled",
                "Disable Offline Mode in Settings → Privacy & Security to search Hugging Face.",
            )
            return

        self.hf_search_started.emit()
        installed = self.app_state.models_repo.list_models()
        models_dir = self.app_state.settings.models_dir
        hw = self.app_state.hardware

        def _worker() -> list[ModelCandidate]:
            return self.app_state.model_fetcher.search_huggingface(
                query=query,
                hardware=hw,
                installed_records=installed,
                target_models_dir=models_dir,
            )

        def _on_error(err: str, _tb: str) -> None:
            friendly = classify_exception(err, context="Hugging Face Search")
            self.hf_search_error.emit(
                friendly.title,
                f"{friendly.summary}\n\n{friendly.recovery_guidance}",
            )

        run_in_background(_worker, on_result=self.hf_search_results.emit, on_error=_on_error)

    def import_gguf_async(self, gguf_path: Path | str, copy_mode: str = "link") -> None:
        models_dir = self.app_state.settings.models_dir

        def _worker() -> tuple[bool, str, InstalledModelRecord | None]:
            return self.app_state.model_registry.import_local_gguf_file(
                gguf_file=gguf_path,
                models_dir=models_dir,
                copy_mode=copy_mode,
            )

        def _on_result(res: tuple[bool, str, InstalledModelRecord | None]) -> None:
            ok, msg, _rec = res
            if ok:
                self.app_state.refresh_installed_models()
            self.gguf_import_finished.emit(ok, msg)

        def _on_error(err: str, _tb: str) -> None:
            self.gguf_import_finished.emit(False, err)

        run_in_background(_worker, on_result=_on_result, on_error=_on_error)
