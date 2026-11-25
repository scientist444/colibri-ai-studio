"""PyQt6 GUI, Multi-Theme Liquid Glass & Emoji-Free Verification Tests (`tests/test_gui.py`)."""

from __future__ import annotations

from pathlib import Path
from pytestqt.qtbot import QtBot

from app.application_state import ApplicationState
from app.ui.liquid_glass import LIQUID_GLASS_THEMES, get_active_theme_key
from app.ui.main_window import MainWindow
from app.ui.views.onboarding_view import OnboardingWizardDialog
from app.ui.widgets.brand_logo import (
    ColibriLogoWidget,
    build_colibri_window_icon,
    render_colibri_pixmap,
)
from app.ui.widgets.markdown_viewer import ChatMessageBubble, render_safe_markdown_html
from app.utils.paths import get_assets_dir


def test_safe_markdown_and_syntax_highlighting_escapes_raw_html() -> None:
    md = "Here is Python code:\n```python\ndef add(a: int, b: int) -> int:\n    return a + b\n```\n<script>alert('xss')</script>"
    rendered = render_safe_markdown_html(md)
    assert "PYTHON" in rendered
    assert "<script>" not in rendered
    assert "&lt;script&gt;" in rendered


def test_main_window_liquid_glass_views_navigation_and_themes(qtbot: QtBot, tmp_path: Path) -> None:
    app_state = ApplicationState(
        db_path=tmp_path / "gui_test.db",
        settings_path=tmp_path / "settings.json",
    )
    app_state.settings_service.update(
        first_run_completed=True,
        models_dir=str(tmp_path / "models"),
        engine_dir=str(tmp_path / "engine"),
    )

    window = MainWindow(app_state=app_state)
    qtbot.addWidget(window)
    window.show()

    # Verify navigation across all 6 Liquid Glass primary views
    for view_key in ("chat", "model_hub", "my_models", "hardware", "performance", "settings"):
        window.switch_view(view_key)
        assert window.sidebar._active_key == view_key

    # Verify switching across all 5 Liquid Glass themes
    assert len(LIQUID_GLASS_THEMES) >= 5
    for theme_key in LIQUID_GLASS_THEMES:
        window.apply_and_persist_theme(theme_key)
        assert get_active_theme_key() == theme_key
        assert window.app_state.settings.theme == theme_key

    # Test sidebar collapse / expand
    window.sidebar.toggle_collapsed()
    assert window.sidebar._collapsed is True
    window.sidebar.toggle_collapsed()
    assert window.sidebar._collapsed is False

    # Verify Model Hub loaded the official Colibri catalog cards
    assert window.model_hub_view.catalog_cards_layout.count() > 5

    # Verify Chat message bubble creation
    bubble = ChatMessageBubble(
        role="assistant",
        content="```python\nprint('Colibri')\n```",
        reasoning_content="Evaluating expert routing...",
        metrics_text="25.0 tok/s",
    )
    qtbot.addWidget(bubble)
    bubble.show()
    assert bubble.toggle_think_btn.isVisible() is True

    window.close()


def test_onboarding_wizard_dialog_tabs(qtbot: QtBot, tmp_path: Path) -> None:
    app_state = ApplicationState(
        db_path=tmp_path / "wiz_test.db",
        settings_path=tmp_path / "wiz_settings.json",
    )
    app_state.settings_service.update(first_run_completed=True)
    window = MainWindow(app_state=app_state)
    qtbot.addWidget(window)

    wizard = OnboardingWizardDialog(
        app_state=app_state,
        backend_controller=window.backend_controller,
        parent=window,
    )
    qtbot.addWidget(wizard)
    assert wizard.tabs.count() == 3
    wizard._go_next_tab()
    assert wizard.tabs.currentIndex() == 1
    wizard._go_next_tab()
    assert wizard.tabs.currentIndex() == 2
    wizard._go_prev_tab()
    assert wizard.tabs.currentIndex() == 1
    wizard.close()
    window.close()


def test_no_emojis_in_ui_codebase() -> None:
    """Ensure professional workstation UI modules contain zero pictographic emojis."""
    ui_root = Path(__file__).resolve().parent.parent / "app" / "ui"
    for py_file in ui_root.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        for ch in text:
            cp = ord(ch)
            # Emoji & Supplementary Pictographic blocks
            assert not (0x1F300 <= cp <= 0x1FAFF), f"Emoji character U+{cp:04X} found in {py_file.name}"


def test_colibri_brand_logo_widget_and_assets(qtbot: QtBot) -> None:
    """Verify the Colibri Hummingbird vector logo widget, pixmap renderer, window icon, and disk assets."""
    logo = ColibriLogoWidget(size=64, draw_medallion=True)
    qtbot.addWidget(logo)
    logo.show()
    assert logo.width() == 64
    logo.set_logo_size(40)
    assert logo.width() == 40

    pix = render_colibri_pixmap(size=128, draw_medallion=True)
    assert not pix.isNull()
    assert pix.width() == 128

    icon = build_colibri_window_icon()
    assert not icon.isNull()

    icons_dir = get_assets_dir() / "icons"
    assert (icons_dir / "colibri_logo.svg").exists()
    assert (icons_dir / "colibri_logo_512.png").exists()
    assert (icons_dir / "app_icon.ico").exists()
