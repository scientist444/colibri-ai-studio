"""Liquid Glass Visual & Multi-Theme Engine for Colibri AI Studio.

Provides:
- 5 executive-grade Liquid Glass themes:
  1. `obsidian_glass`     — Obsidian Liquid Glass (Default Dark)
  2. `arctic_aurora`      — Arctic Cyan Glass
  3. `amethyst_nebula`    — Amethyst Studio Glass
  4. `emerald_matrix`     — Emerald Workstation Glass
  5. `alabaster_daylight` — Alabaster Frosted Daylight (Light Liquid Glass)
- Windows 10/11 DWM Acrylic / Mica / Immersive Titlebar integration
- `LiquidGlassBackdrop`, `LiquidGlassPanel`, `LiquidGlassDialog` with live theme reactivity
- High-precision typography configuration (`Segoe UI Variable` / `Inter` + `Cascadia Code`)
"""

from __future__ import annotations

import ctypes
import os
from typing import Any

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PyQt6.QtWidgets import QApplication, QDialog, QFrame, QWidget

UI_FONT_FAMILY = '"Segoe UI Variable Text", "Segoe UI Variable Display", "Inter", "Aptos", "Segoe UI", sans-serif'
MONO_FONT_FAMILY = '"Cascadia Code", "JetBrains Mono", "Consolas", monospace'

