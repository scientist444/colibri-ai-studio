"""Liquid Glass Hardware Monitor View (`hardware_view.py`) — Emoji-Free."""

from __future__ import annotations

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.application_state import ApplicationState
from app.core.compatibility import CompatibilityEngine
from app.ui.liquid_glass import LiquidGlassPanel
from app.ui.widgets.gauge_widget import TelemetryGaugeCard, ThreeTierPlacementDiagram


class HardwareMonitorView(QWidget):
    """Real-time Liquid Glass Hardware & 3-Tier Inference Placement Monitor."""

    def __init__(self, app_state: ApplicationState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.app_state = app_state

        self._build_ui()
        self.refresh_telemetry()

        # Poll live non-blocking telemetry every 2.0 seconds
        self._timer = QTimer(self)
        self._timer.setInterval(2000)
        self._timer.timeout.connect(self.refresh_telemetry)
        self._timer.start()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Header
        header = LiquidGlassPanel(self, radius=16.0, elevated=True)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(18, 12, 18, 12)

        title_col = QVBoxLayout()
        title_lbl = QLabel("Hardware & 3-Tier Placement Monitor")
        title_lbl.setObjectName("viewTitle")
        sub_lbl = QLabel(
            "Live CPU, RAM, GPU VRAM, NVMe Storage & Colibri Hierarchical Expert Placement Telemetry"
        )
        sub_lbl.setObjectName("viewSubtitle")
        title_col.addWidget(title_lbl)
        title_col.addWidget(sub_lbl)
        h_layout.addLayout(title_col, 1)

        rescan_btn = QPushButton("Full Hardware Scan")
        rescan_btn.clicked.connect(self._full_rescan)
        h_layout.addWidget(rescan_btn)
        layout.addWidget(header)

        # Liquid Glass Tabs: Live Overview & 3-Tier Diagram vs Detailed Device Tables
        self.tabs = QTabWidget()

        # Tab 1: Live Telemetry & 3-Tier Placement Diagram
        overview_tab = QWidget()
        o_layout = QVBoxLayout(overview_tab)
        o_layout.setContentsMargins(8, 8, 8, 8)
        o_layout.setSpacing(12)

        gauges_grid = QGridLayout()
        gauges_grid.setSpacing(12)

        self.cpu_gauge = TelemetryGaugeCard("CPU Utilization & Cores")
        self.ram_gauge = TelemetryGaugeCard("System RAM & Safe Budget")
        self.gpu_gauge = TelemetryGaugeCard("GPU Compute & Backend")
        self.vram_gauge = TelemetryGaugeCard("Dedicated GPU VRAM")
        self.storage_gauge = TelemetryGaugeCard("Model Storage Volume")
        self.runtime_gauge = TelemetryGaugeCard("Colibri Active Runtime")

        gauges_grid.addWidget(self.cpu_gauge, 0, 0)
        gauges_grid.addWidget(self.ram_gauge, 0, 1)
        gauges_grid.addWidget(self.gpu_gauge, 0, 2)
        gauges_grid.addWidget(self.vram_gauge, 1, 0)
        gauges_grid.addWidget(self.storage_gauge, 1, 1)
        gauges_grid.addWidget(self.runtime_gauge, 1, 2)
        o_layout.addLayout(gauges_grid)

        # 3-Tier Placement Visual Diagram
        self.tier_diagram = ThreeTierPlacementDiagram(overview_tab)
        o_layout.addWidget(self.tier_diagram, 1)

        self.tabs.addTab(overview_tab, "Live Telemetry & 3-Tier Placement")

        # Tab 2: Detailed GPUs & Storage Volumes Inspector
        devices_tab = QWidget()
        d_layout = QVBoxLayout(devices_tab)
        d_layout.setContentsMargins(8, 8, 8, 8)
        d_layout.setSpacing(12)

        gpu_title = QLabel("Detected Graphics Adapters (Discrete & Integrated)")
        gpu_title.setObjectName("sectionHeader")
        d_layout.addWidget(gpu_title)

        self.gpu_table = QTableWidget(0, 7)
        self.gpu_table.setHorizontalHeaderLabels(
            ["GPU Name", "Vendor", "Type", "Dedicated VRAM", "Available VRAM", "Backends", "Driver"]
        )
        self.gpu_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)  # type: ignore[union-attr]
        d_layout.addWidget(self.gpu_table)

        vol_title = QLabel("Detected Windows Storage Volumes")
        vol_title.setObjectName("sectionHeader")
        d_layout.addWidget(vol_title)

        self.vol_table = QTableWidget(0, 6)
        self.vol_table.setHorizontalHeaderLabels(
            ["Drive", "Filesystem", "Media / Bus Type", "Total Capacity", "Free Space", "Utilization"]
        )
        self.vol_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)  # type: ignore[union-attr]
        d_layout.addWidget(self.vol_table)

        self.tabs.addTab(devices_tab, "GPU & Storage Device Inspector")
        layout.addWidget(self.tabs, 1)

    def _full_rescan(self) -> None:
        self.app_state.hardware = self.app_state.hardware_profiler.scan_system(
            workload_profile=self.app_state.settings.workload_profile,
            safety_reserve_gb=self.app_state.settings.system_ram_reserve_gb,
            custom_ram_budget_gb=self.app_state.settings.custom_ram_budget_gb,
        )
        self.refresh_telemetry()

    def refresh_telemetry(self) -> None:
        hw = self.app_state.hardware_profiler.refresh_live_telemetry(
            workload_profile=self.app_state.settings.workload_profile,
            safety_reserve_gb=self.app_state.settings.system_ram_reserve_gb,
            custom_ram_budget_gb=self.app_state.settings.custom_ram_budget_gb,
        )
        self.app_state.hardware = hw

        self.cpu_gauge.update_metric(
            percent=hw.cpu.utilization_percent,
            value_text=f"{hw.cpu.utilization_percent:.1f}%",
            subtitle=hw.cpu.name,
            detail=(
                f"{hw.cpu.physical_cores} Physical ({hw.cpu.performance_cores} P-Cores) / "
                f"{hw.cpu.logical_cores} Logical  |  ISA: {', '.join(hw.cpu.instruction_sets[:3])}"
            ),
        )

        self.ram_gauge.update_metric(
            percent=hw.ram.utilization_percent,
            value_text=f"{hw.ram.used_gb:.1f} / {hw.ram.total_gb:.1f} GB",
            subtitle=f"Safe Inference Budget: {hw.ram.safe_allocatable_gb:.1f} GB",
            detail=(
                f"Available Commit: {hw.ram.commit_available_gb:.1f} GB  |  "
                f"Windows Reserve: {hw.ram.safety_reserve_gb:.1f} GB ({hw.workload_profile})"
            ),
        )

        gpu = hw.primary_gpu
        if gpu:
            util_str = f"{gpu.utilization_percent:.0f}%" if gpu.utilization_percent is not None else "Not available"
            temp_str = f"{gpu.temperature_c:.0f} C" if gpu.temperature_c is not None else "Not available"
            self.gpu_gauge.update_metric(
                percent=gpu.utilization_percent,
                value_text=util_str,
                subtitle=gpu.name,
                detail=f"Backend: {hw.recommended_backend.upper()}  |  Temp: {temp_str}  |  Driver: {gpu.driver_version or 'Standard'}",
            )
            vram_pct = (
                (gpu.used_vram_gb / gpu.dedicated_vram_gb) * 100.0
                if gpu.dedicated_vram_gb > 0
                else 0.0
            )
            self.vram_gauge.update_metric(
                percent=vram_pct,
                value_text=f"{gpu.dedicated_vram_gb:.1f} GB",
                subtitle=(
                    f"Available Dedicated: {gpu.available_vram_gb:.1f} GB"
                    if gpu.is_discrete
                    else "Integrated GPU (Uses System RAM)"
                ),
                detail="Shared iGPU memory is never double-counted as physical VRAM.",
            )
        else:
            self.gpu_gauge.update_metric(
                percent=None,
                value_text="CPU Mode",
                subtitle="No Discrete GPU Detected",
                detail="Colibri AVX2/AVX-VNNI CPU engine active",
            )
            self.vram_gauge.update_metric(
                percent=0.0,
                value_text="0.0 GB",
                subtitle="Not available (CPU Only)",
                detail="All resident weights and expert caches placed in System RAM",
            )

        if hw.volumes:
            vol = hw.volumes[0]
            self.storage_gauge.update_metric(
                percent=vol.percent_used,
                value_text=f"{vol.free_gb:.1f} GB Free",
                subtitle=f"Drive {vol.drive_letter} ({'NVMe SSD' if vol.is_nvme else ('SSD' if vol.is_ssd else 'HDD')})",
                detail=f"Total: {vol.total_gb:.1f} GB  |  Models Dir: {self.app_state.settings.models_dir}",
            )

        pm = self.app_state.process_manager
        st = pm.state.value
        active_mod = pm.active_model_id or "No Active Model"
        self.runtime_gauge.update_metric(
            percent=100.0 if st == "RUNNING" else 0.0,
            value_text=st,
            subtitle=f"Active Model: {active_mod}",
            detail=pm.state_detail or "Idle",
        )

        cand = self.app_state.catalog_candidates[0] if self.app_state.catalog_candidates else None
        summary = CompatibilityEngine.compute_tier_placement(
            model_path=pm.active_model_path or self.app_state.settings.active_model_path or None,
            candidate=cand,
            hardware=hw,
            ctx_tokens=self.app_state.settings.context_length,
            policy=self.app_state.settings.retention_policy,
            custom_ram_gb=self.app_state.settings.custom_ram_budget_gb,
            custom_vram_gb=self.app_state.settings.custom_vram_budget_gb,
        )
        self.tier_diagram.set_summary(summary)

        self.gpu_table.setRowCount(len(hw.gpus))
        for r, g in enumerate(hw.gpus):
            b_list = []
            if g.cuda_available:
                b_list.append("CUDA")
            if g.vulkan_available:
                b_list.append("Vulkan")
            vals = [
                g.name,
                g.vendor.value,
                "Discrete" if g.is_discrete else "Integrated",
                f"{g.dedicated_vram_gb:.2f} GB",
                f"{g.available_vram_gb:.2f} GB",
                ", ".join(b_list) or "None",
                g.driver_version or "Unknown",
            ]
            for c_idx, val in enumerate(vals):
                self.gpu_table.setItem(r, c_idx, QTableWidgetItem(val))

        self.vol_table.setRowCount(len(hw.volumes))
        for r, v in enumerate(hw.volumes):
            vals = [
                v.drive_letter,
                v.filesystem,
                f"{v.media_type} ({v.bus_type})",
                f"{v.total_gb:.1f} GB",
                f"{v.free_gb:.1f} GB",
                f"{v.percent_used:.1f}%",
            ]
            for c_idx, val in enumerate(vals):
                self.vol_table.setItem(r, c_idx, QTableWidgetItem(val))
