"""Settings persistence and Windows Credential Manager integration."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import keyring

from app.constants import (
    KEYRING_HF_TOKEN_ACCOUNT,
    KEYRING_LOCAL_API_KEY_ACCOUNT,
    KEYRING_SERVICE_NAME,
)
from app.models.settings_models import AppSettings
from app.utils.paths import get_settings_file_path

logger = logging.getLogger(__name__)


class SettingsService:
    """Loads, validates, and saves user settings and secure credentials."""

    def __init__(self, settings_path: Path | None = None) -> None:
        self.settings_path: Path = settings_path or get_settings_file_path()
        self._settings: AppSettings = self.load()

    @property
    def current(self) -> AppSettings:
        return self._settings

    def load(self) -> AppSettings:
        """Load and validate settings from disk, falling back to safe defaults."""
        if self.settings_path.exists():
            try:
                raw = json.loads(self.settings_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    self._settings = AppSettings.model_validate(raw)
                    return self._settings
            except Exception as exc:
                logger.warning("Corrupted or outdated settings.json, resetting to defaults: %s", exc)
        self._settings = AppSettings()
        self.save()
        return self._settings

    def save(self, updated: AppSettings | None = None) -> AppSettings:
        """Persist validated settings to `settings.json`."""
        if updated is not None:
            self._settings = AppSettings.model_validate(updated.model_dump())
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings_path.write_text(
            json.dumps(self._settings.model_dump(), indent=2),
            encoding="utf-8",
        )
        return self._settings

    def update(self, **changes: Any) -> AppSettings:
        """Update specific setting fields and persist."""
        merged = self._settings.model_dump()
        merged.update(changes)
        self._settings = AppSettings.model_validate(merged)
        return self.save()

    # --- Secure Credential Storage (Windows Credential Manager via keyring) ---

    @staticmethod
    def get_huggingface_token() -> str | None:
        try:
            tok = keyring.get_password(KEYRING_SERVICE_NAME, KEYRING_HF_TOKEN_ACCOUNT)
            return tok.strip() if tok else None
        except Exception as exc:
            logger.debug("Keyring read skipped: %s", exc)
            return None

    @staticmethod
    def set_huggingface_token(token: str | None) -> bool:
        try:
            if token and token.strip():
                keyring.set_password(KEYRING_SERVICE_NAME, KEYRING_HF_TOKEN_ACCOUNT, token.strip())
            else:
                try:
                    keyring.delete_password(KEYRING_SERVICE_NAME, KEYRING_HF_TOKEN_ACCOUNT)
                except Exception:
                    pass
            return True
        except Exception as exc:
            logger.error("Failed storing Hugging Face token in Credential Manager: %s", exc)
            return False

    @staticmethod
    def get_local_api_key() -> str | None:
        try:
            key = keyring.get_password(KEYRING_SERVICE_NAME, KEYRING_LOCAL_API_KEY_ACCOUNT)
            return key.strip() if key else None
        except Exception:
            return None

    @staticmethod
    def set_local_api_key(api_key: str | None) -> bool:
        try:
            if api_key and api_key.strip():
                keyring.set_password(KEYRING_SERVICE_NAME, KEYRING_LOCAL_API_KEY_ACCOUNT, api_key.strip())
            else:
                try:
                    keyring.delete_password(KEYRING_SERVICE_NAME, KEYRING_LOCAL_API_KEY_ACCOUNT)
                except Exception:
                    pass
            return True
        except Exception as exc:
            logger.error("Failed storing local API key in Credential Manager: %s", exc)
            return False
