"""Generate Official Colibri AI Studio Logo Assets (`scripts/generate_logo.py`).

Produces:
- `assets/icons/colibri_logo.svg`     — Scalable vector master logo
- `assets/icons/colibri_logo_512.png` — 512x512 supersampled master PNG
- `assets/icons/app_icon.ico`         — Multi-resolution Windows icon (16, 24, 32, 48, 64, 128, 256)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image  # noqa: E402
from PyQt6.QtGui import QGuiApplication  # noqa: E402

from app.ui.widgets.brand_logo import (  # noqa: E402
    generate_svg_logo,
    render_colibri_pixmap,
)


def generate_all_logo_assets() -> dict[str, Path]:
    app = QGuiApplication.instance() or QGuiApplication(sys.argv)
    _ = app

    icons_dir = ROOT_DIR / "assets" / "icons"
    icons_dir.mkdir(parents=True, exist_ok=True)

    svg_path = generate_svg_logo(icons_dir / "colibri_logo.svg")

    # Render at 1024x1024 and downsample to 512x512 for razor-sharp edges
    pix_1024 = render_colibri_pixmap(size=1024, draw_medallion=True)
    tmp_1024 = icons_dir / "_tmp_1024.png"
    pix_1024.save(str(tmp_1024), "PNG")

    master_img = Image.open(tmp_1024).convert("RGBA")
    img_512 = master_img.resize((512, 512), Image.Resampling.LANCZOS)
    png_512_path = icons_dir / "colibri_logo_512.png"
    img_512.save(png_512_path, format="PNG")

    ico_path = icons_dir / "app_icon.ico"
    ico_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    master_img.save(ico_path, format="ICO", sizes=ico_sizes)

    try:
        tmp_1024.unlink(missing_ok=True)
    except OSError:
        pass

    return {
        "svg": svg_path,
        "png_512": png_512_path,
        "ico": ico_path,
    }


if __name__ == "__main__":
    paths = generate_all_logo_assets()
    for k, p in paths.items():
        print(f"{k}: {p} ({p.stat().st_size} bytes)")
