"""Colibri OpenAI-Compatible HTTP & SSE Streaming Client (colibri_api.py).

Communicates with Colibri's local server (`openai_server.py`):
- `GET /health`
- `GET /v1/models`
- `GET /profile`
- `GET /metrics`
- `POST /v1/chat/completions` (streaming SSE and non-streaming)
Includes an incremental SSE line framing parser safe across arbitrary byte/UTF-8 chunk boundaries.
"""

from __future__ import annotations

import codecs
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator

import httpx

logger = logging.getLogger(__name__)


@dataclass
class StreamDeltaEvent:
    """Single parsed incremental event from a Colibri SSE chat stream."""

    content_delta: str = ""
    reasoning_delta: str = ""
    finish_reason: str | None = None
    compaction_info: dict[str, Any] | None = None
    usage: dict[str, Any] | None = None
    is_done: bool = False


@dataclass
class StreamCompletionResult:
    """Final aggregated metrics and content from a completed or cancelled stream."""

    content: str = ""
    reasoning_content: str = ""
    finish_reason: str = "stop"
    ttft_ms: float = 0.0
    total_time_s: float = 0.0
    tokens_per_sec: float = 0.0
    completion_tokens: int = 0
    prompt_tokens: int = 0
    was_cancelled: bool = False
    compaction_events: list[dict[str, Any]] = field(default_factory=list)


class IncrementalSseParser:
    """Incremental UTF-8 and SSE line parser resilient to arbitrary network chunking."""

    def __init__(self) -> None:
        self._utf8_decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self._buffer = ""
        self._in_think_tag = False

    def feed_bytes(self, raw_chunk: bytes, final: bool = False) -> list[StreamDeltaEvent]:
        text_chunk = self._utf8_decoder.decode(raw_chunk, final=final)
        return self.feed_text(text_chunk, final=final)

    def feed_text(self, text_chunk: str, final: bool = False) -> list[StreamDeltaEvent]:
        self._buffer += text_chunk
        events: list[StreamDeltaEvent] = []

        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            line = line.rstrip("\r")
            ev = self._parse_sse_line(line)
            if ev is not None:
                events.append(ev)

        if final and self._buffer.strip():
            ev = self._parse_sse_line(self._buffer.strip())
            self._buffer = ""
            if ev is not None:
                events.append(ev)

        return events

    def _parse_sse_line(self, line: str) -> StreamDeltaEvent | None:
        if not line or line.startswith(":"):
            return None
        if not line.startswith("data:"):
            return None

        payload_str = line[5:].strip()
        if not payload_str:
            return None
        if payload_str == "[DONE]":
            return StreamDeltaEvent(is_done=True, finish_reason="stop")

        try:
            payload = json.loads(payload_str)
        except json.JSONDecodeError:
            logger.debug("Malformed SSE JSON frame ignored: %s", payload_str[:120])
            return None

        if not isinstance(payload, dict):
            return None

        if "error" in payload:
            err_obj = payload["error"]
            msg = err_obj.get("message", str(err_obj)) if isinstance(err_obj, dict) else str(err_obj)
            raise RuntimeError(f"Colibri Server Error: {msg}")

        compaction = payload.get("compaction") if isinstance(payload.get("compaction"), dict) else None
        usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else None

        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            if compaction or usage:
                return StreamDeltaEvent(compaction_info=compaction, usage=usage)
            return None

        choice0 = choices[0] if isinstance(choices[0], dict) else {}
        delta = choice0.get("delta") if isinstance(choice0.get("delta"), dict) else {}
        finish_reason = choice0.get("finish_reason")

        content_piece = str(delta.get("content") or "")
        reasoning_piece = str(delta.get("reasoning_content") or "")

        # Also handle inline <think>...</think> blocks if model emits raw tags
        if content_piece and not reasoning_piece:
            content_piece, extracted_think = self._split_think_tags(content_piece)
            reasoning_piece = extracted_think

        return StreamDeltaEvent(
            content_delta=content_piece,
            reasoning_delta=reasoning_piece,
            finish_reason=str(finish_reason) if finish_reason else None,
            compaction_info=compaction,
            usage=usage,
            is_done=False,
        )

    def _split_think_tags(self, text: str) -> tuple[str, str]:
        if "<think>" in text:
            before, after = text.split("<think>", 1)
            self._in_think_tag = True
            if "</think>" in after:
                think_part, rest = after.split("</think>", 1)
                self._in_think_tag = False
                return before + rest, think_part
            return before, after
        if self._in_think_tag:
            if "</think>" in text:
                think_part, rest = text.split("</think>", 1)
                self._in_think_tag = False
                return rest, think_part
            return "", text
        return text, ""


