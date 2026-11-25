"""Rich Liquid Glass Model Hub Card & Pre-Download Confirmation Dialog (Emoji-Free)."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.models.model_metadata import ModelCandidate, SupportTier
from app.ui.liquid_glass import MONO_FONT_FAMILY, LiquidGlassDialog, LiquidGlassPanel
from app.ui.widgets.status_badge import StatusBadge


class PreDownloadConfirmDialog(LiquidGlassDialog):
    """Liquid Glass confirmation dialog shown before downloading large multi-GB models."""

    def __init__(
        self,
        candidate: ModelCandidate,
        target_dir: str,
        free_space_gb: float,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent=parent, title="Confirm Model Download")
        self.setMinimumWidth(540)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)

        header = QLabel(f"Confirm Download: {candidate.display_name}")
        header.setStyleSheet("font-size: 18px; font-weight: 700;")
        layout.addWidget(header)

        info_panel = LiquidGlassPanel(self, radius=12.0)
        info_layout = QVBoxLayout(info_panel)
        info_layout.setContentsMargins(14, 12, 14, 12)
        info_layout.setSpacing(6)

        details = [
            f"<b>Hugging Face Repository:</b> <code>{candidate.hf_repo}</code>",
            f"<b>Download Size:</b> {candidate.download_size_gb:.1f} GB "
            f"(Required Disk Space: {candidate.compatibility.estimated_disk_required_gb:.1f} GB)",
            f"<b>Target Directory:</b> <code>{target_dir}</code> ({free_space_gb:.1f} GB available)",
            f"<b>Estimated RAM Required:</b> {candidate.ram_min_gb:.1f} GB minimum / {candidate.ram_good_gb:.1f} GB recommended",
            f"<b>Expected Execution Mode:</b> {candidate.compatibility.expected_mode}",
            f"<b>Compatibility Assessment:</b> {candidate.compatibility.badge_label}",
        ]
        if candidate.compatibility.requires_gguf_import:
            details.append("<b>Conversion:</b> Automatic <code>coli import</code> GGUF conversion after download")

        for line in details:
            lbl = QLabel(line)
            lbl.setWordWrap(True)
            lbl.setTextFormat(Qt.TextFormat.RichText)
            lbl.setStyleSheet("font-size: 12.5px;")
            info_layout.addWidget(lbl)

        layout.addWidget(info_panel)

        if candidate.compatibility.warnings:
            warn_lbl = QLabel("Notice: " + " | ".join(candidate.compatibility.warnings))
            warn_lbl.setWordWrap(True)
            warn_lbl.setStyleSheet("font-size: 12px; color: #FBBF24; font-weight: 600;")
            layout.addWidget(warn_lbl)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        confirm_btn = QPushButton(f"Start Download ({candidate.download_size_gb:.1f} GB)")
        confirm_btn.setObjectName("primaryGlassButton")
        confirm_btn.clicked.connect(self.accept)
        btn_row.addWidget(confirm_btn)
        layout.addLayout(btn_row)


class ModelHubCard(LiquidGlassPanel):
    """Rich Liquid Glass card displaying all 16 required Model Hub metadata fields."""

    download_requested = pyqtSignal(object)  # ModelCandidate
    launch_requested = pyqtSignal(object)    # ModelCandidate

    def __init__(self, candidate: ModelCandidate, parent: QWidget | None = None) -> None:
        super().__init__(parent=parent, radius=16.0)
        self.candidate = candidate
        self._build_ui()

    def _build_ui(self) -> None:
        c = self.candidate
        comp = c.compatibility

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # Row 1: Title, Repository, Support Tier badge, Compatibility badge
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        title = QLabel(c.display_name)
        title.setStyleSheet("font-size: 16px; font-weight: 700; letter-spacing: 0.2px;")
        top_row.addWidget(title)

        repo_lbl = QLabel(f"[{c.hf_repo}]")
        repo_lbl.setStyleSheet(f"font-family: {MONO_FONT_FAMILY}; font-size: 11.5px; color: #38BDF8;")
        top_row.addWidget(repo_lbl)

        top_row.addStretch(1)

        tier_text = {
            SupportTier.OFFICIAL_CATALOG: "OFFICIAL CATALOG",
            SupportTier.VALIDATED_GGUF: "VALIDATED GGUF",
            SupportTier.POTENTIALLY_COMPATIBLE: "VERIFY ARCHITECTURE",
            SupportTier.UNSUPPORTED: "UNSUPPORTED",
        }.get(c.support_tier, "CATALOG")
        tier_badge = StatusBadge(
            tier_text,
            variant="info" if c.support_tier == SupportTier.OFFICIAL_CATALOG else "yellow",
        )
        top_row.addWidget(tier_badge)

        comp_badge = StatusBadge.from_compatibility(comp.badge, comp.badge_label)
        top_row.addWidget(comp_badge)
        layout.addLayout(top_row)

        # Row 2: Description
        if c.description:
            desc_lbl = QLabel(c.description)
            desc_lbl.setWordWrap(True)
            desc_lbl.setStyleSheet("font-size: 12.5px; color: #94A3B8;")
            layout.addWidget(desc_lbl)

        # Row 3: 16-Field Metadata Grid
        meta_grid = QGridLayout()
        meta_grid.setHorizontalSpacing(18)
        meta_grid.setVerticalSpacing(5)

        fields = [
            ("Family / Arch", f"{c.family} ({c.architecture})"),
            ("Parameters", f"{c.parameter_count}  |  {c.active_parameters}"),
            ("Quantization", c.quantization),
            ("Download / Disk", f"{c.download_size_gb:.1f} GB  /  {comp.estimated_disk_required_gb:.1f} GB"),
            ("RAM Required", f"{c.ram_min_gb:.1f} GB min  |  {c.ram_good_gb:.1f} GB ideal"),
            ("Est. VRAM Cache", f"{comp.estimated_vram_used_gb:.1f} GB ({comp.recommended_backend.upper()})"),
            ("Execution Mode", comp.expected_mode),
            ("Speed Tier", comp.speed_tier),
            ("License / Access", f"{c.license_name} ({'Gated Token Required' if c.is_gated else 'Open Access'})"),
            (
                "Conversion",
                "Requires `coli import`" if comp.requires_gguf_import else "Native Colibri Ready",
            ),
        ]

        for idx, (k, v) in enumerate(fields):
            row = idx // 2
            col = (idx % 2) * 2
            k_lbl = QLabel(f"{k}:")
            k_lbl.setStyleSheet("font-size: 11px; color: #94A3B8; font-weight: 600;")
            v_lbl = QLabel(v)
            v_lbl.setStyleSheet("font-size: 12px; font-weight: 600;")
            meta_grid.addWidget(k_lbl, row, col)
            meta_grid.addWidget(v_lbl, row, col + 1)

        layout.addLayout(meta_grid)

        # Row 4: Compatibility explanation + Action Button
        bottom_row = QHBoxLayout()
        reasons_text = "  |  ".join(comp.reasons + comp.warnings)
        reason_lbl = QLabel(reasons_text)
        reason_lbl.setWordWrap(True)
        reason_lbl.setStyleSheet(
            "font-size: 11.5px; color: #34D399; font-weight: 500;"
            if comp.badge.value == "green"
            else "font-size: 11.5px; color: #FBBF24; font-weight: 500;"
        )
        bottom_row.addWidget(reason_lbl, 1)

        if c.is_installed:
            launch_btn = QPushButton("Load & Chat")
            launch_btn.setObjectName("primaryGlassButton")
            launch_btn.setEnabled(comp.can_execute)
            launch_btn.clicked.connect(lambda: self.launch_requested.emit(self.candidate))
            bottom_row.addWidget(launch_btn)
        else:
            dl_btn = QPushButton(f"Download ({c.download_size_gb:.1f} GB)")
            dl_btn.setObjectName("primaryGlassButton")
            dl_btn.setEnabled(comp.can_download and comp.architecture_supported)
            if not comp.can_download:
                dl_btn.setToolTip("Insufficient disk space on target volume.")
            dl_btn.clicked.connect(lambda: self.download_requested.emit(self.candidate))
            bottom_row.addWidget(dl_btn)

        layout.addLayout(bottom_row)
