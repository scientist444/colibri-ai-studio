"""Diagnostics & Update Services."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.constants import APP_NAME, APP_VERSION
from app.core.backend_adapter import ColibriBackendAdapter
from app.models.hardware_models import SystemHardwareProfile
from app.models.settings_models import AppSettings
from app.services.installation_service import InstallationService
from app.utils.logging_config import get_recent_logs, redact_sensitive_text


class DiagnosticsService:
    """Generates redacted diagnostic bundles and runs Colibri doctor checks."""

    def __init__(self, adapter: ColibriBackendAdapter) -> None:
        self.adapter = adapter

    def build_diagnostic_report(
        self,
        hardware: SystemHardwareProfile,
        settings: AppSettings,
        active_model_path: str = "",
    ) -> dict[str, Any]:
        engine_info = self.adapter.detect_installed_engine_binaries()
        doctor_res = {}
        if active_model_path and Path(active_model_path).exists():
            doctor_res = self.adapter.run_doctor(model_dir=active_model_path)

        sanitized_settings = settings.model_dump()
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "application": {"name": APP_NAME, "version": APP_VERSION},
            "engine": engine_info,
            "doctor": doctor_res,
            "hardware": hardware.model_dump(),
            "settings": sanitized_settings,
            "recent_logs": get_recent_logs(max_lines=250).splitlines(),
        }

    def export_diagnostic_bundle(
        self,
        output_path: Path,
        hardware: SystemHardwareProfile,
        settings: AppSettings,
        active_model_path: str = "",
    ) -> Path:
        report = self.build_diagnostic_report(hardware, settings, active_model_path)
        raw_json = json.dumps(report, indent=2)
        redacted_json = redact_sensitive_text(raw_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(redacted_json, encoding="utf-8")
        return output_path


class UpdateService:
    """Checks for newer Colibri engine releases on GitHub."""

    def __init__(self, adapter: ColibriBackendAdapter, installer: InstallationService) -> None:
        self.adapter = adapter
        self.installer = installer

    def check_for_updates(self) -> dict[str, Any]:
        installed_ver = self.adapter.get_version()
        try:
            latest = self.installer.fetch_latest_windows_release_info()
            latest_tag = str(latest.get("tag_name") or "").lstrip("v")
            has_update = bool(latest_tag and latest_tag != installed_ver)
            return {
                "installed_version": installed_ver,
                "latest_version": latest_tag or installed_ver,
                "update_available": has_update,
                "release_info": latest,
            }
        except Exception as exc:
            return {
                "installed_version": installed_ver,
                "latest_version": installed_ver,
                "update_available": False,
                "error": str(exc),
            }
