"""Tests for Intelligent Model Hub Fetcher (`app/core/model_fetcher.py`)."""

from __future__ import annotations

from pathlib import Path

from app.core.model_fetcher import ModelFetcher
from app.models.hardware_models import CpuProfile, RamProfile, SystemHardwareProfile
from app.models.model_metadata import SupportTier


def _sample_hw() -> SystemHardwareProfile:
    return SystemHardwareProfile(
        cpu=CpuProfile(name="Test CPU", physical_cores=8, logical_cores=16, performance_cores=8),
        ram=RamProfile(total_gb=32.0, available_gb=24.0, safe_allocatable_gb=24.0, safety_reserve_gb=4.0),
    )


def test_load_official_colibri_catalog(tmp_path: Path) -> None:
    fetcher = ModelFetcher()
    hw = _sample_hw()
    catalog = fetcher.load_official_catalog(hardware=hw, target_models_dir=tmp_path)
    assert len(catalog) >= 10
    ids = {c.model_id for c in catalog}
    assert "qwen36-35b" in ids
    assert "qwen3-coder-30b" in ids
    assert "deepseek-v4-flash-reap" in ids

    for item in catalog:
        assert item.support_tier == SupportTier.OFFICIAL_CATALOG
        assert item.download_size_gb > 0


def test_hf_architecture_verification_rejects_unsupported_keyword_matches(tmp_path: Path) -> None:
    fetcher = ModelFetcher()
    hw = _sample_hw()

    # 1. Supported Qwen3 MoE model with verified config.model_type
    valid_hf_item = {
        "id": "org/Qwen3-30B-A3B-Custom",
        "tags": ["moe", "safetensors", "license:apache-2.0"],
        "config": {"model_type": "qwen3_moe"},
        "downloads": 1250,
        "likes": 45,
        "gated": False,
        "sha": "abcdef1234567890",
        "siblings": [
            {"rfilename": "config.json", "size": 1024},
            {"rfilename": "model-00001.safetensors", "size": 10 * (1024**3)},
        ],
    }
    parsed_valid = fetcher._parse_hf_model_item(valid_hf_item, hw, {}, tmp_path)
    assert parsed_valid is not None
    assert parsed_valid.family == "qwen36"
    assert parsed_valid.support_tier in (SupportTier.POTENTIALLY_COMPATIBLE, SupportTier.OFFICIAL_CATALOG)
    assert parsed_valid.compatibility.architecture_supported is True

    # 2. Unsupported BERT/GPT2 model that happens to have 'moe' in its name must be marked UNSUPPORTED
    unsupported_hf_item = {
        "id": "random/fake-moe-gpt2-test",
        "tags": ["moe"],
        "config": {"model_type": "gpt2"},
        "downloads": 10,
        "likes": 0,
        "siblings": [{"rfilename": "model.safetensors", "size": 500 * 1024 * 1024}],
    }
    parsed_unsup = fetcher._parse_hf_model_item(unsupported_hf_item, hw, {}, tmp_path)
    assert parsed_unsup is not None
    assert parsed_unsup.support_tier == SupportTier.UNSUPPORTED
    assert parsed_unsup.compatibility.can_execute is False
