"""Rotating file logging with secret/token redaction."""

from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.utils.paths import get_logs_dir

_SECRET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(hf_[A-Za-z0-9]{10,})"), "hf_[REDACTED]"),
    (re.compile(r"(Bearer\s+[A-Za-z0-9._\-]{8,})", re.IGNORECASE), "Bearer [REDACTED]"),
    (re.compile(r"(--api-key\s+\S+)", re.IGNORECASE), "--api-key [REDACTED]"),
    (re.compile(r"(\"api_key\"\s*:\s*\"[^\"]+\")", re.IGNORECASE), '"api_key": "[REDACTED]"'),
    (re.compile(r"(\"token\"\s*:\s*\"[^\"]+\")", re.IGNORECASE), '"token": "[REDACTED]"'),
]


def redact_sensitive_text(text: str) -> str:
    """Redact API keys, Hugging Face tokens, and Bearer tokens from log/diagnostic text."""
    if not text:
        return text
    sanitized = text
    for pattern, replacement in _SECRET_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


class RedactingFilter(logging.Filter):
    """Logging filter that strips secrets from log records before emission."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_sensitive_text(record.msg)
        if record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(
                    redact_sensitive_text(arg) if isinstance(arg, str) else arg
                    for arg in record.args
                )
            elif isinstance(record.args, dict):
                record.args = {
                    k: (redact_sensitive_text(v) if isinstance(v, str) else v)
                    for k, v in record.args.items()
                }
        return True


def setup_logging(log_level: int = logging.INFO) -> Path:
    """Configure application-wide rotating file and console logging."""
    logs_dir = get_logs_dir()
    log_file = logs_dir / "colibri_studio.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Avoid duplicate handlers on repeated initialization
    if any( getattr(h, "_colibri_configured", False) for h in root_logger.handlers ):
        return log_file

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    redactor = RedactingFilter()

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(redactor)
    setattr(file_handler, "_colibri_configured", True)
    root_logger.addHandler(file_handler)

    return log_file


def get_recent_logs(max_lines: int = 400) -> str:
    """Read and redact the most recent lines from the application log file."""
    log_file = get_logs_dir() / "colibri_studio.log"
    if not log_file.exists():
        return "No application logs written yet."
    try:
        lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
        subset = lines[-max_lines:]
        return redact_sensitive_text("\n".join(subset))
    except OSError as exc:
        return f"Failed to read log file: {exc}"
