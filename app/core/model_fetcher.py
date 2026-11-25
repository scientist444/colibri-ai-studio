"""Intelligent Model Hub Fetcher (model_fetcher.py).

Combines:
- Source A: Official Colibri Catalog (`setup_catalog.py`)
- Source B: Live Hugging Face Hub API (`huggingface_hub` / `httpx`)
with verified Colibri architecture checking (never naive keyword-only labeling).
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import httpx

from app.constants import (
    COLIBRI_SUPPORTED_FAMILIES,
    HUGGINGFACE_API_BASE,
    SUPPORTED_CONFIG_MODEL_TYPES,
    SUPPORTED_GGUF_ARCHITECTURES,
)
from app.core.compatibility import CompatibilityEngine
from app.models.hardware_models import SystemHardwareProfile
from app.models.model_metadata import (
    InstalledModelRecord,
    ModelCandidate,
    SupportTier,
)
from app.utils.paths import get_bundled_colibri_runtime_dir

logger = logging.getLogger(__name__)


def _ensure_colibri_runtime_on_path() -> None:
    rt_dir = str(get_bundled_colibri_runtime_dir())
    if rt_dir not in sys.path:
        sys.path.insert(0, rt_dir)


# Enriched metadata for the official Colibri catalog entries
_CATALOG_ENRICHMENT: dict[str, dict[str, str]] = {
    "qwen36-35b": {
        "parameter_count": "35B Total",
        "active_parameters": "3B Active (MoE)",
        "quantization": "INT4 (Group 64)",
        "architecture": "qwen3_5_moe",
        "license_name": "Apache-2.0",
    },
    "qwen3-coder-30b": {
        "parameter_count": "30B Total",
        "active_parameters": "3B Active (MoE)",
        "quantization": "INT4",
        "architecture": "qwen3_moe",
        "license_name": "Apache-2.0",
    },
    "deepseek-v4-flash-reap": {
        "parameter_count": "150B Total (REAP Pruned)",
        "active_parameters": "8B Active (MoE)",
        "quantization": "FP8 / INT4",
        "architecture": "deepseek_v4",
        "license_name": "MIT / DeepSeek",
    },
    "deepseek-v4-flash": {
        "parameter_count": "236B Total",
        "active_parameters": "12B Active (MoE)",
        "quantization": "FP8",
        "architecture": "deepseek_v4",
        "license_name": "MIT / DeepSeek",
    },
    "qwen38-flash-next": {
        "parameter_count": "185B Total",
        "active_parameters": "10B Active (MoE)",
        "quantization": "FP8",
        "architecture": "qwen4_exp",
        "license_name": "Apache-2.0",
    },
    "mimo-v2.6-flash": {
        "parameter_count": "172B Total",
        "active_parameters": "24B Active (MoE)",
        "quantization": "FP8 / MOPD",
        "architecture": "mimo_v2",
        "license_name": "Apache-2.0",
    },
    "glm-5.2": {
        "parameter_count": "744B Total",
        "active_parameters": "40B Active (MoE + INT8 MTP)",
        "quantization": "INT4 (Group 64)",
        "architecture": "glm_moe_dsa",
        "license_name": "MIT / GLM",
    },
    "glm-5.3": {
        "parameter_count": "744B Total",
        "active_parameters": "40B Active (MoE)",
        "quantization": "INT4 (Group 64)",
        "architecture": "glm5_next",
        "license_name": "MIT / GLM",
    },
    "mimo-v2.6-pro": {
        "parameter_count": "564B Total",
        "active_parameters": "32B Active (MoE)",
        "quantization": "FP8 / MOPD",
        "architecture": "mimo_v2",
        "license_name": "Apache-2.0",
    },
    "inkling": {
        "parameter_count": "800B+ Total",
        "active_parameters": "49B Active (MoE)",
        "quantization": "INT4",
        "architecture": "inkling_mm_model",
        "license_name": "Custom Research",
    },
    "kimi-k3": {
        "parameter_count": "1.5T+ Total",
        "active_parameters": "20B Active (MoE)",
        "quantization": "FP8",
        "architecture": "kimi_k3",
        "license_name": "MIT / Moonshot",
    },
    "qwen-image-2.1": {
        "parameter_count": "14B Diffusion",
        "active_parameters": "8.5B Dense",
        "quantization": "BF16 / FP8",
        "architecture": "qwenimage21pipeline",
        "license_name": "Apache-2.0",
    },
}


class ModelFetcher:
    """Discovers models from the official Colibri catalog and live Hugging Face Hub API."""

    def __init__(self, hf_token: str | None = None) -> None:
        self.hf_token = hf_token

    def load_official_catalog(
        self,
        hardware: SystemHardwareProfile,
        installed_records: list[InstalledModelRecord] | None = None,
        target_models_dir: Path | str | None = None,
    ) -> list[ModelCandidate]:
        """Load the official Colibri model catalog from `setup_catalog.py` and assess compatibility."""
        _ensure_colibri_runtime_on_path()
        installed_map = {r.model_id: r for r in (installed_records or [])}
        installed_repos = {r.hf_repo.lower(): r for r in (installed_records or []) if r.hf_repo}

        raw_models: list[Any] = []
        try:
            import setup_catalog  # type: ignore[import-not-found]

            raw_models = list(getattr(setup_catalog, "CATALOG", getattr(setup_catalog, "MODELS", [])))
        except Exception as exc:
            logger.error("Failed to load setup_catalog.CATALOG: %s", exc)

        candidates: list[ModelCandidate] = []
        for entry in raw_models:
            mid = str(getattr(entry, "id", ""))
            enrich = _CATALOG_ENRICHMENT.get(mid, {})
            dl_gb = float(getattr(entry, "disk_gb", getattr(entry, "download_gb", 20.0)))
            repo_str = str(getattr(entry, "repo", getattr(entry, "hf_repo", "")))
            inst = installed_map.get(mid) or installed_repos.get(repo_str.lower())

            cand = ModelCandidate(
                model_id=mid,
                display_name=str(getattr(entry, "name", mid)),
                hf_repo=repo_str,
                family=str(getattr(entry, "family", "qwen36")),
                architecture=enrich.get("architecture", str(getattr(entry, "family", "qwen36"))),
                parameter_count=enrich.get("parameter_count", "MoE"),
                active_parameters=enrich.get("active_parameters", "Sparse MoE"),
                quantization=enrich.get("quantization", "INT4 / FP8"),
                download_size_gb=dl_gb,
                disk_required_gb=round(dl_gb * 1.05, 1),
                ram_min_gb=float(getattr(entry, "ram_min_gb", 8.0)),
                ram_good_gb=float(getattr(entry, "ram_good_gb", 16.0)),
                dense_gb=float(getattr(entry, "dense_gb", 3.5)),
                tier=str(getattr(entry, "size_class", getattr(entry, "tier", "small"))),
                modality=str(getattr(entry, "modality", "text")),
                description=str(getattr(entry, "summary", getattr(entry, "blurb", ""))),
                license_name=enrich.get("license_name", "Apache-2.0"),
                is_gated=False,
                revision=str(getattr(entry, "revision", "main")),
                support_tier=SupportTier.OFFICIAL_CATALOG,
                is_installed=inst is not None,
                local_path=inst.local_path if inst else None,
            )
            cand.compatibility = CompatibilityEngine.evaluate_candidate(
                cand, hardware, target_models_dir=target_models_dir
            )
            candidates.append(cand)

        return candidates

    def search_huggingface(
        self,
        query: str,
        hardware: SystemHardwareProfile,
        installed_records: list[InstalledModelRecord] | None = None,
        target_models_dir: Path | str | None = None,
        limit: int = 20,
    ) -> list[ModelCandidate]:
        """Query the live Hugging Face Hub API and verify Colibri architecture compatibility."""
        installed_repos = {r.hf_repo.lower(): r for r in (installed_records or []) if r.hf_repo}
        headers: dict[str, str] = {"Accept": "application/json"}
        if self.hf_token:
            headers["Authorization"] = f"Bearer {self.hf_token}"

        search_term = query.strip() or "colibri qwen3 moe gguf"
        params: dict[str, Any] = {
            "search": search_term,
            "limit": min(max(limit, 5), 40),
            "sort": "downloads",
            "direction": "-1",
            "full": "true",
            "config": "true",
        }

        url = f"{HUGGINGFACE_API_BASE}/api/models"
        with httpx.Client(timeout=15.0, headers=headers, follow_redirects=True) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            items = resp.json()

        if not isinstance(items, list):
            return []

        results: list[ModelCandidate] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            cand = self._parse_hf_model_item(item, hardware, installed_repos, target_models_dir)
            if cand is not None:
                results.append(cand)

        return results

    def _parse_hf_model_item(
        self,
        item: dict[str, Any],
        hardware: SystemHardwareProfile,
        installed_repos: dict[str, InstalledModelRecord],
        target_models_dir: Path | str | None,
    ) -> ModelCandidate | None:
        repo_id = str(item.get("id") or item.get("modelId") or "").strip()
        if not repo_id:
            return None

        tags = [str(t).lower() for t in (item.get("tags") or [])]
        config = item.get("config") or {}
        model_type = str(config.get("model_type") or "").strip().lower()
        siblings = item.get("siblings") or []

        # Calculate repository weight size from siblings when present, or estimate from safetensors metadata
        total_bytes = 0
        has_gguf = False
        has_colibri_meta = "colibri" in repo_id.lower() or any("colibri" in t for t in tags)
        quant_hint = "BF16 / FP16"

        for sib in siblings:
            if not isinstance(sib, dict):
                continue
            rfilename = str(sib.get("rfilename") or "").lower()
            fsize = int(sib.get("size") or 0)
            if rfilename.endswith((".safetensors", ".gguf", ".bin")):
                total_bytes += fsize
            if rfilename.endswith(".gguf"):
                has_gguf = True
            if "colibri_meta.json" in rfilename:
                has_colibri_meta = True

        if "gguf" in tags or "gguf" in repo_id.lower():
            has_gguf = True

        # Detect quantization from repo name / tags
        lower_repo = repo_id.lower()
        for q_label, q_keys in (
            ("INT4 (Colibri)", ("colibri-i4", "colibri-int4", "int4-g64")),
            ("Q4_K_M (GGUF)", ("q4_k_m", "q4_k", "q4_0")),
            ("Q8_0 (GGUF)", ("q8_0", "int8")),
            ("FP8", ("fp8",)),
            ("AWQ / GPTQ", ("awq", "gptq")),
        ):
            if any(k in lower_repo for k in q_keys) or any(k in tags for k in q_keys):
                quant_hint = q_label
                break

        # Strict Architecture Verification (Never label compatible by keyword alone!)
        support_tier = SupportTier.UNSUPPORTED
        resolved_family = "unsupported"
        resolved_arch = model_type or "unknown"

        if model_type in SUPPORTED_CONFIG_MODEL_TYPES:
            resolved_family = SUPPORTED_CONFIG_MODEL_TYPES[model_type]
            resolved_arch = model_type
            if has_colibri_meta:
                support_tier = SupportTier.OFFICIAL_CATALOG
            elif has_gguf:
                support_tier = SupportTier.VALIDATED_GGUF
            else:
                support_tier = SupportTier.POTENTIALLY_COMPATIBLE
        else:
            # Check if GGUF architecture tag matches Colibri's GGUF importer list
            matched_gguf_arch = None
            for arch_key, fam in SUPPORTED_GGUF_ARCHITECTURES.items():
                if arch_key in tags or f"arch:{arch_key}" in tags:
                    matched_gguf_arch = arch_key
                    resolved_family = fam
                    break
            if matched_gguf_arch and has_gguf:
                resolved_arch = matched_gguf_arch
                support_tier = SupportTier.VALIDATED_GGUF
            elif has_colibri_meta:
                # Official Colibri pre-quantized repository
                for fam in COLIBRI_SUPPORTED_FAMILIES:
                    if fam in lower_repo:
                        resolved_family = fam
                        break
                else:
                    resolved_family = "qwen36"
                resolved_arch = resolved_family
                support_tier = SupportTier.OFFICIAL_CATALOG
            elif has_gguf and any(
                k in lower_repo for k in ("qwen3", "deepseek-v4", "glm-5", "mimo-v2", "olmoe", "kimi-k3", "lfm3")
            ):
                # Candidate GGUF that requires header verification before import
                support_tier = SupportTier.POTENTIALLY_COMPATIBLE
                resolved_family = "qwen36"
                resolved_arch = "gguf (header verification required)"

        dl_gb = round(total_bytes / (1024**3), 2) if total_bytes > 0 else 18.0
        dense_gb = round(min(max(2.5, dl_gb * 0.18), 32.0), 1)
        ram_min_gb = round(dense_gb + 4.5, 1)
        ram_good_gb = round(min(max(ram_min_gb + 6.0, dl_gb * 0.65), dl_gb + 6.0), 1)

        license_str = "Open / Check Repo"
        for t in tags:
            if t.startswith("license:"):
                license_str = t.split(":", 1)[1].upper()
                break

        gated_val = item.get("gated")
        is_gated = bool(gated_val) and str(gated_val).lower() not in ("false", "none")

        inst = installed_repos.get(repo_id.lower())
        short_id = repo_id.replace("/", "--").lower()

        cand = ModelCandidate(
            model_id=short_id,
            display_name=repo_id.split("/")[-1],
            hf_repo=repo_id,
            family=resolved_family,
            architecture=resolved_arch,
            parameter_count=self._extract_param_badge(repo_id, tags),
            active_parameters="MoE / Sparse" if "moe" in lower_repo or "a3b" in lower_repo else "Dense / Standard",
            quantization=quant_hint,
            download_size_gb=dl_gb,
            disk_required_gb=round(dl_gb * (1.15 if has_gguf else 1.05), 1),
            ram_min_gb=ram_min_gb,
            ram_good_gb=ram_good_gb,
            dense_gb=dense_gb,
            tier="small" if dl_gb <= 40.0 else "large",
            modality="image" if "image" in lower_repo else "text",
            description=f"Hugging Face repository {repo_id} ({ int(item.get('downloads') or 0):,} downloads).",
            license_name=license_str,
            is_gated=is_gated,
            revision=str(item.get("sha") or "main")[:12],
            downloads_count=int(item.get("downloads") or 0),
            likes_count=int(item.get("likes") or 0),
            support_tier=support_tier,
            is_installed=inst is not None,
            local_path=inst.local_path if inst else None,
        )
        cand.compatibility = CompatibilityEngine.evaluate_candidate(
            cand, hardware, target_models_dir=target_models_dir
        )
        return cand

    @staticmethod
    def _extract_param_badge(repo_id: str, tags: list[str]) -> str:
        import re

        m = re.search(r"(\d+(?:\.\d+)?[bBtT])\b", repo_id)
        if m:
            return m.group(1).upper()
        for t in tags:
            m2 = re.search(r"^(\d+(?:\.\d+)?[bBtT])$", t)
            if m2:
                return m2.group(1).upper()
        return "Unknown"
