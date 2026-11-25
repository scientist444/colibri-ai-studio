"""Centralized reactive Application State container."""

from __future__ import annotations

from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal

from app.core.backend_adapter import ColibriBackendAdapter
from app.core.colibri_manager import ColibriProcessManager
from app.core.download_manager import DownloadManager
from app.core.model_fetcher import ModelFetcher
from app.core.performance_optimizer import PerformanceOptimizer
from app.core.system_check import HardwareProfiler
from app.database.database import DatabaseManager
from app.database.repositories import (
    BenchmarkRepository,
    ConversationRepository,
    DownloadTasksRepository,
    InstalledModelsRepository,
)
from app.models.hardware_models import SystemHardwareProfile
from app.models.model_metadata import InstalledModelRecord, ModelCandidate
from app.models.settings_models import AppSettings
from app.services.conversation_service import ConversationService
from app.services.diagnostics_service import DiagnosticsService, UpdateService
from app.services.installation_service import InstallationService
from app.services.model_registry import ModelRegistryService
from app.services.settings_service import SettingsService


class ApplicationState(QObject):
    """Owns shared services, repositories, and top-level reactive Qt signals."""

    hardware_updated = pyqtSignal(object)          # SystemHardwareProfile
    settings_changed = pyqtSignal(object)          # AppSettings
    catalog_updated = pyqtSignal(list)             # list[ModelCandidate]
    installed_models_changed = pyqtSignal(list)    # list[InstalledModelRecord]
    active_model_changed = pyqtSignal(str, str)    # (model_id, model_path)
    navigation_requested = pyqtSignal(str)         # view_key

    def __init__(
        self,
        db_path: Path | None = None,
        settings_path: Path | None = None,
    ) -> None:
        super().__init__()
        self.settings_service = SettingsService(settings_path=settings_path)
        self.db = DatabaseManager(db_path=db_path)

        # Repositories
        self.conversations_repo = ConversationRepository(self.db)
        self.models_repo = InstalledModelsRepository(self.db)
        self.downloads_repo = DownloadTasksRepository(self.db)
        self.benchmarks_repo = BenchmarkRepository(self.db)

        # Core Services & Adapters
        self.hardware_profiler = HardwareProfiler()
        self.hardware: SystemHardwareProfile = self.hardware_profiler.scan_system(
            workload_profile=self.settings.workload_profile,
            safety_reserve_gb=self.settings.system_ram_reserve_gb,
            custom_ram_budget_gb=self.settings.custom_ram_budget_gb,
            vram_headroom_gb=self.settings.vram_headroom_gb,
        )

        self.adapter = ColibriBackendAdapter(engine_dir=self.settings.engine_dir)
        self.process_manager = ColibriProcessManager(self.adapter)
        self.installation_service = InstallationService(self.adapter)
        self.model_registry = ModelRegistryService(self.models_repo, self.adapter)
        self.conversation_service = ConversationService(self.conversations_repo)
        self.diagnostics_service = DiagnosticsService(self.adapter)
        self.update_service = UpdateService(self.adapter, self.installation_service)
        self.performance_optimizer = PerformanceOptimizer(self.adapter, self.benchmarks_repo)

        self.download_manager = DownloadManager(
            tasks_repo=self.downloads_repo,
            models_repo=self.models_repo,
            hf_token_provider=SettingsService.get_huggingface_token,
            gguf_importer=lambda src, dst: self.adapter.import_gguf(src, dst, mode="link"),
        )
        self.download_manager.task_completed.connect(self._on_download_completed)

        self.model_fetcher = ModelFetcher(hf_token=SettingsService.get_huggingface_token())
        self.catalog_candidates: list[ModelCandidate] = []
        self.refresh_installed_models()
        self.refresh_catalog()

    @property
    def settings(self) -> AppSettings:
        return self.settings_service.current

    def update_settings(self, **kwargs: object) -> AppSettings:
        updated = self.settings_service.update(**kwargs)
        self.model_fetcher.hf_token = SettingsService.get_huggingface_token()
        self.hardware = self.hardware_profiler.scan_system(
            workload_profile=updated.workload_profile,
            safety_reserve_gb=updated.system_ram_reserve_gb,
            custom_ram_budget_gb=updated.custom_ram_budget_gb,
            vram_headroom_gb=updated.vram_headroom_gb,
        )
        self.settings_changed.emit(updated)
        self.hardware_updated.emit(self.hardware)
        self.refresh_catalog()
        return updated

    def refresh_installed_models(self) -> list[InstalledModelRecord]:
        models = self.model_registry.scan_and_sync_models_dir(self.settings.models_dir)
        self.installed_models_changed.emit(models)
        return models

    def refresh_catalog(self) -> list[ModelCandidate]:
        installed = self.models_repo.list_models()
        self.catalog_candidates = self.model_fetcher.load_official_catalog(
            hardware=self.hardware,
            installed_records=installed,
            target_models_dir=self.settings.models_dir,
        )
        self.catalog_updated.emit(self.catalog_candidates)
        return self.catalog_candidates

    def _on_download_completed(self, _record: InstalledModelRecord) -> None:
        self.refresh_installed_models()
        self.refresh_catalog()
