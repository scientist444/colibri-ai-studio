"""Liquid Glass Chat Interface (`chat_view.py`) — Emoji-Free Professional Workstation Design."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.application_state import ApplicationState
from app.controllers.backend_controller import BackendController
from app.controllers.chat_controller import ChatController
from app.core.colibri_manager import BackendState
from app.models.model_metadata import InstalledModelRecord
from app.ui.liquid_glass import LiquidGlassPanel
from app.ui.widgets.brand_logo import ColibriLogoWidget
from app.ui.widgets.markdown_viewer import ChatMessageBubble
from app.ui.widgets.status_badge import StatusBadge


class ChatInputBox(QPlainTextEdit):
    """Multi-line Liquid Glass chat input supporting Enter to send and Shift+Enter for newline."""

    def __init__(self, on_submit: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._on_submit = on_submit
        self.setPlaceholderText("Enter a message for Colibri AI... (Press Enter to send, Shift+Enter for a new line)")
        self.setFixedHeight(78)

    def keyPressEvent(self, event: QKeyEvent | None) -> None:  # noqa: N802
        if event is not None and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                self._on_submit()
                event.accept()
                return
        super().keyPressEvent(event)


class ChatView(QWidget):
    """Main ChatGPT-inspired Liquid Glass conversational interface."""

    def __init__(
        self,
        app_state: ApplicationState,
        chat_controller: ChatController,
        backend_controller: BackendController,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.app_state = app_state
        self.chat_controller = chat_controller
        self.backend_controller = backend_controller

        self._active_conv_id: str = ""
        self._streaming_bubble: ChatMessageBubble | None = None
        self._stream_content_acc: str = ""
        self._stream_reasoning_acc: str = ""
        self._user_scrolled_up: bool = False

        self._build_ui()
        self._connect_signals()
        self.refresh_model_selector()
        self.load_conversations_list()

    def _build_ui(self) -> None:
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(12)

        # Left Panel: Liquid Glass Conversation History Sidebar
        self.conv_sidebar = LiquidGlassPanel(self, radius=16.0)
        self.conv_sidebar.setFixedWidth(265)
        side_layout = QVBoxLayout(self.conv_sidebar)
        side_layout.setContentsMargins(12, 12, 12, 12)
        side_layout.setSpacing(8)

        new_chat_btn = QPushButton("+  New Conversation")
        new_chat_btn.setObjectName("primaryGlassButton")
        new_chat_btn.setMinimumHeight(36)
        new_chat_btn.clicked.connect(self._create_new_conversation)
        side_layout.addWidget(new_chat_btn)

        self.search_conv_edit = QLineEdit()
        self.search_conv_edit.setPlaceholderText("Filter conversations...")
        self.search_conv_edit.textChanged.connect(self.load_conversations_list)
        side_layout.addWidget(self.search_conv_edit)

        self.conv_list = QListWidget()
        self.conv_list.currentItemChanged.connect(self._on_conversation_selected)
        side_layout.addWidget(self.conv_list, 1)

        # Conversation Actions Row
        conv_actions = QHBoxLayout()
        conv_actions.setSpacing(4)

        rename_btn = QPushButton("Rename")
        rename_btn.setStyleSheet("padding: 5px 8px; font-size: 11px;")
        rename_btn.clicked.connect(self._rename_current_conversation)
        conv_actions.addWidget(rename_btn)

        export_btn = QPushButton("Export")
        export_btn.setStyleSheet("padding: 5px 8px; font-size: 11px;")
        export_btn.clicked.connect(self._export_current_conversation)
        conv_actions.addWidget(export_btn)

        del_btn = QPushButton("Delete")
        del_btn.setObjectName("dangerGlassButton")
        del_btn.setStyleSheet("padding: 5px 8px; font-size: 11px;")
        del_btn.clicked.connect(self._delete_current_conversation)
        conv_actions.addWidget(del_btn)

        side_layout.addLayout(conv_actions)
        root_layout.addWidget(self.conv_sidebar)

        # Right Main Chat Workspace
        right_col = QVBoxLayout()
        right_col.setSpacing(10)

        # Top Liquid Glass Bar: Model Selector + Server Controls + Sampling Drawer Toggle
        top_bar = LiquidGlassPanel(self, radius=15.0, elevated=True)
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(14, 10, 14, 10)
        top_layout.setSpacing(10)

        model_lbl = QLabel("ACTIVE MODEL:")
        model_lbl.setStyleSheet("font-size: 11px; font-weight: 700; letter-spacing: 0.6px; color: #38BDF8;")
        top_layout.addWidget(model_lbl)

        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(240)
        top_layout.addWidget(self.model_combo, 1)

        self.start_server_btn = QPushButton("Load Model")
        self.start_server_btn.setObjectName("primaryGlassButton")
        self.start_server_btn.clicked.connect(self._start_selected_model)
        top_layout.addWidget(self.start_server_btn)

        self.stop_server_btn = QPushButton("Unload")
        self.stop_server_btn.setObjectName("dangerGlassButton")
        self.stop_server_btn.clicked.connect(self.backend_controller.stop_server_async)
        top_layout.addWidget(self.stop_server_btn)

        self.server_badge = StatusBadge("STANDBY", variant="info")
        top_layout.addWidget(self.server_badge)

        self.params_toggle_btn = QPushButton("Parameters & Prompt")
        self.params_toggle_btn.setCheckable(True)
        self.params_toggle_btn.toggled.connect(self._toggle_params_drawer)
        top_layout.addWidget(self.params_toggle_btn)

        right_col.addWidget(top_bar)

        # Collapsible Liquid Glass Parameters & System Prompt Tabs Drawer
        self.params_drawer = QTabWidget()
        self.params_drawer.setMaximumHeight(165)
        self.params_drawer.setVisible(False)

        # Tab 1: System Prompt
        prompt_tab = QWidget()
        p_layout = QVBoxLayout(prompt_tab)
        p_layout.setContentsMargins(8, 6, 8, 6)
        self.sys_prompt_edit = QPlainTextEdit(self.app_state.settings.default_system_prompt)
        self.sys_prompt_edit.setPlaceholderText("Enter system instructions for this conversation...")
        self.sys_prompt_edit.textChanged.connect(self._save_conversation_system_prompt)
        p_layout.addWidget(self.sys_prompt_edit)
        self.params_drawer.addTab(prompt_tab, "System Prompt")

        # Tab 2: Sampling & Generation Parameters
        sampling_tab = QWidget()
        s_layout = QHBoxLayout(sampling_tab)
        s_layout.setContentsMargins(10, 8, 10, 8)
        s_layout.setSpacing(14)

        s_layout.addWidget(QLabel("Temperature:"))
        self.temp_spin = QDoubleSpinBox()
        self.temp_spin.setRange(0.0, 2.0)
        self.temp_spin.setSingleStep(0.05)
        self.temp_spin.setValue(self.app_state.settings.default_temperature)
        s_layout.addWidget(self.temp_spin)

        s_layout.addWidget(QLabel("Top-P:"))
        self.top_p_spin = QDoubleSpinBox()
        self.top_p_spin.setRange(0.05, 1.0)
        self.top_p_spin.setSingleStep(0.05)
        self.top_p_spin.setValue(self.app_state.settings.default_top_p)
        s_layout.addWidget(self.top_p_spin)

        s_layout.addWidget(QLabel("Max Tokens:"))
        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(32, 32768)
        self.max_tokens_spin.setSingleStep(128)
        self.max_tokens_spin.setValue(self.app_state.settings.default_max_tokens)
        s_layout.addWidget(self.max_tokens_spin)
        s_layout.addStretch(1)
        self.params_drawer.addTab(sampling_tab, "Sampling Controls")

        # Tab 3: Reasoning & Context Compaction (Colibri Native Extensions)
        reasoning_tab = QWidget()
        r_layout = QHBoxLayout(reasoning_tab)
        r_layout.setContentsMargins(10, 8, 10, 8)
        r_layout.setSpacing(14)

        self.thinking_chk = QCheckBox("Enable Thinking (`enable_thinking`)")
        self.thinking_chk.setChecked(self.app_state.settings.enable_thinking)
        r_layout.addWidget(self.thinking_chk)

        r_layout.addWidget(QLabel("Reasoning Effort:"))
        self.effort_combo = QComboBox()
        self.effort_combo.addItems(["none", "minimal", "low", "medium", "high", "xhigh"])
        self.effort_combo.setCurrentText(self.app_state.settings.reasoning_effort)
        r_layout.addWidget(self.effort_combo)

        self.preserve_think_chk = QCheckBox("Preserve Thinking Across Turns (Qwen3.6)")
        self.preserve_think_chk.setChecked(self.app_state.settings.preserve_thinking)
        r_layout.addWidget(self.preserve_think_chk)
        r_layout.addStretch(1)
        self.params_drawer.addTab(reasoning_tab, "Reasoning & Thinking")

        right_col.addWidget(self.params_drawer)

        # Center Liquid Glass Messages Scroll Area
        self.messages_panel = LiquidGlassPanel(self, radius=16.0)
        msg_panel_layout = QVBoxLayout(self.messages_panel)
        msg_panel_layout.setContentsMargins(8, 8, 8, 8)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.verticalScrollBar().valueChanged.connect(self._on_scroll_value_changed)  # type: ignore[union-attr]

        self.messages_container = QWidget()
        self.messages_layout = QVBoxLayout(self.messages_container)
        self.messages_layout.setContentsMargins(10, 10, 10, 10)
        self.messages_layout.setSpacing(12)
        self.messages_layout.addStretch(1)

        self.scroll_area.setWidget(self.messages_container)
        msg_panel_layout.addWidget(self.scroll_area, 1)
        right_col.addWidget(self.messages_panel, 1)

        # Bottom Liquid Glass Composer Bar
        composer_panel = LiquidGlassPanel(self, radius=16.0, elevated=True)
        comp_layout = QVBoxLayout(composer_panel)
        comp_layout.setContentsMargins(14, 10, 14, 10)
        comp_layout.setSpacing(8)

        self.input_box = ChatInputBox(on_submit=self._send_message, parent=composer_panel)
        comp_layout.addWidget(self.input_box)

        action_row = QHBoxLayout()
        self.hint_lbl = QLabel("Local Private Inference  |  Zero data leaves your workstation")
        self.hint_lbl.setStyleSheet("font-size: 11px; color: #94A3B8;")
        action_row.addWidget(self.hint_lbl, 1)

        self.regen_btn = QPushButton("Regenerate")
        self.regen_btn.clicked.connect(self._regenerate_last)
        action_row.addWidget(self.regen_btn)

        self.stop_gen_btn = QPushButton("Stop Generation")
        self.stop_gen_btn.setObjectName("dangerGlassButton")
        self.stop_gen_btn.setVisible(False)
        self.stop_gen_btn.clicked.connect(self.chat_controller.stop_generation)
        action_row.addWidget(self.stop_gen_btn)

        self.send_btn = QPushButton("Send Message")
        self.send_btn.setObjectName("primaryGlassButton")
        self.send_btn.setMinimumHeight(34)
        self.send_btn.clicked.connect(self._send_message)
        action_row.addWidget(self.send_btn)

        comp_layout.addLayout(action_row)
        right_col.addWidget(composer_panel)

        root_layout.addLayout(right_col, 1)

    def _connect_signals(self) -> None:
        self.app_state.installed_models_changed.connect(lambda _: self.refresh_model_selector())
        self.app_state.process_manager.state_changed.connect(self._on_backend_state_changed)

        self.chat_controller.stream_started.connect(self._on_stream_started)
        self.chat_controller.stream_delta.connect(self._on_stream_delta)
        self.chat_controller.stream_compaction.connect(self._on_stream_compaction)
        self.chat_controller.stream_finished.connect(self._on_stream_finished)
        self.chat_controller.stream_error.connect(self._on_stream_error)

    def _toggle_params_drawer(self, checked: bool) -> None:
        self.params_drawer.setVisible(checked)

    def refresh_model_selector(self) -> None:
        installed: list[InstalledModelRecord] = self.app_state.models_repo.list_models()
        current_id = self.app_state.settings.active_model_id
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        if not installed:
            self.model_combo.addItem("No local models installed — Open Model Hub to download", ("", ""))
        else:
            selected_idx = 0
            for idx, rec in enumerate(installed):
                size_gb = rec.size_bytes / (1024**3)
                label = f"{rec.display_name} ({rec.family} | {size_gb:.1f} GB)"
                self.model_combo.addItem(label, (rec.model_id, rec.local_path))
                if rec.model_id == current_id:
                    selected_idx = idx
            self.model_combo.setCurrentIndex(selected_idx)
        self.model_combo.blockSignals(False)

    def _start_selected_model(self) -> None:
        data = self.model_combo.currentData()
        if not data or not data[0]:
            self.app_state.navigation_requested.emit("model_hub")
            return
        model_id, local_path = data
        self.backend_controller.start_model_async(model_id, local_path)

    def _on_backend_state_changed(self, state: str, detail: str) -> None:
        st = state.upper()
        if st == "RUNNING":
            self.server_badge.set_variant("green", "RUNNING")
        elif st in ("STARTING", "INSTALLING"):
            self.server_badge.set_variant("yellow", st)
        elif st in ("FAILED", "NOT_INSTALLED"):
            self.server_badge.set_variant("red", st)
        else:
            self.server_badge.set_variant("info", st)
        self.hint_lbl.setText(detail or "Local Private Inference")

    def load_conversations_list(self) -> None:
        query = self.search_conv_edit.text().strip()
        convs = self.app_state.conversations_repo.list_conversations(search_query=query)
        if not convs and not query:
            default_conv = self.app_state.conversation_service.ensure_default_conversation(
                self.app_state.settings.default_system_prompt
            )
            convs = [default_conv]

        self.conv_list.blockSignals(True)
        self.conv_list.clear()
        target_row = 0
        for idx, c in enumerate(convs):
            item = QListWidgetItem(str(c["title"]))
            item.setData(Qt.ItemDataRole.UserRole, c["id"])
            self.conv_list.addItem(item)
            if c["id"] == self._active_conv_id:
                target_row = idx
        self.conv_list.blockSignals(False)

        if self.conv_list.count() > 0:
            self.conv_list.setCurrentRow(target_row)
            cur_item = self.conv_list.item(target_row)
            if cur_item:
                self._load_conversation_messages(str(cur_item.data(Qt.ItemDataRole.UserRole)))

    def _on_conversation_selected(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        if current is None:
            return
        conv_id = str(current.data(Qt.ItemDataRole.UserRole))
        self._load_conversation_messages(conv_id)

    def _load_conversation_messages(self, conv_id: str) -> None:
        self._active_conv_id = conv_id
        conv = self.app_state.conversations_repo.get_conversation(conv_id)
        if conv:
            self.sys_prompt_edit.blockSignals(True)
            self.sys_prompt_edit.setPlainText(
                str(conv.get("system_prompt") or self.app_state.settings.default_system_prompt)
            )
            self.sys_prompt_edit.blockSignals(False)

        while self.messages_layout.count() > 1:
            item = self.messages_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        messages = self.app_state.conversations_repo.get_messages(conv_id)
        if not messages:
            empty_card = LiquidGlassPanel(self.messages_container, radius=16.0, elevated=True)
            e_layout = QHBoxLayout(empty_card)
            e_layout.setContentsMargins(24, 22, 24, 22)
            e_layout.setSpacing(20)

            hero_logo = ColibriLogoWidget(empty_card, size=74, draw_medallion=True)
            e_layout.addWidget(hero_logo)

            text_col = QVBoxLayout()
            text_col.setSpacing(6)
            welcome_title = QLabel("Colibri AI Studio — Ready for Local Inference")
            welcome_title.setStyleSheet("font-size: 16.5px; font-weight: 800; letter-spacing: 0.2px;")
            welcome_sub = QLabel(
                "01. Select an installed model in the top bar (or download one from Model Hub).\n"
                "02. Click 'Load Model' to start the local Colibri inference server.\n"
                "03. Enter a prompt below to stream responses with full Markdown and syntax highlighting."
            )
            welcome_sub.setWordWrap(True)
            welcome_sub.setStyleSheet("font-size: 13px; color: #94A3B8;")
            text_col.addWidget(welcome_title)
            text_col.addWidget(welcome_sub)
            e_layout.addLayout(text_col, 1)

            self.messages_layout.insertWidget(0, empty_card)
            return

        for m in messages:
            metrics = ""
            if m["role"] == "assistant" and (m.get("tokens_per_sec") or m.get("ttft_ms")):
                metrics = (
                    f"{float(m.get('tokens_per_sec') or 0.0):.1f} tok/s  |  "
                    f"TTFT: {float(m.get('ttft_ms') or 0.0):.0f} ms  |  "
                    f"Tokens: {int(m.get('token_count') or 0)}"
                )
            bubble = ChatMessageBubble(
                role=str(m["role"]),
                content=str(m["content"]),
                reasoning_content=str(m.get("reasoning_content") or ""),
                metrics_text=metrics,
                parent=self.messages_container,
            )
            self.messages_layout.insertWidget(self.messages_layout.count() - 1, bubble)

        QTimer.singleShot(50, self._scroll_to_bottom_force)

    def _create_new_conversation(self) -> None:
        conv = self.app_state.conversations_repo.create_conversation(
            title="New Conversation",
            model_id=self.app_state.settings.active_model_id,
            system_prompt=self.app_state.settings.default_system_prompt,
        )
        self._active_conv_id = str(conv["id"])
        self.load_conversations_list()

    def _rename_current_conversation(self) -> None:
        if not self._active_conv_id:
            return
        conv = self.app_state.conversations_repo.get_conversation(self._active_conv_id)
        if not conv:
            return
        new_title, ok = QInputDialog.getText(
            self,
            "Rename Conversation",
            "Conversation Title:",
            text=str(conv.get("title") or ""),
        )
        if ok and new_title.strip():
            self.app_state.conversations_repo.rename_conversation(self._active_conv_id, new_title.strip())
            self.load_conversations_list()

    def _delete_current_conversation(self) -> None:
        if not self._active_conv_id:
            return
        reply = QMessageBox.question(
            self,
            "Delete Conversation",
            "Delete this conversation and its message history?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.app_state.conversations_repo.delete_conversation(self._active_conv_id)
            self._active_conv_id = ""
            self.load_conversations_list()

    def _export_current_conversation(self) -> None:
        if not self._active_conv_id:
            return
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Conversation",
            "colibri_conversation.md",
            "Markdown (*.md);;JSON (*.json)",
        )
        if not file_path:
            return
        out = Path(file_path)
        if "json" in selected_filter.lower() or out.suffix.lower() == ".json":
            self.app_state.conversation_service.export_conversation_json(self._active_conv_id, out)
        else:
            self.app_state.conversation_service.export_conversation_markdown(self._active_conv_id, out)
        QMessageBox.information(self, "Export Complete", f"Conversation exported to:\n{out}")

    def _save_conversation_system_prompt(self) -> None:
        if not self._active_conv_id:
            return
        self.app_state.conversations_repo.update_conversation_settings(
            self._active_conv_id,
            system_prompt=self.sys_prompt_edit.toPlainText().strip(),
        )

    def _send_message(self) -> None:
        if self.chat_controller.is_streaming:
            return
        text = self.input_box.toPlainText().strip()
        if not text:
            return

        if self.app_state.process_manager.state != BackendState.RUNNING:
            QMessageBox.information(
                self,
                "Model Server Not Running",
                "Please load an installed model using 'Load Model' in the top bar (or verify that a local Colibri server is running) before sending a message.",
            )
            return

        if not self._active_conv_id:
            self._create_new_conversation()

        self.input_box.clear()

        if (
            self.messages_layout.count() == 2
            and not isinstance(self.messages_layout.itemAt(0).widget(), ChatMessageBubble)  # type: ignore[union-attr]
        ):
            w = self.messages_layout.takeAt(0).widget()  # type: ignore[union-attr]
            if w:
                w.deleteLater()

        user_bubble = ChatMessageBubble(
            role="user",
            content=text,
            parent=self.messages_container,
        )
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, user_bubble)
        self._user_scrolled_up = False
        self._scroll_to_bottom_force()

        self.chat_controller.send_user_message(
            conversation_id=self._active_conv_id,
            user_text=text,
            temperature=self.temp_spin.value(),
            top_p=self.top_p_spin.value(),
            max_tokens=self.max_tokens_spin.value(),
            enable_thinking=self.thinking_chk.isChecked(),
            reasoning_effort=self.effort_combo.currentText(),
            preserve_thinking=self.preserve_think_chk.isChecked(),
        )

    def _regenerate_last(self) -> None:
        if not self._active_conv_id or self.chat_controller.is_streaming:
            return
        if self.app_state.process_manager.state != BackendState.RUNNING:
            return
        if self.messages_layout.count() > 1:
            last_idx = self.messages_layout.count() - 2
            w = self.messages_layout.itemAt(last_idx).widget()  # type: ignore[union-attr]
            if isinstance(w, ChatMessageBubble) and w.role == "assistant":
                self.messages_layout.takeAt(last_idx)
                w.deleteLater()

        self.chat_controller.regenerate_last_response(
            conversation_id=self._active_conv_id,
            temperature=self.temp_spin.value(),
            top_p=self.top_p_spin.value(),
            max_tokens=self.max_tokens_spin.value(),
            enable_thinking=self.thinking_chk.isChecked(),
            reasoning_effort=self.effort_combo.currentText(),
            preserve_thinking=self.preserve_think_chk.isChecked(),
        )

    def _on_stream_started(self, _conv_id: str) -> None:
        self.send_btn.setEnabled(False)
        self.regen_btn.setEnabled(False)
        self.stop_gen_btn.setVisible(True)
        self._stream_content_acc = ""
        self._stream_reasoning_acc = ""

        self._streaming_bubble = ChatMessageBubble(
            role="assistant",
            content="|",
            metrics_text="Streaming from local Colibri engine...",
            parent=self.messages_container,
        )
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, self._streaming_bubble)
        self._scroll_to_bottom_if_sticky()

    def _on_stream_delta(self, content_delta: str, reasoning_delta: str) -> None:
        self._stream_content_acc += content_delta
        self._stream_reasoning_acc += reasoning_delta
        if self._streaming_bubble is not None:
            self._streaming_bubble.set_content(
                content=self._stream_content_acc + " |",
                reasoning_content=self._stream_reasoning_acc,
                metrics_text="Streaming...",
            )
            self._scroll_to_bottom_if_sticky()

    def _on_stream_compaction(self, info: dict[str, Any]) -> None:
        dropped = info.get("dropped_messages", 0)
        self.hint_lbl.setText(f"Context automatically compacted ({dropped} older messages summarized).")

    def _on_stream_finished(self, saved_msg: dict[str, Any]) -> None:
        self.send_btn.setEnabled(True)
        self.regen_btn.setEnabled(True)
        self.stop_gen_btn.setVisible(False)

        metrics = (
            f"{float(saved_msg.get('tokens_per_sec') or 0.0):.1f} tok/s  |  "
            f"TTFT: {float(saved_msg.get('ttft_ms') or 0.0):.0f} ms  |  "
            f"Tokens: {int(saved_msg.get('token_count') or 0)}"
        )
        if self._streaming_bubble is not None:
            self._streaming_bubble.set_content(
                content=str(saved_msg.get("content") or ""),
                reasoning_content=str(saved_msg.get("reasoning_content") or ""),
                metrics_text=metrics,
            )
            self._streaming_bubble = None
        self.load_conversations_list()

    def _on_stream_error(self, title: str, body: str) -> None:
        self.send_btn.setEnabled(True)
        self.regen_btn.setEnabled(True)
        self.stop_gen_btn.setVisible(False)
        if self._streaming_bubble is not None:
            self._streaming_bubble.set_content(
                content=f"**{title}**\n\n{body}",
                metrics_text="Generation failed",
            )
            self._streaming_bubble = None

    def _on_scroll_value_changed(self, value: int) -> None:
        bar = self.scroll_area.verticalScrollBar()
        if bar is None:
            return
        self._user_scrolled_up = (bar.maximum() - value) > 45

    def _scroll_to_bottom_if_sticky(self) -> None:
        if not self._user_scrolled_up:
            self._scroll_to_bottom_force()

    def _scroll_to_bottom_force(self) -> None:
        bar = self.scroll_area.verticalScrollBar()
        if bar is not None:
            bar.setValue(bar.maximum())
