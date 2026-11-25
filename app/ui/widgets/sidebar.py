"""Collapsible Liquid Glass Left Navigation Sidebar with Live Theme Switcher."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.liquid_glass import LIQUID_GLASS_THEMES, LiquidGlassPanel, get_active_theme
from app.ui.widgets.brand_logo import ColibriLogoWidget
from app.ui.widgets.status_badge import StatusBadge

NAV_ITEMS: list[tuple[str, str, str]] = [
    ("chat", "01", "Chat Workspace"),
    ("model_hub", "02", "Model Hub"),
    ("my_models", "03", "My Models"),
    ("hardware", "04", "Hardware Monitor"),
    ("performance", "05", "Performance Lab"),
    ("settings", "06", "Settings"),
]


class NavigationSidebar(LiquidGlassPanel):
    """Collapsible Liquid Glass sidebar with 6 primary views, live theme selector, and backend status."""

    view_selected = pyqtSignal(str)
    wizard_requested = pyqtSignal()
    theme_selected = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent=parent, radius=18.0, elevated=True)
        self._collapsed = False
        self._active_key = "chat"
        self._buttons: dict[str, QPushButton] = {}

        self.setFixedWidth(244)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 14, 12, 14)
        layout.setSpacing(8)

        # Brand Header + Collapse Toggle
        header_row = QHBoxLayout()
        header_row.setSpacing(10)

        self.logo_widget = ColibriLogoWidget(self, size=40, draw_medallion=True)
        header_row.addWidget(self.logo_widget)

        brand_col = QVBoxLayout()
        brand_col.setContentsMargins(0, 0, 0, 0)
        brand_col.setSpacing(1)
        self.title_label = QLabel("COLIBRI STUDIO")
        self.title_label.setStyleSheet(
            "font-size: 13.5px; font-weight: 800; letter-spacing: 0.9px;"
        )
        self.brand_sub_label = QLabel("LOCAL AI WORKSTATION")
        self.brand_sub_label.setStyleSheet(
            "font-size: 9.5px; font-weight: 700; letter-spacing: 0.7px; color: #38BDF8;"
        )
        brand_col.addWidget(self.title_label)
        brand_col.addWidget(self.brand_sub_label)
        header_row.addLayout(brand_col, 1)

        self.collapse_btn = QPushButton("<<")
        self.collapse_btn.setFixedSize(26, 26)
        self.collapse_btn.setToolTip("Collapse / Expand Navigation")
        self.collapse_btn.setStyleSheet("padding: 2px; font-size: 10.5px; font-weight: 700; border-radius: 8px;")
        self.collapse_btn.clicked.connect(self.toggle_collapsed)
        header_row.addWidget(self.collapse_btn)
        layout.addLayout(header_row)

        layout.addSpacing(8)

        # Navigation Buttons (Liquid Glass Pills)
        for key, code, label in NAV_ITEMS:
            btn = QPushButton(f"  {code}   {label}")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(40)
            btn.clicked.connect(lambda _checked, k=key: self.set_active_view(k))
            self._buttons[key] = btn
            layout.addWidget(btn)

        layout.addStretch(1)

        # Quick Theme Switcher
        self.theme_caption = QLabel("INTERFACE THEME")
        self.theme_caption.setStyleSheet("font-size: 10px; font-weight: 700; letter-spacing: 0.8px; color: #94A3B8;")
        layout.addWidget(self.theme_caption)

        self.theme_combo = QComboBox()
        for t_key, t_meta in LIQUID_GLASS_THEMES.items():
            self.theme_combo.addItem(str(t_meta["label"]), t_key)
        self.theme_combo.currentIndexChanged.connect(self._on_theme_combo_changed)
        layout.addWidget(self.theme_combo)

        # Setup Wizard Button
        self.wizard_btn = QPushButton("First-Run Setup Wizard")
        self.wizard_btn.setMinimumHeight(34)
        self.wizard_btn.setToolTip("Open the System Scan & Colibri Engine Setup Wizard")
        self.wizard_btn.clicked.connect(self.wizard_requested.emit)
        layout.addWidget(self.wizard_btn)

        # Bottom Liquid Glass Backend & Active Model Status Card
        self.footer_card = LiquidGlassPanel(self, radius=13.0)
        footer_layout = QVBoxLayout(self.footer_card)
        footer_layout.setContentsMargins(10, 10, 10, 10)
        footer_layout.setSpacing(5)

        status_row = QHBoxLayout()
        self.backend_caption = QLabel("ENGINE STATUS")
        self.backend_caption.setStyleSheet(
            "font-size: 10px; color: #94A3B8; font-weight: 700; letter-spacing: 0.7px;"
        )
        status_row.addWidget(self.backend_caption)
        status_row.addStretch(1)
        self.status_badge = StatusBadge("READY", variant="info")
        status_row.addWidget(self.status_badge)
        footer_layout.addLayout(status_row)

        self.active_model_label = QLabel("Model: None Loaded")
        self.active_model_label.setWordWrap(True)
        self.active_model_label.setStyleSheet("font-size: 12px; font-weight: 600;")
        footer_layout.addWidget(self.active_model_label)

        self.detail_label = QLabel("Local inference standby")
        self.detail_label.setWordWrap(True)
        self.detail_label.setStyleSheet("font-size: 11px; color: #94A3B8;")
        footer_layout.addWidget(self.detail_label)

        layout.addWidget(self.footer_card)
        self._apply_nav_styles()

    def set_selected_theme_key(self, theme_key: str) -> None:
        self.theme_combo.blockSignals(True)
        for i in range(self.theme_combo.count()):
            if self.theme_combo.itemData(i) == theme_key:
                self.theme_combo.setCurrentIndex(i)
                break
        self.theme_combo.blockSignals(False)
        self._apply_nav_styles()

    def _on_theme_combo_changed(self, _idx: int) -> None:
        t_key = str(self.theme_combo.currentData() or "obsidian_glass")
        self.theme_selected.emit(t_key)
        self._apply_nav_styles()

    def set_active_view(self, key: str, emit_signal: bool = True) -> None:
        if key not in self._buttons:
            return
        self._active_key = key
        self._apply_nav_styles()
        if emit_signal:
            self.view_selected.emit(key)

    def _apply_nav_styles(self) -> None:
        t = get_active_theme()
        acc1 = t["accent_primary"]
        acc2 = t["accent_secondary"]
        fg = t["text_primary"]
        fg2 = t["text_secondary"]
        is_dark = bool(t["is_dark"])
        idle_bg = "rgba(24, 34, 56, 95)" if is_dark else "rgba(255, 255, 255, 165)"
        hover_bg = "rgba(45, 62, 98, 155)" if is_dark else "rgba(255, 255, 255, 235)"

        for key, code, label in NAV_ITEMS:
            btn = self._buttons[key]
            is_active = key == self._active_key
            btn.setChecked(is_active)
            btn.setText(code if self._collapsed else f"  {code}   {label}")
            align = "center" if self._collapsed else "left"
            if is_active:
                btn.setStyleSheet(
                    f"""
                    QPushButton {{
                        text-align: {align};
                        background-color: qlineargradient(
                            x1:0, y1:0, x2:1, y2:0,
                            stop:0 {acc1},
                            stop:1 {acc2}
                        );
                        color: #FFFFFF;
                        border-top: 1px solid rgba(255, 255, 255, 0.48);
                        border-left: 1px solid rgba(255, 255, 255, 0.35);
                        border-right: 1px solid rgba(255, 255, 255, 0.30);
                        border-bottom: 1px solid {acc1};
                        border-radius: 10px;
                        padding: 8px 12px;
                        font-weight: 700;
                        letter-spacing: 0.2px;
                    }}
                    """
                )
            else:
                btn.setStyleSheet(
                    f"""
                    QPushButton {{
                        text-align: {align};
                        background-color: {idle_bg};
                        color: {fg2};
                        border: 1px solid rgba(148, 163, 184, 0.16);
                        border-radius: 10px;
                        padding: 8px 12px;
                        font-weight: 600;
                    }}
                    QPushButton:hover {{
                        background-color: {hover_bg};
                        color: {fg};
                    }}
                    """
                )

    def toggle_collapsed(self) -> None:
        self._collapsed = not self._collapsed
        if self._collapsed:
            self.setFixedWidth(74)
            self.logo_widget.set_logo_size(24)
            self.title_label.setVisible(False)
            self.brand_sub_label.setVisible(False)
            self.theme_caption.setVisible(False)
            self.theme_combo.setVisible(False)
            self.wizard_btn.setText("WIZ")
            self.footer_card.setVisible(False)
            self.collapse_btn.setText(">>")
        else:
            self.setFixedWidth(244)
            self.logo_widget.set_logo_size(40)
            self.title_label.setVisible(True)
            self.brand_sub_label.setVisible(True)
            self.theme_caption.setVisible(True)
            self.theme_combo.setVisible(True)
            self.wizard_btn.setText("First-Run Setup Wizard")
            self.footer_card.setVisible(True)
            self.collapse_btn.setText("<<")
        self._apply_nav_styles()

    def update_backend_status(
        self,
        state: str,
        detail: str = "",
        active_model: str = "",
    ) -> None:
        st_upper = state.upper()
        if st_upper == "RUNNING":
            self.status_badge.set_variant("green", "RUNNING")
        elif st_upper in ("STARTING", "INSTALLING", "RECOVERING"):
            self.status_badge.set_variant("yellow", st_upper)
        elif st_upper in ("FAILED", "NOT_INSTALLED"):
            self.status_badge.set_variant("red", st_upper)
        else:
            self.status_badge.set_variant("info", st_upper)

        if active_model:
            self.active_model_label.setText(f"Model: {active_model}")
        elif st_upper == "STOPPED":
            self.active_model_label.setText("Model: None Loaded")
        if detail:
            self.detail_label.setText(detail)
