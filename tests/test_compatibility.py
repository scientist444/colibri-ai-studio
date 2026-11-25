"""Tests for Hardware / Model Compatibility Engine (`app/core/compatibility.py`)."""

from __future__ import annotations

from pathlib import Path

from app.core.compatibility import CompatibilityEngine, verify_architecture_support
from app.models.hardware_models import CpuProfile, GpuDevice, GpuVendor, RamProfile, SystemHardwareProfile
from app.models.model_metadata import CompatibilityBadge, ModelCandidate, SupportTier


def _make_hw(total_ram_gb: float, vram_gb: float = 0.0) -> SystemHardwareProfile:
    gpus = []
    if vram_gb > 0:
        gpus.append(
            GpuDevice(
                index=0,
                name="NVIDIA RTX Test GPU",
                vendor=GpuVendor.NVIDIA,
                is_discrete=True,
                dedicated_vram_gb=vram_gb,
                available_vram_gb=vram_gb - 1.0,
                cuda_available=True,
            )
        )
    return SystemHardwareProfile(
        cpu=CpuProfile(name="Test CPU", physical_cores=8, logical_cores=16, performance_cores=8),
        ram=RamProfile(
            total_gb=total_ram_gb,
            available_gb=total_ram_gb - 4.0,
            safe_allocatable_gb=max(2.0, total_ram_gb - 4.0),
            safety_reserve_gb=4.0,
        ),
        gpus=gpus,
        cuda_available=vram_gb >= 4.0,
        recommended_backend="cuda" if vram_gb >= 4.0 else "cpu",
    )


def test_verify_architecture_support() -> None:
    ok, fam, req_imp = verify_architecture_support(config_model_type="qwen3_5_moe")
    assert ok is True
    assert fam == "qwen36"
    assert req_imp is False

    ok_gguf, fam_gguf, req_imp_gguf = verify_architecture_support(gguf_arch="deepseek4")
    assert ok_gguf is True
    assert fam_gguf == "deepseek_v4"
    assert req_imp_gguf is True

    ok_bad, fam_bad, _ = verify_architecture_support(config_model_type="llama_unsupported_xyz")
    assert ok_bad is False
    assert fam_bad == "unsupported"


def test_compatibility_green_yellow_red_classification(tmp_path: Path) -> None:
    cand = ModelCandidate(
        model_id="qwen3-coder-30b",
        display_name="Qwen3-Coder 30B-A3B",
        hf_repo="Justvugg/Qwen3-Coder-30B-A3B-colibri-int4",
        family="qwen36",
        architecture="qwen3_moe",
        download_size_gb=19.4,
        disk_required_gb=20.0,
        ram_min_gb=8.0,
        ram_good_gb=18.0,
        dense_gb=3.6,
        support_tier=SupportTier.OFFICIAL_CATALOG,
    )

    # 1. 32 GB RAM + 12 GB VRAM -> GREEN (Recommended)
    hw_high = _make_hw(total_ram_gb=32.0, vram_gb=12.0)
    res_green = CompatibilityEngine.evaluate_candidate(cand, hw_high, target_models_dir=tmp_path)
    assert res_green.badge == CompatibilityBadge.GREEN
    assert res_green.can_execute is True

    # 2. 12 GB RAM (between ram_min=8 and ram_good=18) -> YELLOW (Runs with Expert Streaming)
    hw_mid = _make_hw(total_ram_gb=12.0, vram_gb=0.0)
    res_yellow = CompatibilityEngine.evaluate_candidate(cand, hw_mid, target_models_dir=tmp_path)
    assert res_yellow.badge == CompatibilityBadge.YELLOW
    assert res_yellow.can_execute is True

    # 3. 4 GB RAM (below ram_min=8) -> RED (Insufficient System RAM)
    hw_low = _make_hw(total_ram_gb=4.0, vram_gb=0.0)
    res_red = CompatibilityEngine.evaluate_candidate(cand, hw_low, target_models_dir=tmp_path)
    assert res_red.badge == CompatibilityBadge.RED
    assert res_red.can_execute is False

    # 4. Unsupported architecture -> RED
    unsupported_cand = cand.model_copy(
        update={
            "family": "unsupported",
            "architecture": "unknown_arch",
            "support_tier": SupportTier.UNSUPPORTED,
        }
    )
    res_unsup = CompatibilityEngine.evaluate_candidate(unsupported_cand, hw_high, target_models_dir=tmp_path)
    assert res_unsup.badge == CompatibilityBadge.RED
    assert res_unsup.can_execute is False


def test_compute_tier_placement() -> None:
    hw = _make_hw(total_ram_gb=32.0, vram_gb=8.0)
    cand = ModelCandidate(
        model_id="qwen36-35b",
        display_name="Qwen3.6 35B-A3B",
        hf_repo="Kreuzzelg/qwen36-35b-a3b-colibri-i4-gs64",
        family="qwen36",
        download_size_gb=23.1,
        dense_gb=3.5,
    )
    summary = CompatibilityEngine.compute_tier_placement(
        model_path=None,
        candidate=cand,
        hardware=hw,
        ctx_tokens=4096,
    )
    assert summary.dense_gb == 3.5
    assert summary.ram_expert_cache_gb > 0
    assert summary.vram_expert_cache_gb > 0
    assert 0.0 <= summary.expert_retention_ratio <= 1.0