LIQUID_GLASS_THEMES: dict[str, dict[str, Any]] = {
    "obsidian_glass": {
        "label": "Obsidian Liquid Glass (Default)",
        "is_dark": True,
        "bg_start": (8, 12, 22, 252),
        "bg_mid": (12, 18, 34, 252),
        "bg_end": (7, 10, 19, 254),
        "orb1": (14, 165, 233, 44),
        "orb2": (99, 102, 241, 40),
        "panel_top": (30, 42, 68, 172),
        "panel_mid": (20, 29, 48, 162),
        "panel_bot": (14, 21, 36, 182),
        "panel_elev_top": (38, 53, 84, 192),
        "panel_elev_bot": (18, 26, 45, 204),
        "border_spec": (255, 255, 255, 84),
        "border_accent1": (56, 189, 248, 60),
        "border_accent2": (99, 102, 241, 46),
        "accent_primary": "#0EA5E9",
        "accent_secondary": "#6366F1",
        "accent_hover": "#38BDF8",
        "text_primary": "#F8FAFC",
        "text_secondary": "#CBD5E1",
        "text_muted": "#94A3B8",
        "text_accent": "#7DD3FC",
        "input_bg": "rgba(12, 19, 34, 185)",
        "input_focus_bg": "rgba(16, 25, 44, 210)",
    },
    "arctic_aurora": {
        "label": "Arctic Cyan Glass",
        "is_dark": True,
        "bg_start": (6, 16, 26, 252),
        "bg_mid": (9, 24, 38, 252),
        "bg_end": (5, 14, 22, 254),
        "orb1": (6, 182, 212, 50),
        "orb2": (20, 184, 166, 38),
        "panel_top": (20, 48, 68, 172),
        "panel_mid": (14, 35, 52, 162),
        "panel_bot": (10, 26, 40, 182),
        "panel_elev_top": (26, 60, 84, 192),
        "panel_elev_bot": (12, 32, 48, 204),
        "border_spec": (240, 253, 250, 88),
        "border_accent1": (34, 211, 238, 66),
        "border_accent2": (45, 212, 191, 48),
        "accent_primary": "#06B6D4",
        "accent_secondary": "#0D9488",
        "accent_hover": "#22D3EE",
        "text_primary": "#F0FDFA",
        "text_secondary": "#CCFBF1",
        "text_muted": "#99F6E4",
        "text_accent": "#67E8F9",
        "input_bg": "rgba(8, 24, 36, 185)",
        "input_focus_bg": "rgba(12, 32, 48, 210)",
    },
    "amethyst_nebula": {
        "label": "Amethyst Studio Glass",
        "is_dark": True,
        "bg_start": (13, 9, 24, 252),
        "bg_mid": (20, 13, 36, 252),
        "bg_end": (10, 7, 19, 254),
        "orb1": (139, 92, 246, 46),
        "orb2": (217, 70, 239, 34),
        "panel_top": (42, 28, 68, 172),
        "panel_mid": (29, 19, 49, 162),
        "panel_bot": (21, 14, 36, 182),
        "panel_elev_top": (54, 36, 86, 192),
        "panel_elev_bot": (26, 17, 45, 204),
        "border_spec": (255, 255, 255, 84),
        "border_accent1": (167, 139, 250, 64),
        "border_accent2": (232, 121, 249, 46),
        "accent_primary": "#8B5CF6",
        "accent_secondary": "#C026D3",
        "accent_hover": "#A78BFA",
        "text_primary": "#FAF5FF",
        "text_secondary": "#E9D5FF",
        "text_muted": "#C4B5FD",
        "text_accent": "#DDD6FE",
        "input_bg": "rgba(18, 11, 32, 185)",
        "input_focus_bg": "rgba(25, 16, 44, 210)",
    },
    "emerald_matrix": {
        "label": "Emerald Workstation Glass",
        "is_dark": True,
        "bg_start": (6, 16, 13, 252),
        "bg_mid": (10, 24, 20, 252),
        "bg_end": (5, 13, 10, 254),
        "orb1": (16, 185, 129, 44),
        "orb2": (14, 165, 233, 34),
        "panel_top": (20, 48, 39, 172),
        "panel_mid": (14, 34, 28, 162),
        "panel_bot": (10, 25, 20, 182),
        "panel_elev_top": (26, 60, 49, 192),
        "panel_elev_bot": (12, 30, 25, 204),
        "border_spec": (236, 253, 245, 84),
        "border_accent1": (52, 211, 153, 62),
        "border_accent2": (16, 185, 129, 46),
        "accent_primary": "#10B981",
        "accent_secondary": "#059669",
        "accent_hover": "#34D399",
        "text_primary": "#ECFDF5",
        "text_secondary": "#D1FAE5",
        "text_muted": "#6EE7B7",
        "text_accent": "#A7F3D0",
        "input_bg": "rgba(8, 22, 18, 185)",
        "input_focus_bg": "rgba(12, 30, 24, 210)",
    },
    "alabaster_daylight": {
        "label": "Alabaster Frosted Daylight (Light)",
        "is_dark": False,
        "bg_start": (236, 242, 249, 255),
        "bg_mid": (228, 236, 246, 255),
        "bg_end": (241, 245, 250, 255),
        "orb1": (14, 165, 233, 35),
        "orb2": (99, 102, 241, 28),
        "panel_top": (255, 255, 255, 215),
        "panel_mid": (248, 250, 252, 205),
        "panel_bot": (241, 245, 249, 220),
        "panel_elev_top": (255, 255, 255, 238),
        "panel_elev_bot": (245, 248, 252, 232),
        "border_spec": (255, 255, 255, 220),
        "border_accent1": (2, 132, 199, 75),
        "border_accent2": (79, 70, 229, 55),
        "accent_primary": "#0284C7",
        "accent_secondary": "#4F46E5",
        "accent_hover": "#0369A1",
        "text_primary": "#0F172A",
        "text_secondary": "#1E293B",
        "text_muted": "#475569",
        "text_accent": "#0369A1",
        "input_bg": "rgba(255, 255, 255, 215)",
        "input_focus_bg": "rgba(255, 255, 255, 245)",
    },
}

_ACTIVE_THEME_KEY: str = "obsidian_glass"


def get_active_theme_key() -> str:
    return _ACTIVE_THEME_KEY


def get_active_theme() -> dict[str, Any]:
    return LIQUID_GLASS_THEMES.get(_ACTIVE_THEME_KEY, LIQUID_GLASS_THEMES["obsidian_glass"])


def configure_application_typography(app: QApplication, scale_percent: int = 100) -> None:
    """Configure high-clarity OpenType/ClearType application typography."""
    base_pt = max(9, int(round(10.0 * (scale_percent / 100.0))))
    font = QFont("Segoe UI Variable Text", base_pt)
    font.setStyleHint(QFont.StyleHint.SansSerif)
    font.setStyleStrategy(
        QFont.StyleStrategy.PreferAntialias | QFont.StyleStrategy.PreferQuality
    )
    app.setFont(font)


