"""Hardware profile, CPU, RAM, GPU, Storage, and Colibri Tier Placement models."""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


class GpuVendor(str, Enum):
    NVIDIA = "NVIDIA"
    AMD = "AMD"
    INTEL = "Intel"
    MICROSOFT = "Microsoft"
    OTHER = "Other"


class CpuProfile(BaseModel):
    """Detected CPU hardware and instruction set capabilities."""

    name: str = "Unknown CPU"
    architecture: str = "x86_64"
    physical_cores: int = 1
    logical_cores: int = 1
    performance_cores: int = 1
    utilization_percent: float = 0.0
    frequency_mhz: float = 0.0
    max_frequency_mhz: float = 0.0
    avx2: bool = False
    avx512: bool = False
    avx_vnni: bool = False
    instruction_sets: list[str] = Field(default_factory=list)


class RamProfile(BaseModel):
    """Detected system memory and safe allocation budgets."""

    total_gb: float = 0.0
    available_gb: float = 0.0
    used_gb: float = 0.0
    utilization_percent: float = 0.0
    commit_available_gb: float = 0.0
    safety_reserve_gb: float = 4.0
    safe_allocatable_gb: float = 0.0
    is_unsafe_budget: bool = False
    warning_message: str = ""


class GpuDevice(BaseModel):
    """Individual GPU device capabilities and memory metrics."""

    index: int = 0
    name: str = "Unknown GPU"
    vendor: GpuVendor = GpuVendor.OTHER
    is_discrete: bool = False
    is_integrated: bool = False
    dedicated_vram_gb: float = 0.0
    available_vram_gb: float = 0.0
    used_vram_gb: float = 0.0
    shared_system_ram_gb: float = 0.0
    utilization_percent: float | None = None
    temperature_c: float | None = None
    cuda_available: bool = False
    compute_capability: str | None = None
    vulkan_available: bool = False
    driver_version: str | None = None
    backend_compatible: bool = False


class StorageVolume(BaseModel):
    """Detected Windows storage volume and performance characteristics."""

    drive_letter: str = "C:\\"
    mount_point: str = "C:\\"
    label: str = ""
    filesystem: str = "NTFS"
    total_gb: float = 0.0
    free_gb: float = 0.0
    used_gb: float = 0.0
    percent_used: float = 0.0
    bus_type: str = "Unknown"
    media_type: str = "Unknown"
    is_ssd: bool = True
    is_nvme: bool = False
    measured_seq_read_mb_s: float | None = None
    measured_rand_read_mb_s: float | None = None


class TierPlacementSummary(BaseModel):
    """3-Tier placement summary (GPU VRAM -> System RAM -> NVMe Storage)."""

    is_measured: bool = False
    source_label: str = "Planned (Colibri Resource Planner)"
    model_id: str = ""
    family: str = ""
    dense_gb: float = 0.0
    kv_cache_gb: float = 0.0
    vram_expert_cache_gb: float = 0.0
    vram_slots: int = 0
    ram_expert_cache_gb: float = 0.0
    ram_slots: int = 0
    nvme_streaming_gb: float = 0.0
    expert_retention_ratio: float = 0.0
    gpu_mode: str = "off"
    ctx_tokens: int = 4096
    thread_count: int = 4
    warnings: list[str] = Field(default_factory=list)


class SystemHardwareProfile(BaseModel):
    """Aggregated system hardware profile for Colibri AI Studio."""

    os_name: str = "Windows"
    os_version: str = ""
    os_release: str = ""
    cpu: CpuProfile = Field(default_factory=CpuProfile)
    ram: RamProfile = Field(default_factory=RamProfile)
    gpus: list[GpuDevice] = Field(default_factory=list)
    volumes: list[StorageVolume] = Field(default_factory=list)
    cuda_available: bool = False
    vulkan_available: bool = False
    recommended_backend: str = "cpu"
    recommended_models_dir: str = ""
    workload_profile: str = "balanced_desktop"

    @property
    def primary_gpu(self) -> GpuDevice | None:
        if not self.gpus:
            return None
        discrete = [g for g in self.gpus if g.is_discrete]
        if discrete:
            return max(discrete, key=lambda g: g.dedicated_vram_gb)
        return max(self.gpus, key=lambda g: g.dedicated_vram_gb)

    @property
    def total_dedicated_vram_gb(self) -> float:
        gpu = self.primary_gpu
        return gpu.dedicated_vram_gb if gpu else 0.0
