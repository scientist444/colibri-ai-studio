"""Signature Brand Logo Widget & Asset Generator (`brand_logo.py`) for Colibri AI Studio.

Renders the official Colibri AI Studio emblem:
- A precision-sculpted Crystalline Origami Hummingbird ("Colibri") in hovering flight
  inside a Liquid Glass obsidian squircle medallion.
- Layered cyan/azure, royal indigo, and violet-magenta aerodynamic feather facets.
- Luminous Mixture-of-Experts (MoE) neural routing nodes and pathways.
- Specular liquid-glass rim lighting and ambient radial glow.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QColor,
    QIcon,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
    QRadialGradient,
)
from PyQt6.QtWidgets import QSizePolicy, QWidget


def paint_colibri_emblem(
    painter: QPainter,
    rect: QRectF,
    draw_medallion: bool = True,
) -> None:
    """Paint the vector Colibri AI Studio Hummingbird emblem inside `rect`.

    All coordinates are normalized to a 100x100 virtual canvas and scaled cleanly
    to any target resolution (16px icon up to 1024px hero artwork).
    """
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

    size = min(rect.width(), rect.height())
    ox = rect.x() + (rect.width() - size) / 2.0
    oy = rect.y() + (rect.height() - size) / 2.0

    painter.translate(ox, oy)
    scale = size / 100.0
    painter.scale(scale, scale)

    def pt(x: float, y: float) -> QPointF:
        return QPointF(x, y)

    def poly(*coords: tuple[float, float]) -> QPolygonF:
        return QPolygonF([QPointF(x, y) for x, y in coords])

    # 1. Liquid Glass Obsidian Medallion Base
    if draw_medallion:
        medallion_rect = QRectF(3.5, 3.5, 93.0, 93.0)
        medallion_path = QPainterPath()
        medallion_path.addRoundedRect(medallion_rect, 22.5, 22.5)

        # Deep space obsidian-sapphire fill
        bg_grad = QLinearGradient(pt(0, 0), pt(100, 100))
        bg_grad.setColorAt(0.0, QColor(11, 17, 33, 255))
        bg_grad.setColorAt(0.50, QColor(6, 10, 20, 255))
        bg_grad.setColorAt(1.0, QColor(13, 12, 28, 255))
        painter.fillPath(medallion_path, bg_grad)

        # Ambient cyan-indigo-violet aurora bloom inside medallion
        aurora_cyan = QRadialGradient(pt(32, 30), 50.0)
        aurora_cyan.setColorAt(0.0, QColor(56, 189, 248, 78))
        aurora_cyan.setColorAt(0.55, QColor(14, 165, 233, 24))
        aurora_cyan.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillPath(medallion_path, aurora_cyan)

        aurora_violet = QRadialGradient(pt(68, 70), 46.0)
        aurora_violet.setColorAt(0.0, QColor(168, 85, 247, 68))
        aurora_violet.setColorAt(0.55, QColor(99, 102, 241, 22))
        aurora_violet.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillPath(medallion_path, aurora_violet)

        # Subtle Orbital Neural Ring inside the medallion
        painter.setPen(QPen(QColor(56, 189, 248, 28), 0.75, Qt.PenStyle.DashLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(pt(50, 50), 37.5, 37.5)

        # Top Glass Specular Refraction Sheen
        sheen_path = QPainterPath()
        sheen_path.addRoundedRect(QRectF(6.0, 6.0, 88.0, 38.0), 19.0, 19.0)
        sheen_grad = QLinearGradient(pt(50, 6), pt(50, 44))
        sheen_grad.setColorAt(0.0, QColor(255, 255, 255, 34))
        sheen_grad.setColorAt(0.5, QColor(255, 255, 255, 8))
        sheen_grad.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.fillPath(sheen_path, sheen_grad)

        # Outer Prismatic Specular Rim
        border_grad = QLinearGradient(pt(0, 0), pt(100, 100))
        border_grad.setColorAt(0.0, QColor(125, 211, 252, 215))
        border_grad.setColorAt(0.5, QColor(99, 102, 241, 155))
        border_grad.setColorAt(1.0, QColor(192, 132, 252, 200))
        painter.setPen(QPen(border_grad, 2.0))
        painter.drawPath(medallion_path)

    facet_edge = QPen(QColor(224, 242, 254, 135), 0.65)

    # 2. Far Wing (Elevated Secondary Wing in Amethyst -> Royal Indigo)
    far_wing_tip = poly((19, 13), (39, 21), (52, 36), (34, 29))
    fw_grad = QLinearGradient(pt(19, 13), pt(52, 36))
    fw_grad.setColorAt(0.0, QColor(216, 180, 254, 235))
    fw_grad.setColorAt(0.5, QColor(139, 92, 246, 220))
    fw_grad.setColorAt(1.0, QColor(67, 56, 202, 210))
    painter.setPen(facet_edge)
    painter.setBrush(fw_grad)
    painter.drawPolygon(far_wing_tip)

    # 3. Primary Swept Wing — Feather Blade 1 (Leading Edge: Ice Cyan -> Electric Sky)
    wing_blade_1 = poly((11, 19), (33, 24), (52, 39), (35, 36))
    wb1_grad = QLinearGradient(pt(11, 19), pt(52, 39))
    wb1_grad.setColorAt(0.0, QColor(186, 230, 253, 255))
    wb1_grad.setColorAt(0.45, QColor(56, 189, 248, 252))
    wb1_grad.setColorAt(1.0, QColor(2, 132, 199, 248))
    painter.setBrush(wb1_grad)
    painter.drawPolygon(wing_blade_1)

    # 4. Primary Swept Wing — Feather Blade 2 (Mid Primary: Sky Blue -> Royal Blue)
    wing_blade_2 = poly((11, 19), (35, 36), (48, 45), (14, 32))
    wb2_grad = QLinearGradient(pt(11, 25), pt(48, 45))
    wb2_grad.setColorAt(0.0, QColor(56, 189, 248, 248))
    wb2_grad.setColorAt(0.55, QColor(59, 130, 246, 244))
    wb2_grad.setColorAt(1.0, QColor(37, 99, 235, 242))
    painter.setBrush(wb2_grad)
    painter.drawPolygon(wing_blade_2)

    # 5. Primary Swept Wing — Feather Blade 3 (Inner covert: Azure -> Electric Indigo)
    wing_blade_3 = poly((14, 32), (48, 45), (45, 51), (19, 43))
    wb3_grad = QLinearGradient(pt(14, 35), pt(48, 51))
    wb3_grad.setColorAt(0.0, QColor(96, 165, 250, 240))
    wb3_grad.setColorAt(0.55, QColor(99, 102, 241, 238))
    wb3_grad.setColorAt(1.0, QColor(79, 70, 229, 235))
    painter.setBrush(wb3_grad)
    painter.drawPolygon(wing_blade_3)

    # 6. Primary Swept Wing — Feather Blade 4 (Trailing Plume: Violet -> Magenta-Indigo)
    wing_blade_4 = poly((19, 43), (45, 51), (42, 55), (26, 52))
    wb4_grad = QLinearGradient(pt(19, 43), pt(45, 55))
    wb4_grad.setColorAt(0.0, QColor(192, 132, 252, 235))
    wb4_grad.setColorAt(0.6, QColor(139, 92, 246, 230))
    wb4_grad.setColorAt(1.0, QColor(88, 28, 135, 225))
    painter.setBrush(wb4_grad)
    painter.drawPolygon(wing_blade_4)

    # 7. Sculpted Crown & Head (Two interlocking crystalline facets)
    crown_facet = poly((52, 36), (61, 27), (70, 31), (61, 38))
    crown_grad = QLinearGradient(pt(52, 27), pt(70, 38))
    crown_grad.setColorAt(0.0, QColor(186, 230, 253, 255))
    crown_grad.setColorAt(0.6, QColor(56, 189, 248, 252))
    crown_grad.setColorAt(1.0, QColor(14, 165, 233, 248))
    painter.setBrush(crown_grad)
    painter.drawPolygon(crown_facet)

    cheek_facet = poly((52, 36), (61, 38), (70, 31), (66, 43), (52, 39))
    cheek_grad = QLinearGradient(pt(52, 36), pt(70, 43))
    cheek_grad.setColorAt(0.0, QColor(56, 189, 248, 250))
    cheek_grad.setColorAt(1.0, QColor(37, 99, 235, 248))
    painter.setBrush(cheek_grad)
    painter.drawPolygon(cheek_facet)

    # 8. Precision Needle Beak (Sleek hummingbird bill aimed at the star spark)
    beak_upper = poly((70, 31), (88, 22), (68, 36))
    beak_u_grad = QLinearGradient(pt(68, 33), pt(88, 22))
    beak_u_grad.setColorAt(0.0, QColor(125, 211, 252, 255))
    beak_u_grad.setColorAt(1.0, QColor(255, 255, 255, 255))
    painter.setBrush(beak_u_grad)
    painter.drawPolygon(beak_upper)

    beak_lower = poly((68, 36), (88, 22), (66, 40))
    beak_l_grad = QLinearGradient(pt(66, 38), pt(88, 22))
    beak_l_grad.setColorAt(0.0, QColor(14, 165, 233, 250))
    beak_l_grad.setColorAt(1.0, QColor(186, 230, 253, 255))
    painter.setBrush(beak_l_grad)
    painter.drawPolygon(beak_lower)

    # 9. Iridescent Gorget / Breast Prism (Luminous Cyan-Teal -> Deep Sapphire)
    breast_facet = poly((52, 39), (66, 43), (59, 57), (48, 45))
    breast_grad = QLinearGradient(pt(50, 39), pt(64, 57))
    breast_grad.setColorAt(0.0, QColor(103, 232, 249, 255))
    breast_grad.setColorAt(0.45, QColor(6, 182, 212, 250))
    breast_grad.setColorAt(1.0, QColor(29, 78, 216, 248))
    painter.setBrush(breast_grad)
    painter.drawPolygon(breast_facet)

    # 10. Dorsal Spine & Torso Core Facet
    spine_facet = poly((48, 45), (59, 57), (49, 66), (42, 55), (45, 51))
    spine_grad = QLinearGradient(pt(42, 45), pt(59, 66))
    spine_grad.setColorAt(0.0, QColor(59, 130, 246, 248))
    spine_grad.setColorAt(0.6, QColor(79, 70, 229, 245))
    spine_grad.setColorAt(1.0, QColor(49, 46, 129, 245))
    painter.setBrush(spine_grad)
    painter.drawPolygon(spine_facet)

    # 11. Ventral Tail Base Facet
    tail_base = poly((42, 55), (49, 66), (39, 72), (36, 61))
    tb_grad = QLinearGradient(pt(36, 55), pt(49, 72))
    tb_grad.setColorAt(0.0, QColor(99, 102, 241, 242))
    tb_grad.setColorAt(1.0, QColor(124, 58, 237, 240))
    painter.setBrush(tb_grad)
    painter.drawPolygon(tail_base)

    # 12. Swept Forked Tail Feathers (3 graceful aerodynamic tail plumes)
    tail_long = poly((36, 61), (39, 72), (25, 87), (19, 84))
    tl_grad = QLinearGradient(pt(39, 65), pt(19, 87))
    tl_grad.setColorAt(0.0, QColor(99, 102, 241, 245))
    tl_grad.setColorAt(0.5, QColor(168, 85, 247, 240))
    tl_grad.setColorAt(1.0, QColor(236, 72, 153, 235))
    painter.setBrush(tl_grad)
    painter.drawPolygon(tail_long)

    tail_mid = poly((39, 72), (49, 66), (37, 85), (31, 80))
    tm_grad = QLinearGradient(pt(49, 66), pt(33, 85))
    tm_grad.setColorAt(0.0, QColor(56, 189, 248, 240))
    tm_grad.setColorAt(0.6, QColor(99, 102, 241, 235))
    tm_grad.setColorAt(1.0, QColor(168, 85, 247, 230))
    painter.setBrush(tm_grad)
    painter.drawPolygon(tail_mid)

    tail_Fork_right = poly((44, 69), (49, 66), (48, 82), (42, 77))
    tr_grad = QLinearGradient(pt(49, 66), pt(45, 82))
    tr_grad.setColorAt(0.0, QColor(125, 211, 252, 230))
    tr_grad.setColorAt(1.0, QColor(59, 130, 246, 225))
    painter.setBrush(tr_grad)
    painter.drawPolygon(tail_Fork_right)

    # 13. Neural MoE Routing Constellation (Subtle precision circuit pathways + glowing nodes)
    circuit_pen = QPen(QColor(224, 242, 254, 150), 0.75)
    painter.setPen(circuit_pen)
    painter.drawLine(pt(24, 26), pt(35, 36))
    painter.drawLine(pt(35, 36), pt(48, 45))
    painter.drawLine(pt(48, 45), pt(61, 35))
    painter.drawLine(pt(48, 45), pt(46, 60))

    nodes = (
        (24.0, 26.0, 1.45),
        (35.0, 36.0, 1.55),
        (48.0, 45.0, 1.85),
        (46.0, 60.0, 1.45),
        (61.5, 34.5, 1.75),  # Simultaneously serves as the luminous cyber-eye
    )
    for nx, ny, nr in nodes:
        painter.setPen(Qt.PenStyle.NoPen)
        glow = QRadialGradient(pt(nx, ny), nr * 2.3)
        glow.setColorAt(0.0, QColor(255, 255, 255, 250))
        glow.setColorAt(0.45, QColor(125, 211, 252, 195))
        glow.setColorAt(1.0, QColor(56, 189, 248, 0))
        painter.setBrush(glow)
        painter.drawEllipse(pt(nx, ny), nr * 2.3, nr * 2.3)
        painter.setBrush(QColor(255, 255, 255, 255))
        painter.drawEllipse(pt(nx, ny), nr * 0.72, nr * 0.72)

    # 14. Intelligence Spark / Four-Point Star comfortably inside upper-right quadrant (84, 17)
    spark_center = pt(83.5, 16.5)
    spark_glow = QRadialGradient(spark_center, 6.2)
    spark_glow.setColorAt(0.0, QColor(255, 255, 255, 235))
    spark_glow.setColorAt(0.45, QColor(56, 189, 248, 155))
    spark_glow.setColorAt(1.0, QColor(56, 189, 248, 0))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(spark_glow)
    painter.drawEllipse(spark_center, 6.2, 6.2)

    spark_star = poly(
        (83.5, 11.2),
        (84.8, 15.2),
        (88.8, 16.5),
        (84.8, 17.8),
        (83.5, 21.8),
        (82.2, 17.8),
        (78.2, 16.5),
        (82.2, 15.2),
    )
    painter.setBrush(QColor(255, 255, 255, 252))
    painter.drawPolygon(spark_star)

    painter.restore()


def render_colibri_pixmap(size: int = 128, draw_medallion: bool = True) -> QPixmap:
    """Render a supersampled high-DPI QPixmap of the Colibri AI Studio logo."""
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    paint_colibri_emblem(painter, QRectF(0, 0, float(size), float(size)), draw_medallion=draw_medallion)
    painter.end()
    return QPixmap.fromImage(image)


def build_colibri_window_icon() -> QIcon:
    """Build a multi-resolution QIcon directly from the vector renderer."""
    icon = QIcon()
    for sz in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(render_colibri_pixmap(sz, draw_medallion=True))
    return icon


def generate_svg_logo(output_path: Path) -> Path:
    """Write the scalable vector SVG master logo for Colibri AI Studio."""
    svg_content = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="512" height="512">
  <defs>
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0B1121"/>
      <stop offset="50%" stop-color="#060A14"/>
      <stop offset="100%" stop-color="#0D0C1C"/>
    </linearGradient>
    <linearGradient id="rimGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#7DD3FC" stop-opacity="0.85"/>
      <stop offset="50%" stop-color="#6366F1" stop-opacity="0.62"/>
      <stop offset="100%" stop-color="#C084FC" stop-opacity="0.80"/>
    </linearGradient>
    <linearGradient id="farWing" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#D8B4FE"/>
      <stop offset="50%" stop-color="#8B5CF6"/>
      <stop offset="100%" stop-color="#4338CA"/>
    </linearGradient>
    <linearGradient id="blade1" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#BAE6FD"/>
      <stop offset="45%" stop-color="#38BDF8"/>
      <stop offset="100%" stop-color="#0284C7"/>
    </linearGradient>
    <linearGradient id="blade2" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#38BDF8"/>
      <stop offset="55%" stop-color="#3B82F6"/>
      <stop offset="100%" stop-color="#2563EB"/>
    </linearGradient>
    <linearGradient id="blade3" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#60A5FA"/>
      <stop offset="55%" stop-color="#6366F1"/>
      <stop offset="100%" stop-color="#4F46E5"/>
    </linearGradient>
    <linearGradient id="blade4" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#C084FC"/>
      <stop offset="60%" stop-color="#8B5CF6"/>
      <stop offset="100%" stop-color="#581C87"/>
    </linearGradient>
    <linearGradient id="breastGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#67E8F9"/>
      <stop offset="45%" stop-color="#06B6D4"/>
      <stop offset="100%" stop-color="#1D4ED8"/>
    </linearGradient>
    <linearGradient id="spineGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#3B82F6"/>
      <stop offset="60%" stop-color="#4F46E5"/>
      <stop offset="100%" stop-color="#312E81"/>
    </linearGradient>
    <linearGradient id="tailLong" x1="100%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#6366F1"/>
      <stop offset="50%" stop-color="#A855F7"/>
      <stop offset="100%" stop-color="#EC4899"/>
    </linearGradient>
    <linearGradient id="beakGrad" x1="0%" y1="100%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#7DD3FC"/>
      <stop offset="100%" stop-color="#FFFFFF"/>
    </linearGradient>
  </defs>
  <rect x="3.5" y="3.5" width="93" height="93" rx="22.5" ry="22.5" fill="url(#bgGrad)" stroke="url(#rimGrad)" stroke-width="2.0"/>
  <circle cx="50" cy="50" r="37.5" fill="none" stroke="#38BDF8" stroke-opacity="0.14" stroke-width="0.75" stroke-dasharray="3,3"/>
  <g stroke="#E0F2FE" stroke-opacity="0.52" stroke-width="0.65">
    <polygon points="19,13 39,21 52,36 34,29" fill="url(#farWing)"/>
    <polygon points="11,19 33,24 52,39 35,36" fill="url(#blade1)"/>
    <polygon points="11,19 35,36 48,45 14,32" fill="url(#blade2)"/>
    <polygon points="14,32 48,45 45,51 19,43" fill="url(#blade3)"/>
    <polygon points="19,43 45,51 42,55 26,52" fill="url(#blade4)"/>
    <polygon points="52,36 61,27 70,31 61,38" fill="url(#blade1)"/>
    <polygon points="52,36 61,38 70,31 66,43 52,39" fill="url(#blade2)"/>
    <polygon points="70,31 88,22 68,36" fill="url(#beakGrad)"/>
    <polygon points="68,36 88,22 66,40" fill="url(#blade1)"/>
    <polygon points="52,39 66,43 59,57 48,45" fill="url(#breastGrad)"/>
    <polygon points="48,45 59,57 49,66 42,55 45,51" fill="url(#spineGrad)"/>
    <polygon points="42,55 49,66 39,72 36,61" fill="url(#blade3)"/>
    <polygon points="36,61 39,72 25,87 19,84" fill="url(#tailLong)"/>
    <polygon points="39,72 49,66 37,85 31,80" fill="url(#blade3)"/>
    <polygon points="44,69 49,66 48,82 42,77" fill="url(#blade2)"/>
  </g>
  <g stroke="#E0F2FE" stroke-opacity="0.6" stroke-width="0.75">
    <line x1="24" y1="26" x2="35" y2="36"/>
    <line x1="35" y1="36" x2="48" y2="45"/>
    <line x1="48" y1="45" x2="61.5" y2="34.5"/>
    <line x1="48" y1="45" x2="46" y2="60"/>
  </g>
  <g fill="#FFFFFF">
    <circle cx="24" cy="26" r="1.2"/>
    <circle cx="35" cy="36" r="1.3"/>
    <circle cx="48" cy="45" r="1.5"/>
    <circle cx="46" cy="60" r="1.2"/>
    <circle cx="61.5" cy="34.5" r="1.4"/>
    <polygon points="83.5,11.2 84.8,15.2 88.8,16.5 84.8,17.8 83.5,21.8 82.2,17.8 78.2,16.5 82.2,15.2"/>
  </g>
</svg>
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(svg_content.strip() + "\n", encoding="utf-8")
    return output_path


class ColibriLogoWidget(QWidget):
    """Live Vector Brand Emblem Widget for Colibri AI Studio."""

    def __init__(
        self,
        parent: QWidget | None = None,
        size: int = 44,
        draw_medallion: bool = True,
    ) -> None:
        super().__init__(parent)
        self._logo_size = size
        self._draw_medallion = draw_medallion
        self.setFixedSize(size, size)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def set_logo_size(self, size: int) -> None:
        self._logo_size = size
        self.setFixedSize(size, size)
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        paint_colibri_emblem(
            painter,
            QRectF(0.0, 0.0, float(self.width()), float(self.height())),
            draw_medallion=self._draw_medallion,
        )
        painter.end()
