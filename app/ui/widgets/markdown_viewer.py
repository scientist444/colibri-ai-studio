"""Safe Markdown + Pygments Syntax Highlighting Chat Message Widget (Emoji-Free)."""

from __future__ import annotations

import html
import re
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from markdown_it import MarkdownIt
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import TextLexer, get_lexer_by_name

from app.ui.liquid_glass import MONO_FONT_FAMILY, LiquidGlassPanel, get_active_theme

_MD = MarkdownIt("commonmark", {"html": False, "breaks": True}).enable("table").enable("strikethrough")
_CODE_BLOCK_RE = re.compile(r"```([a-zA-Z0-9_+\-]*)\n(.*?)```", re.DOTALL)


def render_safe_markdown_html(markdown_text: str) -> str:
    """Render untrusted model Markdown safely (HTML disabled) with Pygments code highlighting."""
    if not markdown_text:
        return ""
    formatter = HtmlFormatter(nowrap=True, style="monokai")
    t = get_active_theme()
    fg = t.get("text_primary", "#F8FAFC")

    def _highlight_code(
        _renderer: object,
        tokens: object,
        idx: int,
        _options: object,
        _env: object,
    ) -> str:
        token = tokens[idx]  # type: ignore[index]
        info = str(token.info or "").strip().split()[0] if token.info else ""
        code = str(token.content or "")
        try:
            lexer = get_lexer_by_name(info) if info else TextLexer()
        except Exception:
            lexer = TextLexer()
        highlighted = highlight(code, lexer, formatter)
        lang_badge = html.escape(info.upper() or "CODE")
        return (
            f'<div style="background-color: rgba(9, 13, 24, 0.90); '
            f'border: 1px solid rgba(125, 211, 252, 0.28); border-radius: 8px; '
            f'padding: 9px 12px; margin: 6px 0; font-family: {MONO_FONT_FAMILY}; font-size: 12px;">'
            f'<div style="color: #38BDF8; font-size: 10px; font-weight: 700; letter-spacing: 0.6px; margin-bottom: 4px;">{lang_badge}</div>'
            f'<pre style="margin: 0; white-space: pre-wrap; color: #F8FAFC;">{highlighted}</pre>'
            f"</div>"
        )

    _MD.add_render_rule("fence", _highlight_code)
    rendered = _MD.render(markdown_text)
    return (
        f'<div style="color: {fg}; font-size: 13px; line-height: 1.58;">'
        f"{rendered}"
        "</div>"
    )


def extract_code_blocks(markdown_text: str) -> list[tuple[str, str]]:
    """Return list of `(language, code_string)` blocks from markdown text."""
    return [(m.group(1) or "code", m.group(2).strip()) for m in _CODE_BLOCK_RE.finditer(markdown_text)]


