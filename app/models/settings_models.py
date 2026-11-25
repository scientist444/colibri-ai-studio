"""Pydantic settings models for application, hardware, storage, inference, and privacy."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.constants import (
    DEFAULT_CTX_TOKENS,
    DEFAULT_HOST,
    DEFAULT_MAX_TOKENS,
    DEFAULT_PORT,
    DEFAULT_SYSTEM_RAM_RESERVE_GB,
    DEFAULT_TEMPERATURE,
    DEFAULT_TOP_P,
    DEFAULT_VRAM_HEADROOM_GB,
)
from app.utils.paths import get_default_engine_dir, get_default_models_dir


class AppSettings(BaseModel):
    """Validated user settings persisted in `%LOCALAPPDATA%\\ColibriAIStudio\\settings.json`."""

    # General
    first_run_completed: bool = False
    startup_view: str = "chat"
    theme: str = "obsidian_glass"
    ui_scale_percent: int = Field(default=100, ge=75, le=200)
    confirm_before_large_downloads: bool = True

    # Paths & Storage
    engine_dir: str = Field(default_factory=lambda: str(get_default_engine_dir()))
    models_dir: str = Field(default_factory=lambda: str(get_default_models_dir()))
    active_model_id: str = ""
    active_model_path: str = ""

    # Hardware & Memory Budgets
    workload_profile: str = "balanced_desktop"
    performance_profile: str = "balanced"
    system_ram_reserve_gb: float = Field(default=DEFAULT_SYSTEM_RAM_RESERVE_GB, ge=1.0, le=128.0)
    custom_ram_budget_gb: float | None = None
    vram_headroom_gb: float = Field(default=DEFAULT_VRAM_HEADROOM_GB, ge=0.0, le=64.0)
    custom_vram_budget_gb: float | None = None
    preferred_backend: str = "auto"  # auto, cpu, vulkan, cuda
    gpu_offload_mode: str = "auto"   # auto, off, full, hybrid
    cpu_threads: int = Field(default=0, ge=0, le=256)  # 0 = auto P-core count

    # Inference Server & Generation Defaults
    server_host: str = DEFAULT_HOST
    server_port: int = Field(default=DEFAULT_PORT, ge=1024, le=65535)
    auto_tier: bool = True
    retention_policy: str = "balanced"  # quality, balanced, experimental-fast
    context_length: int = Field(default=DEFAULT_CTX_TOKENS, ge=512, le=262144)
    default_temperature: float = Field(default=DEFAULT_TEMPERATURE, ge=0.0, le=2.0)
    default_top_p: float = Field(default=DEFAULT_TOP_P, ge=0.01, le=1.0)
    default_max_tokens: int = Field(default=DEFAULT_MAX_TOKENS, ge=16, le=65536)
    default_system_prompt: str = (
        "You are a helpful, accurate, and thoughtful AI assistant running locally in Colibri AI Studio."
    )
    enable_thinking: bool = False
    reasoning_effort: str = "medium"  # none, minimal, low, medium, high, xhigh
    preserve_thinking: bool = False
    context_compaction: str = "auto"  # auto, off
    stop_sequences: list[str] = Field(default_factory=list)

    # Privacy & Security
    offline_mode: bool = False
    require_local_api_key: bool = False
    sanitize_logs: bool = True

    @field_validator("preferred_backend")
    @classmethod
    def _validate_backend(cls, v: str) -> str:
        allowed = {"auto", "cpu", "vulkan", "cuda"}
        return v.lower() if v.lower() in allowed else "auto"

    @field_validator("retention_policy")
    @classmethod
    def _validate_policy(cls, v: str) -> str:
        allowed = {"quality", "balanced", "experimental-fast"}
        return v if v in allowed else "balanced"
