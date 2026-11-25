"""Liquid Glass Performance Lab View (`performance_view.py`) — Emoji-Free."""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.application_state import ApplicationState
from app.constants import MIN_SAFE_SYSTEM_RAM_RESERVE_GB, PERFORMANCE_PROFILES, WORKLOAD_PROFILES
from app.core.colibri_manager import BackendState
from app.core.performance_optimizer import STANDARD_BENCHMARK_PROMPTS
from app.core.storage_manager import StorageManager
from app.ui.liquid_glass import LiquidGlassPanel
from app.ui.widgets.status_badge import StatusBadge
from app.utils.threading_utils import run_in_background


class PerformanceLabView(QWidget):
    """Liquid Glass Performance Lab for tuning, memory budgeting, and benchmarking."""

    def __init__(self, app_state: ApplicationState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.app_state = app_state
        self._last_storage_seq_mb_s: float = 0.0

        self._build_ui()
        self._load_benchmark_history()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Header
        header = LiquidGlassPanel(self, radius=16.0, elevated=True)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(18, 12, 18, 12)

        title_col = QVBoxLayout()
        title_lbl = QLabel("Performance Lab & Hardware Tuner")
        title_lbl.setObjectName("viewTitle")
        sub_lbl = QLabel(
            "Optimize CPU threads, 3-Tier RAM/VRAM budgets, run Colibri `coli tune`, and benchmark inference speed"
        )
        sub_lbl.setObjectName("viewSubtitle")
        title_col.addWidget(title_lbl)
        title_col.addWidget(sub_lbl)
        h_layout.addLayout(title_col, 1)

        auto_opt_btn = QPushButton("Auto-Optimize for My Workstation")
        auto_opt_btn.setObjectName("primaryGlassButton")
        auto_opt_btn.clicked.connect(self._apply_auto_optimization)
        h_layout.addWidget(auto_opt_btn)
        layout.addWidget(header)

        # Liquid Glass Tabs
        self.tabs = QTabWidget()

        self.tab_profiles = QWidget()
        self.tab_budgets = QWidget()
        self.tab_benchmarks = QWidget()
        self.tab_autotune = QWidget()

        self.tabs.addTab(self.tab_profiles, "01. Workload & Performance Profiles")
        self.tabs.addTab(self.tab_budgets, "02. Memory & Context Budget Sliders")
        self.tabs.addTab(self.tab_benchmarks, "03. Inference Benchmark Suite")
        self.tabs.addTab(self.tab_autotune, "04. Colibri `coli tune` & SSD Benchmark")

        self._build_profiles_tab()
        self._build_budgets_tab()
        self._build_benchmarks_tab()
        self._build_autotune_tab()

        layout.addWidget(self.tabs, 1)

    def _build_profiles_tab(self) -> None:
        layout = QVBoxLayout(self.tab_profiles)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)

        card = LiquidGlassPanel(self.tab_profiles, radius=14.0)
        grid = QGridLayout(card)
        grid.setContentsMargins(16, 14, 16, 14)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(12)

        grid.addWidget(QLabel("Workload Memory Profile:"), 0, 0)
        self.workload_combo = QComboBox()
        for key, meta in WORKLOAD_PROFILES.items():
            self.workload_combo.addItem(f"{meta['label']} — {meta['description']}", key)
        cur_w = self.app_state.settings.workload_profile
        for i in range(self.workload_combo.count()):
            if self.workload_combo.itemData(i) == cur_w:
                self.workload_combo.setCurrentIndex(i)
                break
        grid.addWidget(self.workload_combo, 0, 1)

        grid.addWidget(QLabel("Performance Preset:"), 1, 0)
        self.perf_combo = QComboBox()
        for key, meta in PERFORMANCE_PROFILES.items():
            self.perf_combo.addItem(f"{meta['label']} — {meta['description']}", key)
        cur_p = self.app_state.settings.performance_profile
        for i in range(self.perf_combo.count()):
            if self.perf_combo.itemData(i) == cur_p:
                self.perf_combo.setCurrentIndex(i)
                break
        grid.addWidget(self.perf_combo, 1, 1)

        grid.addWidget(QLabel("Expert Cache Retention Policy:"), 2, 0)
        self.policy_combo = QComboBox()
        self.policy_combo.addItems(["balanced", "quality", "experimental-fast"])
        self.policy_combo.setCurrentText(self.app_state.settings.retention_policy)
        grid.addWidget(self.policy_combo, 2, 1)

        grid.addWidget(QLabel("Preferred Compute Backend:"), 3, 0)
        self.backend_combo = QComboBox()
        self.backend_combo.addItems(["auto", "cpu", "vulkan", "cuda"])
        self.backend_combo.setCurrentText(self.app_state.settings.preferred_backend)
        grid.addWidget(self.backend_combo, 3, 1)

        apply_btn = QPushButton("Apply Profile & Save Settings")
        apply_btn.setObjectName("primaryGlassButton")
        apply_btn.clicked.connect(self._save_profile_tab)
        grid.addWidget(apply_btn, 4, 1, alignment=Qt.AlignmentFlag.AlignRight)

        layout.addWidget(card)
        layout.addStretch(1)

    def _build_budgets_tab(self) -> None:
        layout = QVBoxLayout(self.tab_budgets)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)

        card = LiquidGlassPanel(self.tab_budgets, radius=14.0)
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(16, 14, 16, 14)
        c_layout.setSpacing(12)

        tot_ram = max(4, int(round(self.app_state.hardware.ram.total_gb)))
        cur_reserve = int(round(self.app_state.settings.system_ram_reserve_gb))

        ram_row = QHBoxLayout()
        ram_row.addWidget(QLabel("Windows System RAM Safety Reserve (GB):"))
        self.ram_reserve_lbl = QLabel(f"{cur_reserve} GB Reserved (Leaves {max(1, tot_ram - cur_reserve)} GB for AI)")
        self.ram_reserve_lbl.setStyleSheet("font-weight: 700; color: #38BDF8;")
        ram_row.addStretch(1)
        ram_row.addWidget(self.ram_reserve_lbl)
        c_layout.addLayout(ram_row)

        self.ram_slider = QSlider(Qt.Orientation.Horizontal)
        self.ram_slider.setRange(1, max(4, tot_ram - 2))
        self.ram_slider.setValue(cur_reserve)
        self.ram_slider.valueChanged.connect(self._on_budget_sliders_changed)
        c_layout.addWidget(self.ram_slider)

        self.safety_badge = StatusBadge("SAFE MEMORY ALLOCATION", variant="green")
        c_layout.addWidget(self.safety_badge)

        params_row = QHBoxLayout()
        params_row.addWidget(QLabel("Context Window (`--ctx`):"))
        self.ctx_combo = QComboBox()
        for ctx_val in (2048, 4096, 8192, 16384, 32768, 65536):
            self.ctx_combo.addItem(f"{ctx_val:,} tokens", ctx_val)
        cur_ctx = self.app_state.settings.context_length
        for i in range(self.ctx_combo.count()):
            if self.ctx_combo.itemData(i) == cur_ctx:
                self.ctx_combo.setCurrentIndex(i)
                break
        params_row.addWidget(self.ctx_combo)

        params_row.addSpacing(20)
        params_row.addWidget(QLabel("CPU Inference Threads (0 = Auto P-Cores):"))
        self.threads_spin = QSpinBox()
        self.threads_spin.setRange(0, self.app_state.hardware.cpu.logical_cores)
        self.threads_spin.setValue(self.app_state.settings.cpu_threads)
        params_row.addWidget(self.threads_spin)
        params_row.addStretch(1)

        save_budgets_btn = QPushButton("Save Memory & Thread Budgets")
        save_budgets_btn.setObjectName("primaryGlassButton")
        save_budgets_btn.clicked.connect(self._save_budgets_tab)
        params_row.addWidget(save_budgets_btn)

        c_layout.addLayout(params_row)
        layout.addWidget(card)
        layout.addStretch(1)

    def _build_benchmarks_tab(self) -> None:
        layout = QVBoxLayout(self.tab_benchmarks)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        ctrl_card = LiquidGlassPanel(self.tab_benchmarks, radius=14.0)
        ctrl_row = QHBoxLayout(ctrl_card)
        ctrl_row.setContentsMargins(14, 10, 14, 10)

        ctrl_row.addWidget(QLabel("Benchmark Workload:"))
        self.bench_prompt_combo = QComboBox()
        for name in STANDARD_BENCHMARK_PROMPTS:
            self.bench_prompt_combo.addItem(name)
        ctrl_row.addWidget(self.bench_prompt_combo, 1)

        self.run_bench_btn = QPushButton("Run Live Inference Benchmark")
        self.run_bench_btn.setObjectName("primaryGlassButton")
        self.run_bench_btn.clicked.connect(self._run_live_benchmark)
        ctrl_row.addWidget(self.run_bench_btn)
        layout.addWidget(ctrl_card)

        self.bench_table = QTableWidget(0, 8)
        self.bench_table.setHorizontalHeaderLabels(
            ["Model", "Prompt", "Backend", "Context", "TTFT (ms)", "Decode (tok/s)", "Prefill (tok/s)", "Peak RAM"]
        )
        self.bench_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)  # type: ignore[union-attr]
        layout.addWidget(self.bench_table, 1)

    def _build_autotune_tab(self) -> None:
        layout = QVBoxLayout(self.tab_autotune)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        top_card = LiquidGlassPanel(self.tab_autotune, radius=14.0)
        top_row = QHBoxLayout(top_card)
        top_row.setContentsMargins(14, 10, 14, 10)

        self.storage_bench_btn = QPushButton("Run Bounded SSD/NVMe Read Benchmark (64 MB)")
        self.storage_bench_btn.clicked.connect(self._run_storage_benchmark)
        top_row.addWidget(self.storage_bench_btn)

        self.coli_tune_btn = QPushButton("Run Native `coli tune` on Active Model")
        self.coli_tune_btn.setObjectName("primaryGlassButton")
        self.coli_tune_btn.clicked.connect(self._run_coli_tune)
        top_row.addWidget(self.coli_tune_btn)

        top_row.addStretch(1)
        layout.addWidget(top_card)

        self.tune_output = QPlainTextEdit()
        self.tune_output.setReadOnly(True)
        self.tune_output.setPlaceholderText(
            "Output from `coli tune` or the bounded NVMe/SSD storage read benchmark will appear here..."
        )
        layout.addWidget(self.tune_output, 1)

    def _on_budget_sliders_changed(self, reserve_gb: int) -> None:
        tot = max(4.0, self.app_state.hardware.ram.total_gb)
        alloc = max(0.5, tot - reserve_gb)
        self.ram_reserve_lbl.setText(f"{reserve_gb} GB Reserved (Leaves {alloc:.1f} GB for AI)")
        if reserve_gb < MIN_SAFE_SYSTEM_RAM_RESERVE_GB:
            self.safety_badge.set_variant(
                "red",
                f"UNSAFE RESERVE (< {MIN_SAFE_SYSTEM_RAM_RESERVE_GB:.0f} GB): High risk of Windows pagefile thrashing",
            )
        elif reserve_gb < 4:
            self.safety_badge.set_variant(
                "yellow",
                "TIGHT RESERVE: Close browsers and heavy background apps during inference",
            )
        else:
            self.safety_badge.set_variant("green", "SAFE MEMORY ALLOCATION FOR WINDOWS")

    def _apply_auto_optimization(self) -> None:
        rec = self.app_state.performance_optimizer.recommend_optimal_settings(
            hardware=self.app_state.hardware,
            current_settings=self.app_state.settings,
            performance_preset=str(self.perf_combo.currentData() or "balanced"),
        )
        self.app_state.update_settings(**rec)
        self.ram_slider.setValue(int(round(float(rec["system_ram_reserve_gb"]))))
        self.threads_spin.setValue(int(rec["cpu_threads"]))
        self.policy_combo.setCurrentText(str(rec["retention_policy"]))
        self.backend_combo.setCurrentText(str(rec["preferred_backend"]))
        QMessageBox.information(
            self,
            "Auto-Optimization Applied",
            f"Configured optimal parameters for your workstation:\n\n"
            f"- CPU Threads: {rec['cpu_threads']} (Physical P-Cores)\n"
            f"- Safe RAM Budget: {rec['custom_ram_budget_gb']} GB ({rec['system_ram_reserve_gb']} GB Windows Reserve)\n"
            f"- GPU VRAM Cache Budget: {rec['custom_vram_budget_gb']} GB ({rec['preferred_backend'].upper()})\n"
            f"- Retention Policy: {rec['retention_policy']}",
        )

    def _save_profile_tab(self) -> None:
        w_key = str(self.workload_combo.currentData() or "balanced_desktop")
        p_key = str(self.perf_combo.currentData() or "balanced")
        w_cfg = WORKLOAD_PROFILES.get(w_key, WORKLOAD_PROFILES["balanced_desktop"])
        self.app_state.update_settings(
            workload_profile=w_key,
            performance_profile=p_key,
            system_ram_reserve_gb=float(w_cfg["system_ram_reserve_gb"]),
            vram_headroom_gb=float(w_cfg["vram_headroom_gb"]),
            retention_policy=self.policy_combo.currentText(),
            preferred_backend=self.backend_combo.currentText(),
        )
        self.ram_slider.setValue(int(round(float(w_cfg["system_ram_reserve_gb"]))))
        QMessageBox.information(self, "Profile Saved", "Workload and performance profile settings updated.")

    def _save_budgets_tab(self) -> None:
        reserve = float(self.ram_slider.value())
        tot = self.app_state.hardware.ram.total_gb
        custom_ram = round(max(1.0, tot - reserve), 1)
        ctx = int(self.ctx_combo.currentData() or 4096)
        threads = self.threads_spin.value()
        self.app_state.update_settings(
            system_ram_reserve_gb=reserve,
            custom_ram_budget_gb=custom_ram,
            context_length=ctx,
            cpu_threads=threads,
        )
        QMessageBox.information(self, "Budgets Saved", "Memory, context window, and thread budgets saved.")

    def _run_live_benchmark(self) -> None:
        if self.app_state.process_manager.state != BackendState.RUNNING:
            QMessageBox.information(
                self,
                "Active Server Required",
                "Please load an installed model first so the benchmark suite can measure live TTFT and token throughput.",
            )
            return

        self.run_bench_btn.setEnabled(False)
        prompt_name = self.bench_prompt_combo.currentText()
        client = self.app_state.process_manager.get_api_client()
        model_id = self.app_state.process_manager.active_model_id or "colibri"
        settings = self.app_state.settings

        def _worker() -> dict[str, Any]:
            return self.app_state.performance_optimizer.run_inference_benchmark(
                api_client=client,
                model_id=model_id,
                backend=settings.preferred_backend,
                ctx_tokens=settings.context_length,
                threads=settings.cpu_threads or self.app_state.hardware.cpu.performance_cores,
                policy=settings.retention_policy,
                prompt_name=prompt_name,
                storage_seq_mb_s=self._last_storage_seq_mb_s,
            )

        def _on_done(_rec: dict[str, Any]) -> None:
            self.run_bench_btn.setEnabled(True)
            self._load_benchmark_history()

        def _on_err(err: str, _tb: str) -> None:
            self.run_bench_btn.setEnabled(True)
            QMessageBox.warning(self, "Benchmark Error", err)

        run_in_background(_worker, on_result=_on_done, on_error=_on_err)

    def _load_benchmark_history(self) -> None:
        rows = self.app_state.benchmarks_repo.list_benchmarks(limit=35)
        self.bench_table.setRowCount(len(rows))
        for r_idx, row in enumerate(rows):
            vals = [
                str(row.get("model_id", "")),
                str(row.get("prompt_name", "")),
                str(row.get("backend", "")).upper(),
                str(row.get("ctx_tokens", 4096)),
                f"{float(row.get('ttft_ms') or 0.0):.0f} ms",
                f"{float(row.get('decode_tok_s') or 0.0):.2f} tok/s",
                f"{float(row.get('prefill_tok_s') or 0.0):.1f} tok/s",
                f"{float(row.get('peak_ram_gb') or 0.0):.1f} GB",
            ]
            for c_idx, val in enumerate(vals):
                self.bench_table.setItem(r_idx, c_idx, QTableWidgetItem(val))

    def _run_storage_benchmark(self) -> None:
        target = self.app_state.settings.models_dir
        reply = QMessageBox.question(
            self,
            "Permission to Run Bounded Storage Benchmark",
            f"Colibri AI Studio will write and read a temporary 64 MB test file inside:\n{target}\n"
            "to measure sequential and random 256 KB expert-slice read speeds, and immediately delete the file.\n\n"
            "Proceed?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.storage_bench_btn.setEnabled(False)
        self.tune_output.appendPlainText(f"Running bounded 64 MB storage read benchmark in {target}...")

        def _worker() -> dict[str, float]:
            return StorageManager.run_bounded_read_benchmark(target, size_mb=64)

        def _on_done(res: dict[str, float]) -> None:
            self.storage_bench_btn.setEnabled(True)
            self._last_storage_seq_mb_s = res.get("seq_read_mb_s", 0.0)
            self.tune_output.appendPlainText(
                f"[OK] Storage Benchmark Complete:\n"
                f"  - Sequential Read: {res['seq_read_mb_s']:.1f} MB/s\n"
                f"  - Random 256 KB Expert-Slice Read: {res['rand_read_mb_s']:.1f} MB/s\n"
                f"  - Sequential Write: {res['seq_write_mb_s']:.1f} MB/s\n"
            )

        def _on_err(err: str, _tb: str) -> None:
            self.storage_bench_btn.setEnabled(True)
            self.tune_output.appendPlainText(f"[ERROR] Storage benchmark error: {err}")

        run_in_background(_worker, on_result=_on_done, on_error=_on_err)

    def _run_coli_tune(self) -> None:
        mpath = self.app_state.settings.active_model_path
        if not mpath:
            installed = self.app_state.models_repo.list_models()
            if installed:
                mpath = installed[0].local_path
        if not mpath:
            QMessageBox.information(
                self,
                "No Local Model Installed",
                "Install a model in Model Hub first before running `coli tune`.",
            )
            return

        self.coli_tune_btn.setEnabled(False)
        self.tune_output.appendPlainText(f"Starting `coli tune --model {mpath}`...")

        def _worker() -> tuple[bool, str]:
            return self.app_state.performance_optimizer.run_colibri_autotune(model_dir=mpath)

        def _on_done(res: tuple[bool, str]) -> None:
            self.coli_tune_btn.setEnabled(True)
            ok, out = res
            self.tune_output.appendPlainText(out or ("Autotune finished." if ok else "Autotune exited."))

        def _on_err(err: str, _tb: str) -> None:
            self.coli_tune_btn.setEnabled(True)
            self.tune_output.appendPlainText(f"Error: {err}")

        run_in_background(_worker, on_result=_on_done, on_error=_on_err)
