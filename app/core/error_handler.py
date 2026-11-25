"""Centralized user-friendly error translation and recovery guidance."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FriendlyError:
    """User-facing error explanation and actionable recovery steps."""

    title: str
    summary: str
    recovery_guidance: str
    technical_details: str = ""


def classify_exception(exc: Exception | str, context: str = "") -> FriendlyError:
    """Translate raw exceptions or stderr strings into actionable user guidance."""
    raw = str(exc).strip()
    lower = raw.lower()

    if "401" in lower or "403" in lower or "gated" in lower or "unauthorized" in lower:
        return FriendlyError(
            title="Authentication or Gated Repository Access Required",
            summary="This Hugging Face model requires a valid access token or license agreement.",
            recovery_guidance=(
                "1. Open the model repository on huggingface.co and accept its license terms if gated.\n"
                "2. Go to Settings → Privacy & Security and save your Hugging Face Read Token.\n"
                "3. Retry the download."
            ),
            technical_details=raw,
        )

    if "no space left" in lower or "disk full" in lower or "insufficient disk" in lower or "errno 28" in lower:
        return FriendlyError(
            title="Insufficient Disk Space",
            summary="The selected drive does not have enough free space to complete this operation.",
            recovery_guidance=(
                "1. Free up space on your model storage drive, or\n"
                "2. Go to Settings → Storage and choose another SSD/NVMe volume with more free capacity."
            ),
            technical_details=raw,
        )

    if "timeout" in lower or "connecterror" in lower or "network" in lower or "name or service not known" in lower:
        return FriendlyError(
            title="Network Connection Interrupted",
            summary="Could not reach the remote server or local inference endpoint.",
            recovery_guidance=(
                "1. Check your internet connection if downloading models or checking releases.\n"
                "2. Interrupted downloads automatically save `.part` progress and can be resumed in My Models.\n"
                "3. If offline, enable Offline Mode in Settings → Privacy & Security."
            ),
            technical_details=raw,
        )

    if "address already in use" in lower or "10048" in lower or "port" in lower and "bind" in lower:
        return FriendlyError(
            title="Server Port Already in Use",
            summary="Another process is already listening on the configured local server port.",
            recovery_guidance=(
                "1. Use the Stop Server button or go to Settings → Inference to select a different port (e.g. 8001).\n"
                "2. Restart the model server."
            ),
            technical_details=raw,
        )

    if "memory" in lower or "oom" in lower or "bad_alloc" in lower or "pagefile" in lower:
        return FriendlyError(
            title="Insufficient Memory for Current Configuration",
            summary="The operating system could not allocate the requested RAM or GPU VRAM budget.",
            recovery_guidance=(
                "1. Close memory-intensive background applications.\n"
                "2. In Performance Lab or Settings → Hardware, switch to 'Balanced Desktop' or reduce the Context Length.\n"
                "3. Or select a smaller quantized model in Model Hub."
            ),
            technical_details=raw,
        )

    return FriendlyError(
        title=f"Operation Error{f' ({context})' if context else ''}",
        summary=raw.splitlines()[0] if raw else "An unexpected error occurred.",
        recovery_guidance=(
            "Check Settings → Diagnostics for recent logs or run the Colibri Doctor check to verify your setup."
        ),
        technical_details=raw,
    )
