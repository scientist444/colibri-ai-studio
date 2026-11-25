"""Conversation & Export Service (conversation_service.py)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.database.repositories import ConversationRepository


class ConversationService:
    """High-level conversation management and Markdown/JSON export."""

    def __init__(self, repo: ConversationRepository) -> None:
        self.repo = repo

    def ensure_default_conversation(self, default_system_prompt: str = "") -> dict[str, Any]:
        convs = self.repo.list_conversations()
        if convs:
            return convs[0]
        return self.repo.create_conversation(
            title="Welcome Conversation",
            system_prompt=default_system_prompt,
        )

    def export_conversation_markdown(self, conv_id: str, output_path: Path) -> Path:
        conv = self.repo.get_conversation(conv_id)
        if not conv:
            raise ValueError(f"Conversation {conv_id} not found.")
        messages = self.repo.get_messages(conv_id)

        lines = [
            f"# {conv['title']}",
            "",
            f"- **Model:** `{conv.get('model_id') or 'Local Colibri Model'}`",
            f"- **Created:** {conv.get('created_at', '')}",
            "",
        ]
        if conv.get("system_prompt"):
            lines.extend(["## System Prompt", "", f"> {conv['system_prompt']}", ""])

        lines.append("---")
        lines.append("")

        for msg in messages:
            role_title = "User" if msg["role"] == "user" else "Colibri Assistant"
            lines.append(f"### {role_title}")
            lines.append("")
            if msg.get("reasoning_content"):
                lines.append("<details><summary>Reasoning / Thought Process</summary>")
                lines.append("")
                lines.append(str(msg["reasoning_content"]))
                lines.append("")
                lines.append("</details>")
                lines.append("")
            lines.append(str(msg["content"]))
            lines.append("")
            if msg["role"] == "assistant" and (msg.get("tokens_per_sec") or msg.get("ttft_ms")):
                lines.append(
                    f"*Metrics: {float(msg.get('tokens_per_sec') or 0.0):.1f} tok/s | "
                    f"TTFT: {float(msg.get('ttft_ms') or 0.0):.0f} ms | "
                    f"Tokens: {int(msg.get('token_count') or 0)}*"
                )
                lines.append("")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("\n".join(lines), encoding="utf-8")
        return output_path

    def export_conversation_json(self, conv_id: str, output_path: Path) -> Path:
        conv = self.repo.get_conversation(conv_id)
        if not conv:
            raise ValueError(f"Conversation {conv_id} not found.")
        messages = self.repo.get_messages(conv_id)
        payload = {
            "conversation": conv,
            "messages": messages,
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return output_path
