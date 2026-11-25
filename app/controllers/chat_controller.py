"""Chat Controller handling streaming inference, cancellation, and conversation persistence."""

from __future__ import annotations

import logging
import threading
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal

from app.application_state import ApplicationState
from app.core.colibri_api import StreamCompletionResult, StreamDeltaEvent
from app.core.error_handler import classify_exception
from app.utils.threading_utils import run_in_background

logger = logging.getLogger(__name__)


class ChatController(QObject):
    """Coordinates chat message streaming and conversation history."""

    stream_started = pyqtSignal(str)                 # conversation_id
    stream_delta = pyqtSignal(str, str)              # (content_delta, reasoning_delta)
    stream_compaction = pyqtSignal(dict)             # compaction_info
    stream_finished = pyqtSignal(object)             # dict (saved assistant message)
    stream_error = pyqtSignal(str, str)              # (friendly_title, friendly_body)

    def __init__(self, app_state: ApplicationState) -> None:
        super().__init__()
        self.app_state = app_state
        self._cancel_event = threading.Event()
        self._is_streaming = False

    @property
    def is_streaming(self) -> bool:
        return self._is_streaming

    def stop_generation(self) -> None:
        """Signal the active streaming request to cancel immediately."""
        self._cancel_event.set()

    def send_user_message(
        self,
        conversation_id: str,
        user_text: str,
        temperature: float | None = None,
        top_p: float | None = None,
        max_tokens: int | None = None,
        enable_thinking: bool | None = None,
        reasoning_effort: str | None = None,
        preserve_thinking: bool | None = None,
    ) -> dict[str, Any]:
        """Persist user message and start background SSE streaming from Colibri."""
        saved_user = self.app_state.conversations_repo.add_message(
            conversation_id=conversation_id,
            role="user",
            content=user_text,
            model_id=self.app_state.settings.active_model_id,
        )

        # Auto-title new conversations from the first user prompt
        conv = self.app_state.conversations_repo.get_conversation(conversation_id)
        if conv and conv.get("title") in ("New Conversation", "Welcome Conversation"):
            all_msgs = self.app_state.conversations_repo.get_messages(conversation_id)
            if len(all_msgs) <= 1:
                short_title = user_text.strip().splitlines()[0][:44]
                if len(user_text.strip()) > 44:
                    short_title += "…"
                self.app_state.conversations_repo.rename_conversation(conversation_id, short_title)

        self._start_assistant_stream(
            conversation_id=conversation_id,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            enable_thinking=enable_thinking,
            reasoning_effort=reasoning_effort,
            preserve_thinking=preserve_thinking,
        )
        return saved_user

    def regenerate_last_response(
        self,
        conversation_id: str,
        temperature: float | None = None,
        top_p: float | None = None,
        max_tokens: int | None = None,
        enable_thinking: bool | None = None,
        reasoning_effort: str | None = None,
        preserve_thinking: bool | None = None,
    ) -> None:
        """Delete the last assistant message in `conversation_id` and re-run generation."""
        if self._is_streaming:
            return
        self.app_state.conversations_repo.delete_last_assistant_message(conversation_id)
        self._start_assistant_stream(
            conversation_id=conversation_id,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            enable_thinking=enable_thinking,
            reasoning_effort=reasoning_effort,
            preserve_thinking=preserve_thinking,
        )

    def _start_assistant_stream(
        self,
        conversation_id: str,
        temperature: float | None,
        top_p: float | None,
        max_tokens: int | None,
        enable_thinking: bool | None,
        reasoning_effort: str | None,
        preserve_thinking: bool | None,
    ) -> None:
        self._cancel_event.clear()
        self._is_streaming = True
        self.stream_started.emit(conversation_id)

        settings = self.app_state.settings
        conv = self.app_state.conversations_repo.get_conversation(conversation_id) or {}
        sys_prompt = str(conv.get("system_prompt") or settings.default_system_prompt).strip()
        history = self.app_state.conversations_repo.get_messages(conversation_id)

        api_messages: list[dict[str, str]] = []
        if sys_prompt:
            api_messages.append({"role": "system", "content": sys_prompt})
        for m in history:
            api_messages.append({"role": str(m["role"]), "content": str(m["content"])})

        eff_temp = temperature if temperature is not None else settings.default_temperature
        eff_top_p = top_p if top_p is not None else settings.default_top_p
        eff_max_tok = max_tokens if max_tokens is not None else settings.default_max_tokens
        eff_think = enable_thinking if enable_thinking is not None else settings.enable_thinking
        eff_effort = reasoning_effort if reasoning_effort is not None else settings.reasoning_effort
        eff_preserve = preserve_thinking if preserve_thinking is not None else settings.preserve_thinking
        model_id = settings.active_model_id or "colibri"

        def _worker() -> StreamCompletionResult:
            client = self.app_state.process_manager.get_api_client()

            def _on_delta(ev: StreamDeltaEvent) -> None:
                if ev.content_delta or ev.reasoning_delta:
                    self.stream_delta.emit(ev.content_delta, ev.reasoning_delta)
                if ev.compaction_info:
                    self.stream_compaction.emit(ev.compaction_info)

            return client.stream_chat_completion(
                messages=api_messages,
                model=model_id,
                temperature=eff_temp,
                top_p=eff_top_p,
                max_tokens=eff_max_tok,
                stop=settings.stop_sequences or None,
                enable_thinking=eff_think,
                reasoning_effort=eff_effort,
                preserve_thinking=eff_preserve,
                context_compaction=settings.context_compaction,
                on_delta=_on_delta,
                should_cancel=self._cancel_event.is_set,
            )

        def _on_result(res: StreamCompletionResult) -> None:
            self._is_streaming = False
            content_to_save = res.content
            if res.was_cancelled and not content_to_save.strip():
                content_to_save = "*(Generation stopped by user)*"
            saved_msg = self.app_state.conversations_repo.add_message(
                conversation_id=conversation_id,
                role="assistant",
                content=content_to_save,
                reasoning_content=res.reasoning_content,
                model_id=model_id,
                tokens_per_sec=res.tokens_per_sec,
                ttft_ms=res.ttft_ms,
                token_count=res.completion_tokens,
            )
            self.stream_finished.emit(saved_msg)

        def _on_error(err_msg: str, _tb: str) -> None:
            self._is_streaming = False
            friendly = classify_exception(err_msg, context="Chat Inference")
            self.stream_error.emit(
                friendly.title,
                f"{friendly.summary}\n\nRecovery Steps:\n{friendly.recovery_guidance}",
            )

        run_in_background(_worker, on_result=_on_result, on_error=_on_error)
