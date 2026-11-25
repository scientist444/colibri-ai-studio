"""Model catalog, Hugging Face metadata, and compatibility evaluation models."""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


class CompatibilityBadge(str, Enum):
    GREEN = "green"    # Recommended
    YELLOW = "yellow"  # Streaming / Performance Warning
    RED = "red"        # Unsupported / Insufficient Resources


class SupportTier(str, Enum):
    OFFICIAL_CATALOG = "official_catalog"
    VALIDATED_GGUF = "validated_gguf"
    POTENTIALLY_COMPATIBLE = "potentially_compatible"
    UNSUPPORTED = "unsupported"


class CompatibilityAssessment(BaseModel):
    """Detailed compatibility evaluation for a candidate model on the active hardware."""

    badge: CompatibilityBadge = CompatibilityBadge.YELLOW
    badge_label: str = "Streaming / Performance Warning"
    support_tier: SupportTier = SupportTier.OFFICIAL_CATALOG
    can_download: bool = True
    can_execute: bool = True
    architecture_supported: bool = True
    requires_gguf_import: bool = False
    disk_space_sufficient: bool = True
    ram_sufficient_minimum: bool = True
    ram_sufficient_good: bool = True
    estimated_ram_required_gb: float = 0.0
    estimated_vram_used_gb: float = 0.0
    estimated_disk_required_gb: float = 0.0
    expected_mode: str = "RAM + NVMe Expert Streaming"
    recommended_backend: str = "cpu"
    speed_tier: str = "Interactive (15–35 tok/s)"
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ModelCandidate(BaseModel):
    """Complete model metadata for Model Hub and My Models views."""

    model_id: str
    display_name: str
    hf_repo: str
    family: str = "unknown"
    architecture: str = "unknown"
    parameter_count: str = "Unknown"
    active_parameters: str = "Dense / Unknown"
    quantization: str = "INT4 / FP8"
    download_size_gb: float = 0.0
    disk_required_gb: float = 0.0
    ram_min_gb: float = 8.0
    ram_good_gb: float = 16.0
    dense_gb: float = 3.5
    tier: str = "small"
    modality: str = "text"
    description: str = ""
    license_name: str = "Open / Check Repo"
    is_gated: bool = False
    revision: str = "main"
    downloads_count: int = 0
    likes_count: int = 0
    support_tier: SupportTier = SupportTier.OFFICIAL_CATALOG
    compatibility: CompatibilityAssessment = Field(default_factory=CompatibilityAssessment)
    is_installed: bool = False
    local_path: str | None = None


class InstalledModelRecord(BaseModel):
    """Database/registry record for a locally installed or imported model."""

    model_id: str
    display_name: str
    hf_repo: str = ""
    local_path: str
    family: str = "qwen36"
    architecture: str = ""
    quantization: str = "INT4"
    size_bytes: int = 0
    installed_at: str = ""
    verified: bool = False
    source_type: str = "catalog"  # catalog, huggingface, gguf_import
    notes: str = ""
