"""Re-export UpdateService for clean module imports."""

from __future__ import annotations

from app.services.diagnostics_service import UpdateService

__all__ = ["UpdateService"]
