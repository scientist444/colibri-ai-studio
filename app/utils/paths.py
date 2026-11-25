"""Application path resolution for source and frozen (PyInstaller) runs."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from app.constants import APP_SLUG


def is_frozen() -> bool:
    """Return True if running inside a PyInstaller frozen executable."""
    return bool(getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"))


def get_bundle_root() -> Path:
    """Return the root directory of bundled static assets."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parent.parent.parent


def get_assets_dir() -> Path:
    """Return the path to the `assets/` directory."""
    return get_bundle_root() / "assets"


def get_bundled_colibri_runtime_dir() -> Path:
    """Return the path to bundled official Colibri Python control-plane scripts."""
    return get_assets_dir() / "colibri_runtime"


def get_app_data_dir() -> Path:
    """Return `%LOCALAPPDATA%\\ColibriAIStudio` (or override via COLIBRI_STUDIO_DATA_DIR)."""
    override = os.environ.get("COLIBRI_STUDIO_DATA_DIR")
    if override:
        base = Path(override).expanduser().resolve()
    else:
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            base = Path(local_app_data) / APP_SLUG
        else:
            base = Path.home() / f".{APP_SLUG.lower()}"
    base.mkdir(parents=True, exist_ok=True)
    return base


def get_logs_dir() -> Path:
    """Return the application log directory."""
    logs_dir = get_app_data_dir() / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def get_database_path() -> Path:
    """Return the SQLite database file path."""
    return get_app_data_dir() / "colibri_studio.db"


def get_default_engine_dir() -> Path:
    """Return the default managed Colibri engine directory."""
    engine_dir = get_app_data_dir() / "engine"
    engine_dir.mkdir(parents=True, exist_ok=True)
    return engine_dir


def get_default_models_dir() -> Path:
    """Return the default model storage directory."""
    models_dir = get_app_data_dir() / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    return models_dir


def get_settings_file_path() -> Path:
    """Return the path to the JSON settings file."""
    return get_app_data_dir() / "settings.json"
