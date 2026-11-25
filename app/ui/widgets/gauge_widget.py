"""Liquid Glass Telemetry Gauges & 3-Tier Placement Diagram (`GPU VRAM -> System RAM -> NVMe`)."""

from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from app.models.hardware_models import TierPlacementSummary
from app.ui.liquid_glass import MONO_FONT_FAMILY, LiquidGlassPanel, get_active_theme


class TelemetryGaugeCard(LiquidGlassPanel):
    """Liquid Glass card displaying a live resource metric (CPU, RAM, GPU, VRAM, or Storage)."""

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent=parent, radius=15.0)
        self.setMinimumHeight(125)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        top_row = QHBoxLayout()
        self.title_lbl = QLabel(title.upper())
        self.title_lbl.setStyleSheet(
            "font-size: 11px; font-weight: 700; letter-spacing: 0.6px; color: #38BDF8;"
        )
        top_row.addWidget(self.title_lbl)
        top_row.addStretch(1)

        self.value_lbl = QLabel("0%")
        self.value_lbl.setStyleSheet(
            f"font-family: {MONO_FONT_FAMILY}; font-size: 17px; font-weight: 700;"
        )
        top_row.addWidget(self.value_lbl)
        layout.addLayout(top_row)

        self.subtitle_lbl = QLabel(subtitle)
        self.subtitle_lbl.setWordWrap(True)
        self.subtitle_lbl.setStyleSheet("font-size: 12.5px; font-weight: 600;")
        layout.addWidget(self.subtitle_lbl)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(10)
        layout.addWidget(self.progress)

        self.detail_lbl = QLabel("")
        self.detail_lbl.setWordWrap(True)
        self.detail_lbl.setStyleSheet("font-size: 11px; color: #94A3B8;")
        layout.addWidget(self.detail_lbl)

    def update_metric(
        self,
        percent: float | None,
        value_text: str,
        subtitle: str,
        detail: str,
    ) -> None:
        self.value_lbl.setText(value_text)
        self.subtitle_lbl.setText(subtitle)
        self.detail_lbl.setText(detail)
        if percent is None:
            self.progress.setValue(0)
        else:
            self.progress.setValue(max(0, min(100, int(round(percent)))))


class ThreeTierPlacementDiagram(LiquidGlassPanel):
    """Visual 3-Tier Colibri Architecture Diagram: Tier 1 GPU VRAM -> Tier 2 System RAM -> Tier 3 NVMe SSD."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent=parent, radius=16.0, elevated=True)
        self._summary = TierPlacementSummary()
        self.setMinimumHeight(210)

    def set_summary(self, summary: TierPlacementSummary) -> None:
        self._summary = summary
        self.update()

    def paintEvent(self, event: object) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = QRectF(self.rect()).adjusted(18.0, 16.0, -18.0, -16.0)
        s = self._summary
        t = get_active_theme()
        fg_primary = QColor(t["text_primary"])
        fg_secondary = QColor(t["text_secondary"])
        fg_muted = QColor(t["text_muted"])

        title_font = QFont("Segoe UI Variable Text", 11, QFont.Weight.Bold)
        painter.setFont(title_font)
        painter.setPen(fg_primary)
        header_text = (
            f"3-TIER HIERARCHICAL MOE PLACEMENT  |  {s.source_label.upper()}  "
            f"(Retention: {s.expert_retention_ratio * 100:.0f}%  |  Threads: {s.thread_count}  |  Context: {s.ctx_tokens})"
        )
        painter.drawText(QRectF(rect.left(), rect.top(), rect.width(), 26.0), Qt.AlignmentFlag.AlignLeft, header_text)

        top_y = rect.top() + 38.0
        box_h = max(115.0, rect.height() - 48.0)
        gap = 42.0
        box_w = (rect.width() - (2 * gap)) / 3.0

        tiers = [
            (
                "TIER 1: GPU VRAM (HOT CACHE)",
                f"Mode: {s.gpu_mode.upper()}",
                f"Expert Cache: {s.vram_expert_cache_gb:.1f} GB ({s.vram_slots} slots)",
                "Zero-latency device compute",
                QColor(14, 165, 233),
            ),
            (
                "TIER 2: SYSTEM RAM (WARM RESIDENT)",
                f"Dense + Shared: {s.dense_gb:.1f} GB  |  KV: {s.kv_cache_gb:.1f} GB",
                f"Expert Cache: {s.ram_expert_cache_gb:.1f} GB ({s.ram_slots} slots)",
                "Pinned DDR4/DDR5 expert pool",
                QColor(99, 102, 241),
            ),
            (
                "TIER 3: NVME SSD (COLD STREAMING)",
                f"Streaming Pool: {s.nvme_streaming_gb:.1f} GB",
                "Direct I/O on-demand expert paging",
                "Async prefetch + LRU promotion",
                QColor(16, 185, 129),
            ),
        ]

        for idx, (t_title, line1, line2, line3, accent) in enumerate(tiers):
            bx = rect.left() + idx * (box_w + gap)
            box_rect = QRectF(bx, top_y, box_w, box_h)

            path = QPainterPath()
            path.addRoundedRect(box_rect, 13.0, 13.0)

            grad = QLinearGradient(box_rect.topLeft(), box_rect.bottomLeft())
            grad.setColorAt(0.0, QColor(accent.red(), accent.green(), accent.blue(), 48))
            grad.setColorAt(1.0, QColor(*t["panel_bot"]))
            painter.fillPath(path, grad)

            pen = QPen(QColor(accent.red(), accent.green(), accent.blue(), 155), 1.4)
            painter.setPen(pen)
            painter.drawPath(path)

            inner = box_rect.adjusted(12.0, 10.0, -12.0, -10.0)
            painter.setFont(QFont("Segoe UI Variable Text", 9, QFont.Weight.Bold))
            painter.setPen(fg_primary)
            painter.drawText(QRectF(inner.left(), inner.top(), inner.width(), 20.0), Qt.AlignmentFlag.AlignLeft, t_title)

            painter.setFont(QFont("Cascadia Code", 9, QFont.Weight.DemiBold))
            painter.setPen(accent)
            painter.drawText(QRectF(inner.left(), inner.top() + 26.0, inner.width(), 20.0), Qt.AlignmentFlag.AlignLeft, line1)

            painter.setPen(fg_secondary)
            painter.drawText(QRectF(inner.left(), inner.top() + 48.0, inner.width(), 20.0), Qt.AlignmentFlag.AlignLeft, line2)

            painter.setFont(QFont("Segoe UI Variable Text", 8))
            painter.setPen(fg_muted)
            painter.drawText(QRectF(inner.left(), inner.top() + 72.0, inner.width(), 20.0), Qt.AlignmentFlag.AlignLeft, line3)

            if idx < 2:
                arrow_x = box_rect.right() + 6.0
                arrow_y = box_rect.center().y()
                painter.setPen(QPen(accent, 1.8))
                painter.drawLine(int(arrow_x), int(arrow_y), int(arrow_x + gap - 12.0), int(arrow_y))
                painter.setFont(QFont("Cascadia Code", 9, QFont.Weight.Bold))
                painter.drawText(
                    QRectF(box_rect.right(), arrow_y - 22.0, gap, 20.0),
                    Qt.AlignmentFlag.AlignCenter,
                    "<->",
                )

        painter.end()
