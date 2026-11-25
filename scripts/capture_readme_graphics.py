"""Generate Authentic GitHub README Graphics & Live PyQt6 UI Screenshots (`scripts/capture_readme_graphics.py`)."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from PyQt6.QtCore import QPointF, QRectF, Qt  # noqa: E402
from PyQt6.QtGui import (  # noqa: E402
    QColor,
    QFont,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PyQt6.QtWidgets import QApplication  # noqa: E402

from app.application_state import ApplicationState  # noqa: E402
from app.ui.main_window import MainWindow  # noqa: E402
from app.ui.widgets.brand_logo import paint_colibri_emblem  # noqa: E402


def render_hero_banner(output_path: Path) -> Path:
    """Render a crisp 1280x400 Liquid Glass GitHub Hero Banner with the Colibri logo."""
    w, h = 1280, 400
    image = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)

    p = QPainter(image)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

    # Rounded outer card
    outer = QPainterPath()
    outer.addRoundedRect(QRectF(4, 4, w - 8, h - 8), 28, 28)

    bg = QLinearGradient(QPointF(0, 0), QPointF(w, h))
    bg.setColorAt(0.0, QColor(9, 14, 28))
    bg.setColorAt(0.5, QColor(7, 11, 22))
    bg.setColorAt(1.0, QColor(15, 13, 34))
    p.fillPath(outer, bg)

    # Ambient aurora glows
    g1 = QRadialGradient(QPointF(210, 200), 340)
    g1.setColorAt(0.0, QColor(56, 189, 248, 70))
    g1.setColorAt(0.6, QColor(14, 165, 233, 20))
    g1.setColorAt(1.0, QColor(0, 0, 0, 0))
    p.fillPath(outer, g1)

    g2 = QRadialGradient(QPointF(1080, 120), 360)
    g2.setColorAt(0.0, QColor(168, 85, 247, 58))
    g2.setColorAt(0.6, QColor(99, 102, 241, 18))
    g2.setColorAt(1.0, QColor(0, 0, 0, 0))
    p.fillPath(outer, g2)

    # Subtle grid lines
    p.setClipPath(outer)
    p.setPen(QPen(QColor(148, 163, 184, 18), 1.0))
    for gx in range(0, w, 48):
        p.drawLine(gx, 0, gx, h)
    for gy in range(0, h, 48):
        p.drawLine(0, gy, w, gy)
    p.setClipping(False)

    # Specular border
    rim = QLinearGradient(QPointF(0, 0), QPointF(w, h))
    rim.setColorAt(0.0, QColor(125, 211, 252, 160))
    rim.setColorAt(0.5, QColor(99, 102, 241, 100))
    rim.setColorAt(1.0, QColor(192, 132, 252, 150))
    p.setPen(QPen(rim, 2.0))
    p.drawPath(outer)

    # Logo on the left
    paint_colibri_emblem(p, QRectF(76, 80, 240, 240), draw_medallion=True)

    # Typography on the right
    p.setPen(QColor(56, 189, 248))
    tag_font = QFont("Segoe UI", 11, QFont.Weight.Bold)
    tag_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2.2)
    p.setFont(tag_font)
    p.drawText(QRectF(365, 82, 840, 28), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
               "WINDOWS 10/11  |  LOCAL LLM WORKSTATION  |  POWERED BY COLIBRI")

    p.setPen(QColor(248, 250, 252))
    title_font = QFont("Segoe UI", 42, QFont.Weight.ExtraBold)
    p.setFont(title_font)
    p.drawText(QRectF(365, 112, 840, 68), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
               "Colibri AI Studio")

    p.setPen(QColor(203, 213, 225))
    sub_font = QFont("Segoe UI", 15, QFont.Weight.Normal)
    p.setFont(sub_font)
    p.drawText(
        QRectF(365, 186, 830, 64),
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
        "Run massive MoE & quantized language models locally with a Liquid Glass desktop UI, "
        "3-tier VRAM / RAM / NVMe streaming, live Hugging Face discovery, and zero terminal setup.",
    )

    # Feature Pills
    pills = [
        ("PyQt6 Liquid Glass UI", QColor(56, 189, 248)),
        ("3-Tier VRAM / RAM / NVMe", QColor(99, 102, 241)),
        ("CUDA & Vulkan Ready", QColor(168, 85, 247)),
        ("100% Private & Offline", QColor(16, 185, 129)),
    ]
    px = 365.0
    py = 276.0
    pill_font = QFont("Segoe UI", 11, QFont.Weight.DemiBold)
    p.setFont(pill_font)
    fm = p.fontMetrics()
    for label, accent in pills:
        tw = fm.horizontalAdvance(label) + 32
        pill_rect = QRectF(px, py, float(tw), 36.0)
        pill_path = QPainterPath()
        pill_path.addRoundedRect(pill_rect, 10.0, 10.0)
        p.fillPath(pill_path, QColor(accent.red(), accent.green(), accent.blue(), 34))
        p.setPen(QPen(QColor(accent.red(), accent.green(), accent.blue(), 140), 1.2))
        p.drawPath(pill_path)
        p.setPen(QColor(241, 245, 249))
        p.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter, label)
        px += tw + 12.0

    p.end()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(str(output_path), "PNG")
    return output_path


def capture_ui_previews(output_dir: Path) -> list[Path]:
    """Render live PyQt6 MainWindow views to PNGs for README documentation."""
    output_dir.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication(sys.argv)
    saved: list[Path] = []

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        app_state = ApplicationState(
            db_path=tmp_path / "preview.db",
            settings_path=tmp_path / "settings.json",
        )
        app_state.settings_service.update(
            first_run_completed=True,
            models_dir=str(tmp_path / "models"),
            engine_dir=str(tmp_path / "engine"),
        )

        win = MainWindow(app_state=app_state)
        win.resize(1320, 820)
        win.show()
        app.processEvents()

        captures = [
            ("chat", "obsidian_glass", "preview_chat.png"),
            ("model_hub", "arctic_aurora", "preview_model_hub.png"),
            ("hardware", "amethyst_nebula", "preview_hardware.png"),
        ]
        for view_key, theme_key, fname in captures:
            win.apply_and_persist_theme(theme_key)
            win.switch_view(view_key)
            app.processEvents()
            pix = win.grab()
            out_file = output_dir / fname
            pix.save(str(out_file), "PNG")
            saved.append(out_file)

        win.close()

    return saved


if __name__ == "__main__":
    gfx_dir = ROOT_DIR / "assets" / "graphics"
    banner = render_hero_banner(gfx_dir / "hero_banner.png")
    print(f"Generated hero banner: {banner}")
    previews = capture_ui_previews(gfx_dir)
    for p in previews:
        print(f"Captured UI preview: {p}")