def build_theme_stylesheet(theme_key: str = "obsidian_glass") -> str:
    """Generate the complete Liquid Glass QSS stylesheet for the specified theme."""
    t = LIQUID_GLASS_THEMES.get(theme_key, LIQUID_GLASS_THEMES["obsidian_glass"])
    is_dark = bool(t["is_dark"])
    pt = t["panel_top"]
    pm = t["panel_mid"]
    pb = t["panel_bot"]
    b_spec = t["border_spec"]
    b_acc1 = t["border_accent1"]
    b_acc2 = t["border_accent2"]
    fg1 = t["text_primary"]
    fg2 = t["text_secondary"]
    fg_muted = t["text_muted"]
    fg_acc = t["text_accent"]
    acc1 = t["accent_primary"]
    acc2 = t["accent_secondary"]
    acc_hover = t["accent_hover"]
    inp_bg = t["input_bg"]
    inp_focus = t["input_focus_bg"]
    bg_hex = "#080C16" if is_dark else "#ECF2F9"
    btn_top = "rgba(42, 58, 90, 185)" if is_dark else "rgba(255, 255, 255, 225)"
    btn_bot = "rgba(26, 37, 60, 195)" if is_dark else "rgba(235, 241, 248, 230)"
    btn_hover_top = "rgba(56, 76, 116, 215)" if is_dark else "rgba(255, 255, 255, 250)"
    btn_hover_bot = "rgba(36, 52, 84, 215)" if is_dark else "rgba(224, 234, 246, 245)"
    dropdown_bg = "rgba(15, 23, 40, 246)" if is_dark else "rgba(250, 252, 255, 250)"

    return f"""
QWidget {{
    color: {fg1};
    font-family: {UI_FONT_FAMILY};
    font-size: 13px;
    background: transparent;
}}

QMainWindow, QDialog {{
    background-color: {bg_hex};
}}

QLabel#viewTitle {{
    font-size: 21px;
    font-weight: 700;
    color: {fg1};
    letter-spacing: 0.25px;
}}

QLabel#viewSubtitle {{
    font-size: 12.5px;
    font-weight: 400;
    color: {fg_muted};
}}

QLabel#sectionHeader {{
    font-size: 14.5px;
    font-weight: 600;
    color: {fg1};
    letter-spacing: 0.15px;
}}

QLabel#mutedLabel {{
    color: {fg_muted};
    font-size: 12px;
}}

QLabel#monoValue {{
    font-family: {MONO_FONT_FAMILY};
    font-size: 12.5px;
    color: {fg_acc};
}}

/* Liquid Glass Tabs (All Screens & Sub-Screens) */
QTabWidget::pane {{
    background-color: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba({pt[0]}, {pt[1]}, {pt[2]}, {pt[3]}),
        stop:0.5 rgba({pm[0]}, {pm[1]}, {pm[2]}, {pm[3]}),
        stop:1 rgba({pb[0]}, {pb[1]}, {pb[2]}, {pb[3]})
    );
    border-top: 1px solid rgba({b_spec[0]}, {b_spec[1]}, {b_spec[2]}, {b_spec[3]});
    border-left: 1px solid rgba({b_acc1[0]}, {b_acc1[1]}, {b_acc1[2]}, {b_acc1[3]});
    border-right: 1px solid rgba({b_acc2[0]}, {b_acc2[1]}, {b_acc2[2]}, {b_acc2[3]});
    border-bottom: 1px solid rgba({b_acc1[0]}, {b_acc1[1]}, {b_acc1[2]}, 35);
    border-radius: 16px;
    margin-top: 6px;
    padding: 10px;
}}

QTabBar::tab {{
    background-color: {btn_top};
    color: {fg_muted};
    border-top: 1px solid rgba({b_spec[0]}, {b_spec[1]}, {b_spec[2]}, 55);
    border-left: 1px solid rgba({b_acc1[0]}, {b_acc1[1]}, {b_acc1[2]}, 35);
    border-right: 1px solid rgba({b_acc1[0]}, {b_acc1[1]}, {b_acc1[2]}, 35);
    border-bottom: 1px solid rgba({b_acc1[0]}, {b_acc1[1]}, {b_acc1[2]}, 25);
    border-radius: 10px;
    padding: 8px 18px;
    margin-right: 8px;
    font-weight: 600;
    letter-spacing: 0.2px;
}}

QTabBar::tab:hover {{
    background-color: {btn_hover_top};
    color: {fg1};
}}

QTabBar::tab:selected {{
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 {acc1},
        stop:1 {acc2}
    );
    color: #FFFFFF;
    border-top: 1px solid rgba(255, 255, 255, 140);
    border-left: 1px solid rgba(255, 255, 255, 95);
    border-right: 1px solid rgba(255, 255, 255, 80);
    border-bottom: 1px solid {acc_hover};
}}

/* Liquid Glass Buttons */
QPushButton {{
    background-color: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 {btn_top},
        stop:1 {btn_bot}
    );
    color: {fg1};
    border-top: 1px solid rgba({b_spec[0]}, {b_spec[1]}, {b_spec[2]}, 68);
    border-left: 1px solid rgba({b_acc1[0]}, {b_acc1[1]}, {b_acc1[2]}, 48);
    border-right: 1px solid rgba({b_acc1[0]}, {b_acc1[1]}, {b_acc1[2]}, 48);
    border-bottom: 1px solid rgba({b_acc1[0]}, {b_acc1[1]}, {b_acc1[2]}, 32);
    border-radius: 10px;
    padding: 7px 15px;
    font-weight: 600;
    letter-spacing: 0.15px;
}}

QPushButton:hover {{
    background-color: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 {btn_hover_top},
        stop:1 {btn_hover_bot}
    );
    border-bottom: 1px solid {acc_hover};
}}

QPushButton:disabled {{
    background-color: rgba(128, 128, 128, 35);
    color: {fg_muted};
    border: 1px solid rgba(128, 128, 128, 25);
}}

QPushButton#primaryGlassButton {{
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 {acc1},
        stop:1 {acc2}
    );
    color: #FFFFFF;
    border-top: 1px solid rgba(255, 255, 255, 135);
    border-left: 1px solid rgba(255, 255, 255, 90);
    border-right: 1px solid rgba(255, 255, 255, 75);
    border-bottom: 1px solid {acc_hover};
}}

QPushButton#primaryGlassButton:hover {{
    background-color: {acc_hover};
}}

QPushButton#dangerGlassButton {{
    background-color: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(220, 38, 38, 195),
        stop:1 rgba(153, 27, 27, 205)
    );
    color: #FFFFFF;
    border-top: 1px solid rgba(252, 165, 165, 110);
    border-bottom: 1px solid rgba(239, 68, 68, 100);
}}

QPushButton#dangerGlassButton:hover {{
    background-color: rgba(239, 68, 68, 230);
}}

/* Liquid Glass Inputs, ComboBoxes & Text Areas */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background-color: {inp_bg};
    color: {fg1};
    border-top: 1px solid rgba({b_spec[0]}, {b_spec[1]}, {b_spec[2]}, 58);
    border-left: 1px solid rgba({b_acc1[0]}, {b_acc1[1]}, {b_acc1[2]}, 42);
    border-right: 1px solid rgba({b_acc1[0]}, {b_acc1[1]}, {b_acc1[2]}, 42);
    border-bottom: 1px solid rgba({b_acc1[0]}, {b_acc1[1]}, {b_acc1[2]}, 30);
    border-radius: 10px;
    padding: 7px 11px;
    selection-background-color: {acc1};
    selection-color: #FFFFFF;
}}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{
    border: 1px solid {acc_hover};
    background-color: {inp_focus};
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QComboBox QAbstractItemView {{
    background-color: {dropdown_bg};
    color: {fg1};
    border: 1px solid {acc1};
    border-radius: 10px;
    selection-background-color: {acc1};
    selection-color: #FFFFFF;
    padding: 4px;
}}

/* Liquid Glass Lists & Tables */
QListWidget, QTableWidget, QTreeWidget {{
    background-color: {inp_bg};
    border-top: 1px solid rgba({b_spec[0]}, {b_spec[1]}, {b_spec[2]}, 50);
    border-left: 1px solid rgba({b_acc1[0]}, {b_acc1[1]}, {b_acc1[2]}, 36);
    border-right: 1px solid rgba({b_acc1[0]}, {b_acc1[1]}, {b_acc1[2]}, 36);
    border-bottom: 1px solid rgba({b_acc1[0]}, {b_acc1[1]}, {b_acc1[2]}, 25);
    border-radius: 12px;
    padding: 6px;
    outline: none;
}}

QListWidget::item {{
    border-radius: 8px;
    padding: 8px 10px;
    margin-bottom: 3px;
    color: {fg2};
    font-weight: 500;
}}

QListWidget::item:hover {{
    background-color: rgba({b_acc1[0]}, {b_acc1[1]}, {b_acc1[2]}, 28);
}}

QListWidget::item:selected {{
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 {acc1},
        stop:1 {acc2}
    );
    color: #FFFFFF;
    font-weight: 600;
}}

QHeaderView::section {{
    background-color: {btn_top};
    color: {fg_muted};
    border: none;
    border-bottom: 1px solid rgba({b_acc1[0]}, {b_acc1[1]}, {b_acc1[2]}, 55);
    padding: 7px 10px;
    font-weight: 600;
}}

/* ProgressBar & Sliders */
QProgressBar {{
    background-color: {inp_bg};
    border: 1px solid rgba({b_acc1[0]}, {b_acc1[1]}, {b_acc1[2]}, 45);
    border-radius: 8px;
    text-align: center;
    color: {fg1};
    font-weight: 600;
    min-height: 16px;
}}

QProgressBar::chunk {{
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 {acc1},
        stop:1 {acc2}
    );
    border-radius: 7px;
}}

QSlider::groove:horizontal {{
    height: 6px;
    background: {inp_bg};
    border: 1px solid rgba({b_acc1[0]}, {b_acc1[1]}, {b_acc1[2]}, 40);
    border-radius: 3px;
}}

QSlider::sub-page:horizontal {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {acc1}, stop:1 {acc2});
    border-radius: 3px;
}}

QSlider::handle:horizontal {{
    background: #FFFFFF;
    border: 2px solid {acc1};
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 9px;
}}

QScrollArea {{
    border: none;
    background: transparent;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
    border-radius: 5px;
}}

QScrollBar::handle:vertical {{
    background: rgba(148, 163, 184, 0.35);
    min-height: 28px;
    border-radius: 5px;
}}

QScrollBar::handle:vertical:hover {{
    background: {acc_hover};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
"""


