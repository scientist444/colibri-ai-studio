"""Liquid Glass status and compatibility badges (emoji-free, high-clarity typography)."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QWidget

from app.models.model_metadata import CompatibilityBadge


class StatusBadge(QLabel):
    """Translucent Liquid Glass pill badge for compatibility and server states."""

    def __init__(
        self,
        text: str = "READY",
        variant: str = "info",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_variant(variant, text)

    def set_variant(self, variant: str, text: str | None = None) -> None:
        if text is not None:
            self.setText(text)
        v = variant.lower()
        if v in ("green", "success", "running"):
            bg = "rgba(16, 185, 129, 0.22)"
            border = "rgba(52, 211, 153, 0.55)"
            fg = "#34D399"
        elif v in ("yellow", "warning", "starting"):
            bg = "rgba(245, 158, 11, 0.22)"
            border = "rgba(251, 191, 36, 0.55)"
            fg = "#FBBF24"
        elif v in ("red", "error", "failed"):
            bg = "rgba(239, 68, 68, 0.22)"
            border = "rgba(248, 113, 113, 0.55)"
            fg = "#F87171"
        else:
            bg = "rgba(14, 165, 233, 0.20)"
            border = "rgba(125, 211, 252, 0.50)"
            fg = "#38BDF8"

        self.setStyleSheet(
            f"""
            QLabel {{
                background-color: {bg};
                border: 1px solid {border};
                color: {fg};
                border-radius: 9px;
                padding: 3px 10px;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0.35px;
            }}
            """
        )

    @classmethod
    def from_compatibility(
        cls,
        badge: CompatibilityBadge,
        label: str,
        parent: QWidget | None = None,
    ) -> StatusBadge:
        if badge == CompatibilityBadge.GREEN:
            return cls(f"[RECOMMENDED]  {label}", variant="green", parent=parent)
        if badge == CompatibilityBadge.YELLOW:
            return cls(f"[STREAMING]  {label}", variant="yellow", parent=parent)
        return cls(f"[INCOMPATIBLE]  {label}", variant="red", parent=parent)
