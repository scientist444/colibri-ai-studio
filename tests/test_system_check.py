"""Tests for Hardware Profiler (`app/core/system_check.py`)."""

from __future__ import annotations

from app.core.system_check import (
    HardwareProfiler,
    _classify_vendor,
    _is_integrated_gpu,
    detect_cpu_profile,
    detect_ram_profile,
    detect_storage_volumes,
)
from app.models.hardware_models import GpuDevice, GpuVendor, SystemHardwareProfile


def test_detect_cpu_profile() -> None:
    cpu = detect_cpu_profile(sample_interval=0.01)
    assert cpu.name
    assert cpu.physical_cores >= 1
    assert cpu.logical_cores >= cpu.physical_cores
    assert cpu.performance_cores >= 1
    assert 0.0 <= cpu.utilization_percent <= 100.0
    assert isinstance(cpu.instruction_sets, list)


def test_detect_ram_profile_and_workload_modes() -> None:
    ram_balanced = detect_ram_profile(workload_profile="balanced_desktop", safety_reserve_gb=4.0)
    assert ram_balanced.total_gb > 0
    assert ram_balanced.available_gb > 0
    assert ram_balanced.safe_allocatable_gb > 0
    assert not ram_balanced.is_unsafe_budget

    # Unsafe custom budget leaving < 2 GB for Windows must trigger warning
    unsafe_ram = detect_ram_profile(
        workload_profile="custom",
        safety_reserve_gb=1.0,
        custom_budget_gb=ram_balanced.total_gb - 0.5,
    )
    assert unsafe_ram.is_unsafe_budget
    assert "Unsafe memory budget" in unsafe_ram.warning_message


def test_gpu_classification_and_integrated_gpu_edge_cases() -> None:
    assert _classify_vendor("NVIDIA GeForce RTX 4080") == GpuVendor.NVIDIA
    assert _classify_vendor("AMD Radeon RX 7900 XTX") == GpuVendor.AMD
    assert _classify_vendor("Intel(R) Iris(R) Xe Graphics") == GpuVendor.INTEL

    # Integrated GPUs must be identified and never treated as high-VRAM discrete cards
    assert _is_integrated_gpu("Intel(R) UHD Graphics 770", GpuVendor.INTEL, 0.5) is True
    assert _is_integrated_gpu("NVIDIA GeForce RTX 4090", GpuVendor.NVIDIA, 24.0) is False


def test_multi_gpu_primary_selection() -> None:
    igpu = GpuDevice(
        index=0,
        name="Intel UHD Graphics",
        vendor=GpuVendor.INTEL,
        is_discrete=False,
        is_integrated=True,
        dedicated_vram_gb=0.5,
    )
    dgpu = GpuDevice(
        index=1,
        name="NVIDIA GeForce RTX 4070",
        vendor=GpuVendor.NVIDIA,
        is_discrete=True,
        is_integrated=False,
        dedicated_vram_gb=12.0,
        cuda_available=True,
    )
    profile = SystemHardwareProfile(gpus=[igpu, dgpu])
    assert profile.primary_gpu is not None
    assert profile.primary_gpu.name == "NVIDIA GeForce RTX 4070"
    assert profile.total_dedicated_vram_gb == 12.0


def test_detect_storage_volumes_and_full_scan() -> None:
    vols = detect_storage_volumes(include_disk_types=False)
    assert len(vols) >= 1
    assert vols[0].total_gb > 0

    profiler = HardwareProfiler()
    full = profiler.scan_system(workload_profile="engineering_workstation")
    assert full.cpu.physical_cores >= 1
    assert full.ram.total_gb > 0
    assert full.recommended_backend in ("cpu", "vulkan", "cuda")