def apply_theme_to_app(theme_key: str, scale_percent: int = 100) -> None:
    """Switch the active Liquid Glass theme across the entire QApplication in real time."""
    global _ACTIVE_THEME_KEY
    if theme_key not in LIQUID_GLASS_THEMES:
        theme_key = "obsidian_glass"
    _ACTIVE_THEME_KEY = theme_key

    app = QApplication.instance()
    if isinstance(app, QApplication):
        configure_application_typography(app, scale_percent=scale_percent)
        app.setStyleSheet(build_theme_stylesheet(theme_key))
        for widget in app.allWidgets():
            widget.update()


def apply_windows_liquid_glass(widget: QWidget) -> None:
    """Apply Windows 10/11 DWM immersive title bar, rounded corners, and translucent backdrop."""
    if os.name != "nt":
        return
    try:
        hwnd = int(widget.winId())
        if not hwnd:
            return
        dwmapi = ctypes.windll.dwmapi
        t = get_active_theme()

        # DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        dark_mode = ctypes.c_int(1 if t.get("is_dark", True) else 0)
        dwmapi.DwmSetWindowAttribute(
            hwnd, 20, ctypes.byref(dark_mode), ctypes.sizeof(dark_mode)
        )

        # DWMWA_WINDOW_CORNER_PREFERENCE = 33 (DWMWCP_ROUND = 2)
        round_pref = ctypes.c_int(2)
        dwmapi.DwmSetWindowAttribute(
            hwnd, 33, ctypes.byref(round_pref), ctypes.sizeof(round_pref)
        )

        # DWMWA_SYSTEMBACKDROP_TYPE = 38 (DWMSBT_TRANSIENTWINDOW / Acrylic = 3)
        backdrop_type = ctypes.c_int(3)
        dwmapi.DwmSetWindowAttribute(
            hwnd, 38, ctypes.byref(backdrop_type), ctypes.sizeof(backdrop_type)
        )
    except Exception:
        pass