class ColibriApiClient:
    """HTTP and SSE client for Colibri's local OpenAI-compatible server."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8000,
        api_key: str | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.api_key = api_key

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def check_health(self, timeout: float = 2.0) -> tuple[bool, dict[str, Any]]:
        """Query `GET /health`."""
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.get(f"{self.base_url}/health", headers=self._headers())
                data = resp.json() if resp.content else {}
                is_ok = resp.status_code == 200 and data.get("status") == "ok"
                return is_ok, data if isinstance(data, dict) else {}
        except Exception as exc:
            return False, {"status": "unreachable", "error": str(exc)}

    def list_models(self, timeout: float = 3.0) -> list[dict[str, Any]]:
        """Query `GET /v1/models`."""
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.get(f"{self.base_url}/v1/models", headers=self._headers())
                resp.raise_for_status()
                body = resp.json()
                data = body.get("data", []) if isinstance(body, dict) else []
                return [m for m in data if isinstance(m, dict)]
        except Exception:
            return []

    def get_profile_telemetry(self, timeout: float = 2.5) -> dict[str, Any]:
        """Query `GET /profile` for per-turn latency and token telemetry."""
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.get(f"{self.base_url}/profile", headers=self._headers())
                if resp.status_code == 200:
                    data = resp.json()
                    return data if isinstance(data, dict) else {}
        except Exception:
            pass
        return {}

    def get_prometheus_metrics(self, timeout: float = 2.5) -> dict[str, float]:
        """Query `GET /metrics` and parse key numeric Prometheus gauges/counters."""
        metrics: dict[str, float] = {}
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.get(f"{self.base_url}/metrics", headers=self._headers())
                if resp.status_code == 200:
                    for line in resp.text.splitlines():
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        parts = line.split()
                        if len(parts) >= 2:
                            key = parts[0].split("{")[0]
                            try:
                                metrics[key] = float(parts[-1])
                            except ValueError:
                                pass
        except Exception:
            pass
        return metrics

    def stream_chat_completion(
        self,
        messages: list[dict[str, Any]],
        model: str = "colibri",
        temperature: float = 0.6,
        top_p: float = 0.95,
        max_tokens: int = 1024,
        stop: list[str] | None = None,
        enable_thinking: bool | None = None,
        reasoning_effort: str | None = None,
        preserve_thinking: bool | None = None,
        context_compaction: str = "auto",
        on_delta: Callable[[StreamDeltaEvent], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
        timeout: float = 300.0,
    ) -> StreamCompletionResult:
        """Stream `POST /v1/chat/completions` with real SSE parsing and cancellation support."""
        payload: dict[str, Any] = {
            "model": model or "colibri",
            "messages": messages,
            "stream": True,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
            "context_compaction": context_compaction,
        }
        if stop:
            payload["stop"] = stop[:4]
        if enable_thinking is not None:
            payload["enable_thinking"] = enable_thinking
        if reasoning_effort and reasoning_effort != "none":
            payload["reasoning_effort"] = reasoning_effort
        if preserve_thinking is not None:
            payload["preserve_thinking"] = preserve_thinking

        parser = IncrementalSseParser()
        result = StreamCompletionResult()
        t_start = time.perf_counter()
        t_first_token: float | None = None
        piece_count = 0

        with httpx.Client(timeout=timeout) as client:
            with client.stream(
                "POST",
                f"{self.base_url}/v1/chat/completions",
                headers=self._headers(),
                json=payload,
            ) as resp:
                if resp.status_code >= 400:
                    err_text = resp.read().decode("utf-8", errors="replace")
                    raise RuntimeError(f"HTTP {resp.status_code}: {err_text}")

                for raw_bytes in resp.iter_bytes():
                    if should_cancel and should_cancel():
                        result.was_cancelled = True
                        result.finish_reason = "cancelled"
                        break
                    if not raw_bytes:
                        continue

                    events = parser.feed_bytes(raw_bytes, final=False)
                    for ev in events:
                        if (ev.content_delta or ev.reasoning_delta) and t_first_token is None:
                            t_first_token = time.perf_counter()
                            result.ttft_ms = round((t_first_token - t_start) * 1000.0, 1)

                        if ev.content_delta:
                            result.content += ev.content_delta
                            piece_count += 1
                        if ev.reasoning_delta:
                            result.reasoning_content += ev.reasoning_delta
                            piece_count += 1
                        if ev.compaction_info:
                            result.compaction_events.append(ev.compaction_info)
                        if ev.usage:
                            result.completion_tokens = int(ev.usage.get("completion_tokens") or piece_count)
                            result.prompt_tokens = int(ev.usage.get("prompt_tokens") or 0)
                        if ev.finish_reason:
                            result.finish_reason = ev.finish_reason

                        if on_delta is not None:
                            on_delta(ev)

                        if ev.is_done:
                            break

        t_end = time.perf_counter()
        result.total_time_s = round(max(0.001, t_end - t_start), 3)
        if result.completion_tokens <= 0:
            # Estimate token count from streamed pieces / word subtokens
            result.completion_tokens = max(piece_count, len(result.content.split()))
        decode_window = max(0.001, t_end - (t_first_token or t_start))
        if result.completion_tokens > 1 and t_first_token is not None:
            result.tokens_per_sec = round((result.completion_tokens - 1) / decode_window, 2)
        elif result.completion_tokens > 0:
            result.tokens_per_sec = round(result.completion_tokens / result.total_time_s, 2)

        return result
