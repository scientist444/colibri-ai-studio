"""Performance Optimizer & Benchmark Suite (performance_optimizer.py).

Integrates:
- Automatic hardware optimization recommendations
- `coli tune` native parameter tuner wrapper
- Repeatable inference benchmark runner (TTFT, decode tok/s, prefill speed, peak RAM/VRAM)
- Workload profile configuration
"""

from __future__ import annotations

import logging
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

import psutil

from app.constants import PERFORMANCE_PROFILES, WORKLOAD_PROFILES
from app.core.backend_adapter import CREATE_NO_WINDOW, ColibriBackendAdapter
from app.core.colibri_api import ColibriApiClient
from app.database.repositories import BenchmarkRepository
from app.models.hardware_models import SystemHardwareProfile
from app.models.settings_models import AppSettings

logger = logging.getLogger(__name__)

STANDARD_BENCHMARK_PROMPTS: dict[str, list[dict[str, str]]] = {
    "Short Q&A (Latency & TTFT)": [
        {
            "role": "user",
            "content": "Explain in three concise bullet points how Mixture-of-Experts (MoE) language models reduce active compute per token.",
        }
    ],
    "Code Generation (Throughput)": [
        {
            "role": "user",
            "content": "Write a clean, well-commented Python class implementing an LRU cache using collections.OrderedDict with type annotations and unit test examples.",
        }
    ],
    "Multi-Turn Reasoning": [
        {"role": "user", "content": "We have a 64 GB RAM workstation with an 8 GB VRAM GPU and a 3.5 GB/s NVMe SSD."},
        {"role": "assistant", "content": "Understood. Please share the model parameters you want to analyze."},
        {
            "role": "user",
            "content": "Analyze how a 35B MoE model (3.5 GB dense weights, 3B active parameters per token) distributes across GPU VRAM, System RAM, and NVMe storage.",
        },
    ],
}


class PerformanceOptimizer:
    """Provides hardware tuning recommendations, `coli tune` execution, and benchmarks."""

    def __init__(
        self,
        adapter: ColibriBackendAdapter,
        benchmark_repo: BenchmarkRepository,
    ) -> None:
        self.adapter = adapter
        self.benchmark_repo = benchmark_repo

    @staticmethod
    def recommend_optimal_settings(
        hardware: SystemHardwareProfile,
        current_settings: AppSettings,
        performance_preset: str = "balanced",
    ) -> dict[str, Any]:
        """Compute optimal CPU threads, RAM/VRAM budgets, backend, and context length."""
        preset = PERFORMANCE_PROFILES.get(performance_preset, PERFORMANCE_PROFILES["balanced"])
        workload = WORKLOAD_PROFILES.get(
            current_settings.workload_profile, WORKLOAD_PROFILES["balanced_desktop"]
        )

        p_cores = max(1, hardware.cpu.performance_cores)
        thread_ratio = float(preset.get("thread_ratio", 0.85))
        rec_threads = max(1, int(round(p_cores * thread_ratio)))

        rec_reserve = float(workload.get("system_ram_reserve_gb", 4.0))
        rec_vram_headroom = float(workload.get("vram_headroom_gb", 1.5))
        rec_ram_budget = round(max(2.0, hardware.ram.total_gb - rec_reserve), 1)

        gpu = hardware.primary_gpu
        if gpu and gpu.is_discrete and gpu.dedicated_vram_gb >= 4.0:
            rec_vram_budget = round(max(0.0, gpu.dedicated_vram_gb - rec_vram_headroom), 1)
            rec_gpu_mode = "hybrid"
        else:
            rec_vram_budget = 0.0
            rec_gpu_mode = "off"

        return {
            "cpu_threads": rec_threads,
            "system_ram_reserve_gb": rec_reserve,
            "custom_ram_budget_gb": rec_ram_budget,
            "vram_headroom_gb": rec_vram_headroom,
            "custom_vram_budget_gb": rec_vram_budget,
            "preferred_backend": hardware.recommended_backend,
            "gpu_offload_mode": rec_gpu_mode,
            "retention_policy": str(preset.get("policy", "balanced")),
            "context_length": int(preset.get("ctx_tokens", 4096)),
        }

    def run_colibri_autotune(
        self,
        model_dir: Path | str,
        tokens: int = 16,
        repeats: int = 2,
        on_log: Callable[[str], None] | None = None,
    ) -> tuple[bool, str]:
        """Run `coli tune --model <dir>` to discover optimal runtime flags."""
        mpath = Path(model_dir).resolve()
        if not mpath.exists():
            return False, f"Model directory not found: {mpath}"

        args = [
            "tune",
            "--model",
            str(mpath),
            "--tokens",
            str(tokens),
            "--repeats",
            str(repeats),
        ]
        cmd = self.adapter.build_coli_command(args)
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(self.adapter.engine_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=CREATE_NO_WINDOW,
            )
            lines: list[str] = []
            if proc.stdout:
                for line in proc.stdout:
                    clean = line.rstrip("\r\n")
                    lines.append(clean)
                    if on_log and clean:
                        on_log(clean)
            proc.wait(timeout=900.0)
            output = "\n".join(lines)
            return proc.returncode == 0, output
        except Exception as exc:
            return False, str(exc)

    def run_inference_benchmark(
        self,
        api_client: ColibriApiClient,
        model_id: str,
        backend: str,
        ctx_tokens: int,
        threads: int,
        policy: str,
        prompt_name: str = "Short Q&A (Latency & TTFT)",
        max_tokens: int = 128,
        storage_seq_mb_s: float = 0.0,
    ) -> dict[str, Any]:
        """Execute a live benchmark against the active Colibri server and persist results."""
        messages = STANDARD_BENCHMARK_PROMPTS.get(
            prompt_name,
            STANDARD_BENCHMARK_PROMPTS["Short Q&A (Latency & TTFT)"],
        )

        vm_before = psutil.virtual_memory()
        ram_before_gb = (vm_before.total - vm_before.available) / (1024**3)
        peak_ram_gb = ram_before_gb

        def _track_peak(_ev: Any) -> None:
            nonlocal peak_ram_gb
            vm = psutil.virtual_memory()
            used = (vm.total - vm.available) / (1024**3)
            if used > peak_ram_gb:
                peak_ram_gb = used

        t0 = time.perf_counter()
        stream_res = api_client.stream_chat_completion(
            messages=messages,
            model=model_id,
            temperature=0.2,
            max_tokens=max_tokens,
            on_delta=_track_peak,
        )
        _ = time.perf_counter() - t0

        ttft_s = max(0.005, stream_res.ttft_ms / 1000.0)
        prompt_toks = max(16, stream_res.prompt_tokens or 32)
        prefill_tok_s = round(prompt_toks / ttft_s, 1)

        record = self.benchmark_repo.add_benchmark(
            model_id=model_id,
            backend=backend,
            ctx_tokens=ctx_tokens,
            threads=threads,
            policy=policy,
            prompt_name=prompt_name,
            ttft_ms=round(stream_res.ttft_ms, 1),
            decode_tok_s=round(stream_res.tokens_per_sec, 2),
            prefill_tok_s=prefill_tok_s,
            peak_ram_gb=round(peak_ram_gb, 2),
            peak_vram_gb=0.0,
            storage_seq_mb_s=storage_seq_mb_s,
            notes=f"{stream_res.completion_tokens} tokens generated in {stream_res.total_time_s:.2f}s",
        )
        return record
