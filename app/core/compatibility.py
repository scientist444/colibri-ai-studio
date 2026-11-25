"""Hardware / Model Compatibility Engine (compatibility.py).

Evaluates model compatibility against the user's detected CPU, RAM, GPU VRAM,
and Storage using Colibri's architecture registry and resource planning rules.
Separates download eligibility from execution eligibility.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

from app.constants import (
    COLIBRI_SUPPORTED_FAMILIES,
    SUPPORTED_CONFIG_MODEL_TYPES,
    SUPPORTED_GGUF_ARCHITECTURES,
)
from app.core.storage_manager import StorageManager
from app.models.hardware_models import SystemHardwareProfile, TierPlacementSummary
from app.models.model_metadata import (
    CompatibilityAssessment,
    CompatibilityBadge,
    ModelCandidate,
    SupportTier,
)
from app.utils.paths import get_bundled_colibri_runtime_dir

logger = logging.getLogger(__name__)


def _ensure_colibri_runtime_on_path() -> None:
    rt_dir = str(get_bundled_colibri_runtime_dir())
    if rt_dir not in sys.path:
        sys.path.insert(0, rt_dir)


def verify_architecture_support(
    config_model_type: str = "",
    gguf_arch: str = "",
    family_hint: str = "",
) -> tuple[bool, str, bool]:
    """Check if a model's architecture is genuinely supported by Colibri.

    Returns `(is_supported, resolved_family, requires_gguf_import)`.
    """
    if family_hint and family_hint in COLIBRI_SUPPORTED_FAMILIES:
        return True, family_hint, bool(gguf_arch)

    mt_clean = config_model_type.strip().lower()
    if mt_clean and mt_clean in SUPPORTED_CONFIG_MODEL_TYPES:
        return True, SUPPORTED_CONFIG_MODEL_TYPES[mt_clean], False

    gguf_clean = gguf_arch.strip().lower()
    if gguf_clean and gguf_clean in SUPPORTED_GGUF_ARCHITECTURES:
        return True, SUPPORTED_GGUF_ARCHITECTURES[gguf_clean], True

    return False, "unsupported", False


class CompatibilityEngine:
    """Evaluates candidate and installed models against the active hardware profile."""

    @staticmethod
    def evaluate_candidate(
        candidate: ModelCandidate,
        hardware: SystemHardwareProfile,
        target_models_dir: Path | str | None = None,
    ) -> CompatibilityAssessment:
        """Compute Green / Yellow / Red compatibility badge and explanations."""
        reasons: list[str] = []
        warnings: list[str] = []

        # 1. Check architecture support
        arch_supported = candidate.support_tier in (
            SupportTier.OFFICIAL_CATALOG,
            SupportTier.VALIDATED_GGUF,
            SupportTier.POTENTIALLY_COMPATIBLE,
        )
        if candidate.family in COLIBRI_SUPPORTED_FAMILIES:
            arch_supported = True
        elif candidate.architecture.lower() in SUPPORTED_CONFIG_MODEL_TYPES:
            arch_supported = True
        elif candidate.architecture.lower() in SUPPORTED_GGUF_ARCHITECTURES:
            arch_supported = True

        requires_import = candidate.support_tier == SupportTier.VALIDATED_GGUF or (
            candidate.architecture.lower() in SUPPORTED_GGUF_ARCHITECTURES
        )

        # 2. Check disk space for download
        models_dir = Path(target_models_dir or hardware.recommended_models_dir or ".")
        disk_req_gb = max(candidate.disk_required_gb, candidate.download_size_gb)
        if requires_import:
            # GGUF import needs space for converted shard output unless hardlinked
            disk_req_gb = round(candidate.download_size_gb * 1.15, 2)

        disk_ok, free_gb, disk_msg = StorageManager.check_sufficient_space(
            models_dir, required_gb=disk_req_gb, safety_margin_gb=2.0
        )
        can_download = disk_ok or candidate.is_installed
        if not disk_ok and not candidate.is_installed:
            warnings.append(disk_msg)

        # 3. Check RAM against model's minimum resident requirement and full/good cache requirement
        total_ram = hardware.ram.total_gb
        safe_ram = max(hardware.ram.safe_allocatable_gb, total_ram - hardware.ram.safety_reserve_gb)
        ram_min = max(1.0, candidate.ram_min_gb)
        ram_good = max(ram_min, candidate.ram_good_gb)

        ram_ok_min = total_ram >= ram_min
        ram_ok_good = total_ram >= ram_good and safe_ram >= (ram_min * 0.9)

        # 4. Check GPU VRAM & backend
        primary_gpu = hardware.primary_gpu
        vram_gb = primary_gpu.dedicated_vram_gb if (primary_gpu and primary_gpu.is_discrete) else 0.0
        rec_backend = hardware.recommended_backend

        # Determine execution mode and expected speed tier
        if not arch_supported or candidate.support_tier == SupportTier.UNSUPPORTED:
            return CompatibilityAssessment(
                badge=CompatibilityBadge.RED,
                badge_label="Unsupported Architecture",
                support_tier=SupportTier.UNSUPPORTED,
                can_download=False,
                can_execute=False,
                architecture_supported=False,
                requires_gguf_import=False,
                disk_space_sufficient=disk_ok,
                ram_sufficient_minimum=ram_ok_min,
                ram_sufficient_good=ram_ok_good,
                estimated_ram_required_gb=ram_min,
                estimated_vram_used_gb=0.0,
                estimated_disk_required_gb=disk_req_gb,
                expected_mode="Unsupported by Colibri Engine",
                recommended_backend=rec_backend,
                speed_tier="Cannot Run",
                reasons=[
                    f"Architecture '{candidate.architecture}' is not in Colibri's supported family registry."
                ],
                warnings=warnings,
            )

        if not ram_ok_min:
            reasons.append(
                f"Requires at least {ram_min:.1f} GB system RAM (dense weights {candidate.dense_gb:.1f} GB + runtime), "
                f"but system has {total_ram:.1f} GB."
            )
            return CompatibilityAssessment(
                badge=CompatibilityBadge.RED,
                badge_label="Insufficient System RAM",
                support_tier=candidate.support_tier,
                can_download=can_download,
                can_execute=False,
                architecture_supported=True,
                requires_gguf_import=requires_import,
                disk_space_sufficient=disk_ok,
                ram_sufficient_minimum=False,
                ram_sufficient_good=False,
                estimated_ram_required_gb=ram_min,
                estimated_vram_used_gb=min(vram_gb, candidate.dense_gb),
                estimated_disk_required_gb=disk_req_gb,
                expected_mode="Exceeds Resident Memory",
                recommended_backend=rec_backend,
                speed_tier="Unusable / Will Not Fit",
                reasons=reasons,
                warnings=warnings,
            )

        # Estimate VRAM usage and execution mode
        est_vram = 0.0
        if rec_backend in ("cuda", "vulkan") and vram_gb >= 4.0:
            est_vram = round(min(max(0.0, vram_gb - 1.5), candidate.download_size_gb), 1)

        if vram_gb >= candidate.download_size_gb + 2.0 and rec_backend in ("cuda", "vulkan"):
            expected_mode = f"Full GPU Resident ({rec_backend.upper()})"
            speed_tier = "Fast (40–90+ tok/s)"
        elif total_ram >= candidate.download_size_gb + 6.0:
            if est_vram > 0:
                expected_mode = f"GPU + Full RAM Resident ({rec_backend.upper()} + RAM)"
                speed_tier = "Fast Interactive (25–55 tok/s)"
            else:
                expected_mode = "Full System RAM Resident (Zero Disk Streaming)"
                speed_tier = "Interactive (18–40 tok/s)"
        else:
            if est_vram > 0:
                expected_mode = f"3-Tier Hybrid ({rec_backend.upper()} VRAM + RAM Cache + NVMe Streaming)"
            else:
                expected_mode = "RAM Expert Cache + NVMe SSD Streaming"
            speed_tier = "Streaming Interactive (8–25 tok/s)" if ram_ok_good else "Heavy NVMe Streaming (3–12 tok/s)"

        if requires_import:
            warnings.append("Requires one-time automatic `coli import` GGUF conversion after download.")

        if candidate.support_tier == SupportTier.POTENTIALLY_COMPATIBLE:
            warnings.append("Repository architecture matched by family metadata; verify `config.json` after download.")

        if ram_ok_good and (disk_ok or candidate.is_installed) and candidate.support_tier in (
            SupportTier.OFFICIAL_CATALOG,
            SupportTier.VALIDATED_GGUF,
        ):
            reasons.append(
                f"System RAM ({total_ram:.1f} GB) meets or exceeds recommended {ram_good:.1f} GB budget."
            )
            if est_vram > 0:
                reasons.append(f"GPU acceleration available via {rec_backend.upper()} ({est_vram:.1f} GB VRAM cache).")
            return CompatibilityAssessment(
                badge=CompatibilityBadge.GREEN,
                badge_label="Recommended for Your PC",
                support_tier=candidate.support_tier,
                can_download=can_download,
                can_execute=True,
                architecture_supported=True,
                requires_gguf_import=requires_import,
                disk_space_sufficient=disk_ok,
                ram_sufficient_minimum=True,
                ram_sufficient_good=True,
                estimated_ram_required_gb=ram_good,
                estimated_vram_used_gb=est_vram,
                estimated_disk_required_gb=disk_req_gb,
                expected_mode=expected_mode,
                recommended_backend=rec_backend,
                speed_tier=speed_tier,
                reasons=reasons,
                warnings=warnings,
            )

        # Otherwise YELLOW (runs with heavy NVMe streaming, tight disk space, or needs verification)
        if not ram_ok_good:
            warnings.append(
                f"Runs via NVMe expert streaming: {total_ram:.1f} GB installed is above minimum ({ram_min:.1f} GB) "
                f"but below ideal cache target ({ram_good:.1f} GB). Fast NVMe SSD strongly recommended."
            )
        reasons.append(f"Minimum resident footprint ({ram_min:.1f} GB) fits in system memory.")
        return CompatibilityAssessment(
            badge=CompatibilityBadge.YELLOW,
            badge_label="Runs with Expert Streaming" if ram_ok_min else "Performance Warning",
            support_tier=candidate.support_tier,
            can_download=can_download,
            can_execute=True,
            architecture_supported=True,
            requires_gguf_import=requires_import,
            disk_space_sufficient=disk_ok,
            ram_sufficient_minimum=True,
            ram_sufficient_good=ram_ok_good,
            estimated_ram_required_gb=ram_min,
            estimated_vram_used_gb=est_vram,
            estimated_disk_required_gb=disk_req_gb,
            expected_mode=expected_mode,
            recommended_backend=rec_backend,
            speed_tier=speed_tier,
            reasons=reasons,
            warnings=warnings,
        )

    @staticmethod
    def compute_tier_placement(
        model_path: Path | str | None,
        candidate: ModelCandidate | None,
        hardware: SystemHardwareProfile,
        ctx_tokens: int = 4096,
        policy: str = "balanced",
        custom_ram_gb: float | None = None,
        custom_vram_gb: float | None = None,
    ) -> TierPlacementSummary:
        """Compute 3-tier placement using Colibri's native `resource_plan.build_resource_plan` when model_path exists,
        or an accurate analytical plan for catalog models before download."""
        _ensure_colibri_runtime_on_path()

        if model_path and Path(model_path).exists():
            try:
                import resource_plan  # type: ignore[import-not-found]

                overrides: dict[str, Any] = {"ctx": ctx_tokens, "policy": policy}
                if custom_ram_gb is not None and custom_ram_gb > 0:
                    overrides["ram_gb"] = custom_ram_gb
                if custom_vram_gb is not None and custom_vram_gb >= 0:
                    overrides["vram_gb"] = custom_vram_gb

                plan = resource_plan.build_resource_plan(
                    model_dir=str(model_path),
                    cli_overrides=overrides,
                )
                return TierPlacementSummary(
                    is_measured=False,
                    source_label="Planned (Colibri Native Resource Planner)",
                    model_id=Path(model_path).name,
                    family=str(getattr(plan, "family", "qwen36")),
                    dense_gb=round(float(getattr(plan, "dense_gb", 3.5)), 2),
                    kv_cache_gb=round(float(getattr(plan, "kv_gb", 0.5)), 2),
                    vram_expert_cache_gb=round(float(getattr(plan, "vram_budget_gb", 0.0)), 2),
                    vram_slots=int(getattr(plan, "vram_slots", 0) or 0),
                    ram_expert_cache_gb=round(float(getattr(plan, "ram_budget_gb", 0.0)), 2),
                    ram_slots=int(getattr(plan, "ram_slots", 0) or 0),
                    nvme_streaming_gb=round(
                        max(
                            0.0,
                            float(getattr(plan, "routed_gb", 0.0))
                            - float(getattr(plan, "ram_budget_gb", 0.0))
                            - float(getattr(plan, "vram_budget_gb", 0.0)),
                        ),
                        2,
                    ),
                    expert_retention_ratio=round(float(getattr(plan, "retention_ratio", 0.0)), 3),
                    gpu_mode=str(getattr(plan, "gpu_mode", "off")),
                    ctx_tokens=int(getattr(plan, "ctx_tokens", ctx_tokens)),
                    thread_count=int(getattr(plan, "threads", hardware.cpu.performance_cores)),
                    warnings=list(getattr(plan, "warnings", []) or []),
                )
            except Exception as exc:
                logger.debug("Native resource_plan fallback: %s", exc)

        # Analytical fallback for candidate or when no local model directory is selected yet
        dense_gb = candidate.dense_gb if candidate else 3.5
        total_model_gb = candidate.download_size_gb if candidate else 19.4
        routed_gb = max(0.0, total_model_gb - dense_gb)
        kv_gb = round((ctx_tokens / 4096.0) * 0.45, 2)

        safe_ram = custom_ram_gb if custom_ram_gb else hardware.ram.safe_allocatable_gb
        ram_for_experts = round(max(0.0, min(routed_gb, safe_ram - dense_gb - kv_gb)), 2)

        gpu = hardware.primary_gpu
        vram_avail = custom_vram_gb if custom_vram_gb is not None else (
            max(0.0, gpu.dedicated_vram_gb - 1.5) if (gpu and gpu.is_discrete) else 0.0
        )
        vram_for_experts = round(min(routed_gb, vram_avail), 2)
        nvme_stream = round(max(0.0, routed_gb - ram_for_experts - vram_for_experts), 2)
        retention = round(
            min(1.0, (ram_for_experts + vram_for_experts) / routed_gb) if routed_gb > 0 else 1.0,
            3,
        )

        return TierPlacementSummary(
            is_measured=False,
            source_label="Planned (Hardware Budget Estimate)",
            model_id=candidate.model_id if candidate else "qwen3-coder-30b",
            family=candidate.family if candidate else "qwen36",
            dense_gb=round(dense_gb, 2),
            kv_cache_gb=kv_gb,
            vram_expert_cache_gb=vram_for_experts,
            vram_slots=int(vram_for_experts * 32),
            ram_expert_cache_gb=ram_for_experts,
            ram_slots=int(ram_for_experts * 32),
            nvme_streaming_gb=nvme_stream,
            expert_retention_ratio=retention,
            gpu_mode=hardware.recommended_backend if vram_for_experts > 0 else "off",
            ctx_tokens=ctx_tokens,
            thread_count=hardware.cpu.performance_cores,
            warnings=[],
        )
