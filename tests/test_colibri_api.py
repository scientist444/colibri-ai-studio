"""Tests for Colibri HTTP & Incremental SSE Streaming Client (`app/core/colibri_api.py`)."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from app.core.colibri_api import ColibriApiClient, IncrementalSseParser


def test_incremental_sse_parser_arbitrary_chunk_and_utf8_boundaries() -> None:
    parser = IncrementalSseParser()

    # Construct an SSE stream with multi-byte UTF-8 characters and split across mid-byte boundaries
    frame1 = 'data: {"choices": [{"delta": {"reasoning_content": "Analyzing hardware..."}, "finish_reason": null}]}\n\n'
    frame2 = 'data: {"choices": [{"delta": {"content": "Hello Colibri — local AI!"}, "finish_reason": null}]}\n\n'
    frame3 = 'data: {"compaction": {"dropped_messages": 2}, "usage": {"completion_tokens": 7, "prompt_tokens": 12}}\n\n'
    frame4 = "data: [DONE]\n\n"
    full_bytes = (frame1 + frame2 + frame3 + frame4).encode("utf-8")

    # Feed 5 bytes at a time to stress-test multi-byte UTF-8 and partial line framing
    events = []
    for i in range(0, len(full_bytes), 5):
        chunk = full_bytes[i : i + 5]
        events.extend(parser.feed_bytes(chunk, final=(i + 5 >= len(full_bytes))))

    content = "".join(e.content_delta for e in events)
    reasoning = "".join(e.reasoning_delta for e in events)
    compactions = [e.compaction_info for e in events if e.compaction_info]
    usages = [e.usage for e in events if e.usage]
    done_flags = [e.is_done for e in events if e.is_done]

    assert content == "Hello Colibri — local AI!"
    assert reasoning == "Analyzing hardware..."
    assert len(compactions) == 1
    assert compactions[0]["dropped_messages"] == 2
    assert len(usages) == 1
    assert usages[0]["completion_tokens"] == 7
    assert len(done_flags) == 1


def test_incremental_sse_parser_inline_think_tags_and_malformed_lines() -> None:
    parser = IncrementalSseParser()
    raw = (
        ": keep-alive comment\n"
        "data: {malformed_json_ignored}\n"
        'data: {"choices": [{"delta": {"content": "<think>step 1</think>Final answer"}}]}\n\n'
        "data: [DONE]\n\n"
    )
    events = parser.feed_text(raw, final=True)
    content = "".join(e.content_delta for e in events)
    reasoning = "".join(e.reasoning_delta for e in events)
    assert reasoning == "step 1"
    assert content == "Final answer"


class _MockColibriServerHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        pass

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "arch": "qwen3_moe"}).encode("utf-8"))
        elif self.path == "/v1/models":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"data": [{"id": "qwen3-coder-30b", "context_length": 4096}]}).encode("utf-8"))
        elif self.path == "/metrics":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"colibri_scheduler_active_slots 1.0\n")
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/v1/chat/completions":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            tokens = ["Colibri ", "streams ", "tokens ", "locally!"]
            for tok in tokens:
                frame = f'data: {{"choices": [{{"delta": {{"content": "{tok}"}}}}]}}\n\n'
                self.wfile.write(frame.encode("utf-8"))
                self.wfile.flush()
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()


def test_colibri_api_client_against_local_mock_server() -> None:
    server = HTTPServer(("127.0.0.1", 0), _MockColibriServerHandler)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        client = ColibriApiClient(host="127.0.0.1", port=port)
        ok, health = client.check_health()
        assert ok is True
        assert health["arch"] == "qwen3_moe"

        models = client.list_models()
        assert len(models) == 1
        assert models[0]["id"] == "qwen3-coder-30b"

        metrics = client.get_prometheus_metrics()
        assert metrics.get("colibri_scheduler_active_slots") == 1.0

        deltas: list[str] = []
        res = client.stream_chat_completion(
            messages=[{"role": "user", "content": "Hi"}],
            model="qwen3-coder-30b",
            on_delta=lambda ev: deltas.append(ev.content_delta),
        )
        assert res.content == "Colibri streams tokens locally!"
        assert "".join(deltas) == "Colibri streams tokens locally!"
        assert res.ttft_ms >= 0.0
        assert res.tokens_per_sec > 0.0
    finally:
        server.shutdown()
        server.server_close()