class ChatMessageBubble(LiquidGlassPanel):
    """Liquid Glass chat message bubble with collapsible `<think>` reasoning and copy buttons."""

    def __init__(
        self,
        role: str,
        content: str = "",
        reasoning_content: str = "",
        metrics_text: str = "",
        parent: QWidget | None = None,
    ) -> None:
        is_user = role == "user"
        super().__init__(parent=parent, radius=15.0, tint_color=None, elevated=is_user)
        self.role = role
        self._raw_content = content
        self._raw_reasoning = reasoning_content

        self._build_ui(metrics_text)
        self.set_content(content, reasoning_content, metrics_text)

    def _build_ui(self, metrics_text: str) -> None:
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(16, 12, 16, 12)
        self.main_layout.setSpacing(8)

        # Header Row: Role badge + Copy Full Message button
        header_row = QHBoxLayout()
        role_title = "USER" if self.role == "user" else "COLIBRI AI"
        role_color = "#38BDF8" if self.role == "user" else "#818CF8"
        self.role_lbl = QLabel(role_title)
        self.role_lbl.setStyleSheet(
            f"font-size: 11px; font-weight: 800; letter-spacing: 0.7px; color: {role_color};"
        )
        header_row.addWidget(self.role_lbl)

        header_row.addStretch(1)

        self.toggle_think_btn = QPushButton("Show Reasoning")
        self.toggle_think_btn.setFixedHeight(24)
        self.toggle_think_btn.setStyleSheet("font-size: 11px; padding: 2px 10px;")
        self.toggle_think_btn.setVisible(False)
        self.toggle_think_btn.clicked.connect(self._toggle_reasoning)
        header_row.addWidget(self.toggle_think_btn)

        self.copy_msg_btn = QPushButton("Copy Text")
        self.copy_msg_btn.setFixedHeight(24)
        self.copy_msg_btn.setStyleSheet("font-size: 11px; padding: 2px 10px;")
        self.copy_msg_btn.clicked.connect(self._copy_full_message)
        header_row.addWidget(self.copy_msg_btn)
        self.main_layout.addLayout(header_row)

        # Collapsible Reasoning Panel
        self.reasoning_panel = LiquidGlassPanel(self, radius=10.0)
        self.reasoning_panel.setVisible(False)
        r_layout = QVBoxLayout(self.reasoning_panel)
        r_layout.setContentsMargins(10, 8, 10, 8)
        self.reasoning_lbl = QLabel()
        self.reasoning_lbl.setWordWrap(True)
        self.reasoning_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.reasoning_lbl.setStyleSheet("font-size: 12px; color: #94A3B8; font-style: italic;")
        r_layout.addWidget(self.reasoning_lbl)
        self.main_layout.addWidget(self.reasoning_panel)

        # Main Markdown Content Label
        self.content_lbl = QLabel()
        self.content_lbl.setWordWrap(True)
        self.content_lbl.setTextFormat(Qt.TextFormat.RichText)
        self.content_lbl.setOpenExternalLinks(True)
        self.content_lbl.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.LinksAccessibleByMouse
        )
        self.main_layout.addWidget(self.content_lbl)

        # Code block quick-copy buttons row
        self.code_buttons_layout = QHBoxLayout()
        self.code_buttons_layout.setSpacing(6)
        self.main_layout.addLayout(self.code_buttons_layout)

        # Footer metrics label
        self.metrics_lbl = QLabel(metrics_text)
        self.metrics_lbl.setStyleSheet(f"font-family: {MONO_FONT_FAMILY}; font-size: 11px; color: #64748B;")
        self.metrics_lbl.setVisible(bool(metrics_text))
        self.main_layout.addWidget(self.metrics_lbl)

    def set_content(
        self,
        content: str,
        reasoning_content: str = "",
        metrics_text: str = "",
    ) -> None:
        self._raw_content = content
        self._raw_reasoning = reasoning_content

        if reasoning_content.strip():
            self.toggle_think_btn.setVisible(True)
            self.reasoning_lbl.setText(reasoning_content.strip())
        else:
            self.toggle_think_btn.setVisible(False)
            self.reasoning_panel.setVisible(False)

        self.content_lbl.setText(render_safe_markdown_html(content))

        while self.code_buttons_layout.count():
            item = self.code_buttons_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        blocks = extract_code_blocks(content)
        if blocks:
            for idx, (lang, code_str) in enumerate(blocks, 1):
                btn = QPushButton(f"Copy {lang.upper()} #{idx}")
                btn.setFixedHeight(24)
                btn.setStyleSheet("font-size: 11px; padding: 2px 9px;")
                btn.clicked.connect(lambda _c, s=code_str: self._copy_text(s))
                self.code_buttons_layout.addWidget(btn)
            self.code_buttons_layout.addStretch(1)

        if metrics_text:
            self.metrics_lbl.setText(metrics_text)
            self.metrics_lbl.setVisible(True)

    def _toggle_reasoning(self) -> None:
        vis = not self.reasoning_panel.isVisible()
        self.reasoning_panel.setVisible(vis)
        self.toggle_think_btn.setText("Hide Reasoning" if vis else "Show Reasoning")

    def _copy_full_message(self) -> None:
        self._copy_text(self._raw_content)

    @staticmethod
    def _copy_text(text: str) -> None:
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)