class LiquidGlassBackdrop(QWidget):
    """Root backdrop widget that paints a theme-aware Liquid Glass aurora environment."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    def paintEvent(self, event: object) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect())
        t = get_active_theme()

        base_grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        base_grad.setColorAt(0.0, QColor(*t["bg_start"]))
        base_grad.setColorAt(0.5, QColor(*t["bg_mid"]))
        base_grad.setColorAt(1.0, QColor(*t["bg_end"]))
        painter.fillRect(rect, base_grad)

        orb1 = QRadialGradient(
            QPointF(rect.width() * 0.18, rect.height() * 0.14),
            max(rect.width(), rect.height()) * 0.45,
        )
        orb1.setColorAt(0.0, QColor(*t["orb1"]))
        orb1.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(rect, orb1)

        orb2 = QRadialGradient(
            QPointF(rect.width() * 0.84, rect.height() * 0.82),
            max(rect.width(), rect.height()) * 0.50,
        )
        orb2.setColorAt(0.0, QColor(*t["orb2"]))
        orb2.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(rect, orb2)

        orb3 = QRadialGradient(
            QPointF(rect.width() * 0.52, 0.0),
            rect.width() * 0.40,
        )
        orb3.setColorAt(0.0, QColor(255, 255, 255, 22))
        orb3.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.fillRect(rect, orb3)
        painter.end()


class LiquidGlassPanel(QFrame):
    """Frosted Liquid Glass container with theme-aware refractive fill and specular border."""

    def __init__(
        self,
        parent: QWidget | None = None,
        radius: float = 16.0,
        tint_color: QColor | None = None,
        elevated: bool = False,
    ) -> None:
        super().__init__(parent)
        self._radius = radius
        self._tint = tint_color
        self._elevated = elevated
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def paintEvent(self, event: object) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        path = QPainterPath()
        path.addRoundedRect(r, self._radius, self._radius)
        t = get_active_theme()

        fill_grad = QLinearGradient(r.topLeft(), r.bottomLeft())
        if self._tint is not None:
            c = self._tint
            fill_grad.setColorAt(0.0, QColor(c.red(), c.green(), c.blue(), 65))
            fill_grad.setColorAt(1.0, QColor(*t["panel_bot"]))
        elif self._elevated:
            fill_grad.setColorAt(0.0, QColor(*t["panel_elev_top"]))
            fill_grad.setColorAt(0.5, QColor(*t["panel_mid"]))
            fill_grad.setColorAt(1.0, QColor(*t["panel_elev_bot"]))
        else:
            fill_grad.setColorAt(0.0, QColor(*t["panel_top"]))
            fill_grad.setColorAt(0.5, QColor(*t["panel_mid"]))
            fill_grad.setColorAt(1.0, QColor(*t["panel_bot"]))
        painter.fillPath(path, fill_grad)

        sheen_rect = QRectF(r.left(), r.top(), r.width(), min(40.0, r.height() * 0.35))
        sheen_path = QPainterPath()
        sheen_path.addRoundedRect(sheen_rect, self._radius, self._radius)
        sheen_grad = QLinearGradient(sheen_rect.topLeft(), sheen_rect.bottomLeft())
        sheen_grad.setColorAt(0.0, QColor(255, 255, 255, 24))
        sheen_grad.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.fillPath(sheen_path.intersected(path), sheen_grad)

        border_grad = QLinearGradient(r.topLeft(), r.bottomRight())
        border_grad.setColorAt(0.0, QColor(*t["border_spec"]))
        border_grad.setColorAt(0.4, QColor(*t["border_accent1"]))
        border_grad.setColorAt(0.8, QColor(*t["border_accent2"]))
        border_grad.setColorAt(1.0, QColor(*t["border_spec"]))
        pen = QPen(border_grad, 1.2)
        painter.setPen(pen)
        painter.drawPath(path)
        painter.end()


class LiquidGlassDialog(QDialog):
    """Base modal dialog with Windows DWM Liquid Glass and theme-aware backdrop."""

    def __init__(self, parent: QWidget | None = None, title: str = "Colibri AI Studio") -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        apply_windows_liquid_glass(self)

    def paintEvent(self, event: object) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect())
        t = get_active_theme()

        bg = QLinearGradient(rect.topLeft(), rect.bottomRight())
        bg.setColorAt(0.0, QColor(*t["bg_start"]))
        bg.setColorAt(0.5, QColor(*t["bg_mid"]))
        bg.setColorAt(1.0, QColor(*t["bg_end"]))
        painter.fillRect(rect, bg)

        glow = QRadialGradient(QPointF(rect.width() * 0.25, rect.height() * 0.15), rect.width() * 0.6)
        glow.setColorAt(0.0, QColor(*t["orb1"]))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(rect, glow)

        border_rect = rect.adjusted(1.0, 1.0, -1.0, -1.0)
        pen = QPen(QColor(*t["border_accent1"]), 1.2)
        painter.setPen(pen)
        painter.drawRoundedRect(border_rect, 12.0, 12.0)
        painter.end()
