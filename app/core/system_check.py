"""Advanced Windows Hardware Profiler (system_check.py).

Detects CPU, RAM (physical + commit limit), GPUs (NVIDIA via NVML/nvidia-smi,
AMD/Intel via Windows WMI/DXGI/Registry, Vulkan & CUDA availability), and
Storage volumes (SSD/NVMe detection via Windows Storage APIs).
Never double-counts integrated GPU shared memory as physical RAM.
"""

from __future__ import annotations

import ctypes
import json
import logging
import os
import platform
import subprocess
import winreg
from ctypes import wintypes
from pathlib import Path
from typing import Any

import psutil

from app.constants import (
    DEFAULT_SYSTEM_RAM_RESERVE_GB,
    DEFAULT_VRAM_HEADROOM_GB,
    MIN_SAFE_SYSTEM_RAM_RESERVE_GB,
    WORKLOAD_PROFILES,
)
from app.models.hardware_models import (
    CpuProfile,
    GpuDevice,
    GpuVendor,
    RamProfile,
    StorageVolume,
    SystemHardwareProfile,
)
from app.utils.paths import get_default_models_dir

logger = logging.getLogger(__name__)

CREATE_NO_WINDOW: int = 0x08000000 if os.name == "nt" else 0


class _MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", wintypes.DWORD),
        ("dwMemoryLoad", wintypes.DWORD),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def _get_windows_cpu_brand() -> str:
    """Read exact CPU processor name from Windows Registry."""
    if os.name == "nt":
        try:
            key_path = r"HARDWARE\Description\System\CentralProcessor\0"
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                val, _ = winreg.QueryValueEx(key, "ProcessorNameString")
                if isinstance(val, str) and val.strip():
                    return val.strip()
        except OSError:
            pass
    return platform.processor() or "x86_64 Processor"


def _detect_windows_p_cores(physical_fallback: int) -> int:
    """Estimate performance cores on Windows using GetLogicalProcessorInformationEx."""
    if os.name != "nt":
        return physical_fallback
    try:
        RelationProcessorCore = 0
        kernel32 = ctypes.windll.kernel32
        length = wintypes.DWORD(0)
        kernel32.GetLogicalProcessorInformationEx(RelationProcessorCore, None, ctypes.byref(length))
        if length.value == 0:
            return physical_fallback
        buf = (ctypes.c_ubyte * length.value)()
        if not kernel32.GetLogicalProcessorInformationEx(
            RelationProcessorCore, buf, ctypes.byref(length)
        ):
            return physical_fallback
        raw = bytes(buf)
        offset = 0
        efficiencies: list[int] = []
        while offset + 8 <= len(raw):
            size = int.from_bytes(raw[offset + 4 : offset + 8], "little")
            if size <= 0 or offset + size > len(raw):
                break
            if offset + 10 <= len(raw):
                efficiency = raw[offset + 9]
                efficiencies.append(efficiency)
            offset += size
        if not efficiencies:
            return physical_fallback
        max_eff = max(efficiencies)
        p_cores = sum(1 for e in efficiencies if e == max_eff)
        return p_cores if p_cores > 0 else len(efficiencies)
    except Exception:
        return physical_fallback


def _detect_cpu_instruction_sets(cpu_name: str) -> tuple[bool, bool, bool, list[str]]:
    """Detect AVX2, AVX-512, and AVX-VNNI via Windows IsProcessorFeaturePresent."""
    features: list[str] = ["SSE2", "SSE4.2"]
    avx2 = False
    avx512 = False
    avx_vnni = False

    if os.name == "nt":
        try:
            kernel32 = ctypes.windll.kernel32
            # Windows processor feature constants:
            # PF_AVX2_INSTRUCTIONS_AVAILABLE = 40
            # PF_AVX512F_INSTRUCTIONS_AVAILABLE = 41
            if bool(kernel32.IsProcessorFeaturePresent(40)):
                avx2 = True
                features.append("AVX2")
                features.append("FMA3")
            if bool(kernel32.IsProcessorFeaturePresent(41)):
                avx512 = True
                features.append("AVX-512")
        except Exception:
            pass

    lower_name = cpu_name.lower()
    if not avx2 and any(k in lower_name for k in ("ryzen", "core(tm) i", "core ultra", "epyc", "xeon")):
        avx2 = True
        if "AVX2" not in features:
            features.append("AVX2")
    if any(k in lower_name for k in ("12th gen", "13th gen", "14th gen", "core ultra", "ryzen 7000", "ryzen 8000", "ryzen 9000", "zen 4", "zen 5")):
        avx_vnni = True
        features.append("AVX-VNNI")

    return avx2, avx512, avx_vnni, features


def detect_cpu_profile(sample_interval: float = 0.05) -> CpuProfile:
    """Detect CPU name, cores, utilization, frequency, and instruction sets."""
    name = _get_windows_cpu_brand()
    arch = platform.machine() or "AMD64"
    physical = psutil.cpu_count(logical=False) or 1
    logical = psutil.cpu_count(logical=True) or physical
    p_cores = _detect_windows_p_cores(physical)
    util = float(psutil.cpu_percent(interval=sample_interval))

    freq_mhz = 0.0
    max_freq_mhz = 0.0
    try:
        freq = psutil.cpu_freq()
        if freq:
            freq_mhz = round(float(freq.current), 1)
            max_freq_mhz = round(float(freq.max), 1)
    except Exception:
        pass

    avx2, avx512, avx_vnni, isa_list = _detect_cpu_instruction_sets(name)
    return CpuProfile(
        name=name,
        architecture=arch,
        physical_cores=physical,
        logical_cores=logical,
        performance_cores=p_cores,
        utilization_percent=round(util, 1),
        frequency_mhz=freq_mhz,
        max_frequency_mhz=max_freq_mhz,
        avx2=avx2,
        avx512=avx512,
        avx_vnni=avx_vnni,
        instruction_sets=isa_list,
    )


def detect_ram_profile(
    workload_profile: str = "balanced_desktop",
    safety_reserve_gb: float = DEFAULT_SYSTEM_RAM_RESERVE_GB,
    custom_budget_gb: float | None = None,
) -> RamProfile:
    """Detect physical RAM, Windows commit limit, and safe allocatable budget."""
    vm = psutil.virtual_memory()
    total_gb = round(vm.total / (1024**3), 2)
    avail_phys_gb = round(vm.available / (1024**3), 2)
    used_gb = round((vm.total - vm.available) / (1024**3), 2)
    util_pct = round(float(vm.percent), 1)

    commit_avail_gb = avail_phys_gb
    if os.name == "nt":
        try:
            stat = _MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                avail_phys_gb = round(stat.ullAvailPhys / (1024**3), 2)
                avail_page_gb = round(stat.ullAvailPageFile / (1024**3), 2)
                commit_avail_gb = round(min(avail_phys_gb, avail_page_gb), 2)
        except Exception:
            pass

    profile_cfg = WORKLOAD_PROFILES.get(workload_profile, WORKLOAD_PROFILES["balanced_desktop"])
    effective_reserve = float(safety_reserve_gb)
    if workload_profile != "custom":
        effective_reserve = max(
            effective_reserve, float(profile_cfg.get("system_ram_reserve_gb", 4.0))
        )

    fraction_cap = float(profile_cfg.get("ram_fraction_cap", 0.75))
    max_by_reserve = max(0.0, total_gb - effective_reserve)
    max_by_fraction = round(total_gb * fraction_cap, 2)
    # Use Colibri's conservative planning bound while allowing physical headroom
    calculated_safe = round(min(max_by_reserve, max(commit_avail_gb, max_by_fraction)), 2)

    is_unsafe = False
    warning_msg = ""
    if custom_budget_gb is not None and workload_profile == "custom":
        safe_alloc = round(float(custom_budget_gb), 2)
        if total_gb - safe_alloc < MIN_SAFE_SYSTEM_RAM_RESERVE_GB:
            is_unsafe = True
            warning_msg = (
                f"Unsafe memory budget: leaving less than {MIN_SAFE_SYSTEM_RAM_RESERVE_GB:.1f} GB "
                f"for Windows can cause system freezes or pagefile exhaustion."
            )
        elif safe_alloc > commit_avail_gb + 2.0:
            is_unsafe = True
            warning_msg = (
                f"Selected budget ({safe_alloc:.1f} GB) exceeds currently available Windows commit "
                f"memory ({commit_avail_gb:.1f} GB)."
            )
    else:
        safe_alloc = calculated_safe
        if effective_reserve < MIN_SAFE_SYSTEM_RAM_RESERVE_GB:
            is_unsafe = True
            warning_msg = (
                f"Safety reserve ({effective_reserve:.1f} GB) is below recommended minimum "
                f"({MIN_SAFE_SYSTEM_RAM_RESERVE_GB:.1f} GB)."
            )

    return RamProfile(
        total_gb=total_gb,
        available_gb=avail_phys_gb,
        used_gb=used_gb,
        utilization_percent=util_pct,
        commit_available_gb=commit_avail_gb,
        safety_reserve_gb=round(effective_reserve, 2),
        safe_allocatable_gb=max(0.5, safe_alloc),
        is_unsafe_budget=is_unsafe,
        warning_message=warning_msg,
    )


def _classify_vendor(name: str) -> GpuVendor:
    lower = name.lower()
    if "nvidia" in lower or "geforce" in lower or "quadro" in lower or "rtx" in lower or "gtx" in lower:
        return GpuVendor.NVIDIA
    if "amd" in lower or "radeon" in lower or "advanced micro" in lower:
        return GpuVendor.AMD
    if "intel" in lower or "arc" in lower or "iris" in lower or "uhd" in lower:
        return GpuVendor.INTEL
    if "microsoft" in lower or "basic render" in lower:
        return GpuVendor.MICROSOFT
    return GpuVendor.OTHER


def _is_integrated_gpu(name: str, vendor: GpuVendor, dedicated_vram_gb: float) -> bool:
    lower = name.lower()
    if vendor == GpuVendor.INTEL and "arc" not in lower:
        return True
    if any(k in lower for k in ("uhd graphics", "iris", "radeon(tm) graphics", "radeon graphics", "vega")):
        if dedicated_vram_gb <= 2.0:
            return True
    if dedicated_vram_gb < 1.5:
        return True
    return False


def _probe_vulkan_runtime() -> bool:
    """Check if Vulkan runtime library (vulkan-1.dll) is present and loadable."""
    if os.name == "nt":
        sys32 = Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "vulkan-1.dll"
        if not sys32.exists():
            return False
        try:
            ctypes.WinDLL(str(sys32))
            return True
        except OSError:
            return False
    return False


def _probe_cuda_runtime() -> bool:
    """Check if NVIDIA CUDA driver DLL (nvcuda.dll) is present and loadable."""
    if os.name == "nt":
        sys32 = Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "nvcuda.dll"
        if not sys32.exists():
            return False
        try:
            ctypes.WinDLL(str(sys32))
            return True
        except OSError:
            return False
    return False


def _detect_nvidia_gpus_nvml(vulkan_ok: bool, cuda_dll_ok: bool) -> list[GpuDevice]:
    """Query NVIDIA GPUs via pynvml (nvidia-ml-py)."""
    devices: list[GpuDevice] = []
    try:
        import pynvml  # type: ignore[import-untyped]

        pynvml.nvmlInit()
        try:
            driver_ver = pynvml.nvmlSystemGetDriverVersion()
            if isinstance(driver_ver, bytes):
                driver_ver = driver_ver.decode("utf-8", errors="replace")
            count = pynvml.nvmlDeviceGetCount()
            for idx in range(count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(idx)
                raw_name = pynvml.nvmlDeviceGetName(handle)
                if isinstance(raw_name, bytes):
                    raw_name = raw_name.decode("utf-8", errors="replace")
                mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
                total_gb = round(mem.total / (1024**3), 2)
                free_gb = round(mem.free / (1024**3), 2)
                used_gb = round(mem.used / (1024**3), 2)

                util_pct: float | None = None
                try:
                    rates = pynvml.nvmlDeviceGetUtilizationRates(handle)
                    util_pct = float(rates.gpu)
                except Exception:
                    pass

                temp_c: float | None = None
                try:
                    temp_c = float(pynvml.nvmlDeviceGetTemperature(handle, 0))
                except Exception:
                    pass

                cc_str: str | None = None
                cc_major = 0
                try:
                    major, minor = pynvml.nvmlDeviceGetCudaComputeCapability(handle)
                    cc_major = int(major)
                    cc_str = f"{major}.{minor}"
                except Exception:
                    pass

                cuda_compat = cuda_dll_ok and (cc_major >= 7 or cc_major == 0)
                devices.append(
                    GpuDevice(
                        index=idx,
                        name=str(raw_name),
                        vendor=GpuVendor.NVIDIA,
                        is_discrete=True,
                        is_integrated=False,
                        dedicated_vram_gb=total_gb,
                        available_vram_gb=free_gb,
                        used_vram_gb=used_gb,
                        shared_system_ram_gb=0.0,
                        utilization_percent=util_pct,
                        temperature_c=temp_c,
                        cuda_available=cuda_compat,
                        compute_capability=cc_str,
                        vulkan_available=vulkan_ok,
                        driver_version=str(driver_ver),
                        backend_compatible=cuda_compat or vulkan_ok,
                    )
                )
        finally:
            try:
                pynvml.nvmlShutdown()
            except Exception:
                pass
    except Exception as exc:
        logger.debug("NVML detection skipped or no NVIDIA GPU present: %s", exc)
    return devices


def _detect_windows_display_adapters(
    existing_names: set[str],
    vulkan_ok: bool,
) -> list[GpuDevice]:
    """Detect AMD, Intel, or additional Windows GPUs via Registry Video Class & PowerShell CIM."""
    devices: list[GpuDevice] = []
    if os.name != "nt":
        return devices

    # Read Windows Display Class registry keys for accurate 64-bit HardwareInformation.qwMemorySize
    # (Unlike Win32_VideoController.AdapterRAM which truncates at 4 GB uint32!)
    class_key_path = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, class_key_path) as class_key:
            subkey_idx = 0
            while True:
                try:
                    sub_name = winreg.EnumKey(class_key, subkey_idx)
                    subkey_idx += 1
                except OSError:
                    break
                if not sub_name.startswith("0"):
                    continue
                try:
                    with winreg.OpenKey(class_key, sub_name) as dev_key:
                        desc, _ = winreg.QueryValueEx(dev_key, "DriverDesc")
                        if not isinstance(desc, str) or not desc.strip():
                            continue
                        gpu_name = desc.strip()
                        if any(
                            gpu_name.lower() == ex.lower() or gpu_name.lower() in ex.lower()
                            for ex in existing_names
                        ):
                            continue
                        if "microsoft basic" in gpu_name.lower() or "remote" in gpu_name.lower():
                            continue

                        driver_ver = None
                        try:
                            dv, _ = winreg.QueryValueEx(dev_key, "DriverVersion")
                            driver_ver = str(dv)
                        except OSError:
                            pass

                        mem_bytes = 0
                        for val_name in (
                            "HardwareInformation.qwMemorySize",
                            "HardwareInformation.MemorySize",
                        ):
                            try:
                                raw_mem, _ = winreg.QueryValueEx(dev_key, val_name)
                                if isinstance(raw_mem, int) and raw_mem > 0:
                                    mem_bytes = raw_mem
                                    break
                                if isinstance(raw_mem, bytes) and len(raw_mem) in (4, 8):
                                    mem_bytes = int.from_bytes(raw_mem, "little", signed=False)
                                    if mem_bytes > 0:
                                        break
                            except OSError:
                                continue

                        dedicated_gb = round(mem_bytes / (1024**3), 2) if mem_bytes > 0 else 0.0
                        vendor = _classify_vendor(gpu_name)
                        is_igpu = _is_integrated_gpu(gpu_name, vendor, dedicated_gb)
                        # Never count integrated GPU shared memory as dedicated VRAM
                        if is_igpu and dedicated_gb <= 0.5:
                            avail_vram = 0.0
                        else:
                            avail_vram = round(max(0.0, dedicated_gb * 0.85), 2)

                        devices.append(
                            GpuDevice(
                                index=len(existing_names) + len(devices),
                                name=gpu_name,
                                vendor=vendor,
                                is_discrete=not is_igpu,
                                is_integrated=is_igpu,
                                dedicated_vram_gb=dedicated_gb,
                                available_vram_gb=avail_vram,
                                used_vram_gb=round(max(0.0, dedicated_gb - avail_vram), 2),
                                shared_system_ram_gb=0.0,
                                utilization_percent=None,
                                temperature_c=None,
                                cuda_available=False,
                                compute_capability=None,
                                vulkan_available=vulkan_ok,
                                driver_version=driver_ver,
                                backend_compatible=vulkan_ok and not is_igpu and dedicated_gb >= 4.0,
                            )
                        )
                        existing_names.add(gpu_name)
                except OSError:
                    continue
    except OSError as exc:
        logger.debug("Registry display adapter scan skipped: %s", exc)

    return devices


def detect_gpus() -> list[GpuDevice]:
    """Detect all installed GPUs with dedicated VRAM, CUDA, and Vulkan capabilities."""
    vulkan_ok = _probe_vulkan_runtime()
    cuda_ok = _probe_cuda_runtime()

    gpus = _detect_nvidia_gpus_nvml(vulkan_ok=vulkan_ok, cuda_dll_ok=cuda_ok)
    existing = {g.name for g in gpus}
    other_gpus = _detect_windows_display_adapters(existing, vulkan_ok=vulkan_ok)
    gpus.extend(other_gpus)
    return gpus


def _query_windows_physical_disks() -> dict[str, tuple[str, str]]:
    """Query Windows physical disk MediaType and BusType via PowerShell Storage cmdlet once."""
    result: dict[str, tuple[str, str]] = {}
    if os.name != "nt":
        return result
    try:
        cmd = [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            (
                "Get-Partition | Where-Object { $_.DriveLetter } | ForEach-Object { "
                "$d = Get-PhysicalDisk -Number $_.DiskNumber -ErrorAction SilentlyContinue; "
                "if ($d) { [PSCustomObject]@{ Drive=$_.DriveLetter; Media=$d.MediaType; Bus=$d.BusType } } "
                "} | ConvertTo-Json -Compress"
            ),
        ]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3.5,
            creationflags=CREATE_NO_WINDOW,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            data = json.loads(proc.stdout.strip())
            items = data if isinstance(data, list) else [data]
            for item in items:
                if isinstance(item, dict) and item.get("Drive"):
                    drv = str(item["Drive"]).upper().rstrip(":\\")
                    media = str(item.get("Media") or "SSD")
                    bus = str(item.get("Bus") or "NVMe")
                    result[drv] = (media, bus)
    except Exception as exc:
        logger.debug("Physical disk query fallback: %s", exc)
    return result


_DISK_TYPE_CACHE: dict[str, tuple[str, str]] | None = None


def detect_storage_volumes(include_disk_types: bool = True) -> list[StorageVolume]:
    """Detect accessible storage volumes, free capacity, and SSD/NVMe traits."""
    global _DISK_TYPE_CACHE
    if include_disk_types and _DISK_TYPE_CACHE is None:
        _DISK_TYPE_CACHE = _query_windows_physical_disks()
    disk_types = _DISK_TYPE_CACHE or {}

    volumes: list[StorageVolume] = []
    for part in psutil.disk_partitions(all=False):
        if "cdrom" in part.opts.lower() or not part.fstype:
            continue
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except OSError:
            continue

        drv_key = part.device.upper().rstrip(":\\")
        media_type, bus_type = disk_types.get(drv_key, ("SSD", "SATA/NVMe"))
        is_nvme = "nvme" in bus_type.lower()
        is_ssd = is_nvme or "ssd" in media_type.lower() or "hdd" not in media_type.lower()

        total_gb = round(usage.total / (1024**3), 2)
        free_gb = round(usage.free / (1024**3), 2)
        used_gb = round(usage.used / (1024**3), 2)

        volumes.append(
            StorageVolume(
                drive_letter=part.device,
                mount_point=part.mountpoint,
                filesystem=part.fstype,
                total_gb=total_gb,
                free_gb=free_gb,
                used_gb=used_gb,
                percent_used=round(float(usage.percent), 1),
                bus_type=bus_type,
                media_type=media_type,
                is_ssd=is_ssd,
                is_nvme=is_nvme,
            )
        )
    return volumes


class HardwareProfiler:
    """High-level service for full hardware profiling and live telemetry updates."""

    def __init__(self) -> None:
        self._cached_profile: SystemHardwareProfile | None = None

    def scan_system(
        self,
        workload_profile: str = "balanced_desktop",
        safety_reserve_gb: float = DEFAULT_SYSTEM_RAM_RESERVE_GB,
        custom_ram_budget_gb: float | None = None,
        vram_headroom_gb: float = DEFAULT_VRAM_HEADROOM_GB,
    ) -> SystemHardwareProfile:
        """Perform a complete hardware scan and compute recommended settings."""
        cpu = detect_cpu_profile(sample_interval=0.05)
        ram = detect_ram_profile(
            workload_profile=workload_profile,
            safety_reserve_gb=safety_reserve_gb,
            custom_budget_gb=custom_ram_budget_gb,
        )
        gpus = detect_gpus()
        volumes = detect_storage_volumes(include_disk_types=True)

        cuda_avail = any(g.cuda_available and g.dedicated_vram_gb >= 4.0 for g in gpus)
        vulkan_avail = any(g.vulkan_available and g.is_discrete and g.dedicated_vram_gb >= 4.0 for g in gpus)

        if cuda_avail:
            rec_backend = "cuda"
        elif vulkan_avail:
            rec_backend = "vulkan"
        else:
            rec_backend = "cpu"

        # Recommend model storage directory on the fastest SSD/NVMe with largest free space
        default_models = str(get_default_models_dir())
        best_vol: StorageVolume | None = None
        ssd_vols = [v for v in volumes if v.is_ssd and v.free_gb >= 25.0]
        if ssd_vols:
            best_vol = max(ssd_vols, key=lambda v: (1 if v.is_nvme else 0, v.free_gb))
        elif volumes:
            best_vol = max(volumes, key=lambda v: v.free_gb)

        rec_dir = default_models
        if best_vol:
            default_drive = Path(default_models).drive.upper()
            best_drive = best_vol.drive_letter.upper().rstrip("\\")
            if default_drive and best_drive and default_drive != best_drive and best_vol.free_gb > 50.0:
                rec_dir = str(Path(best_vol.mount_point) / "ColibriAIStudio" / "models")

        profile = SystemHardwareProfile(
            os_name=platform.system(),
            os_version=platform.version(),
            os_release=platform.release(),
            cpu=cpu,
            ram=ram,
            gpus=gpus,
            volumes=volumes,
            cuda_available=cuda_avail,
            vulkan_available=vulkan_avail,
            recommended_backend=rec_backend,
            recommended_models_dir=rec_dir,
            workload_profile=workload_profile,
        )
        self._cached_profile = profile
        return profile

    def refresh_live_telemetry(
        self,
        workload_profile: str = "balanced_desktop",
        safety_reserve_gb: float = DEFAULT_SYSTEM_RAM_RESERVE_GB,
        custom_ram_budget_gb: float | None = None,
    ) -> SystemHardwareProfile:
        """Fast non-blocking telemetry refresh for Hardware Monitor gauges."""
        if self._cached_profile is None:
            return self.scan_system(
                workload_profile=workload_profile,
                safety_reserve_gb=safety_reserve_gb,
                custom_ram_budget_gb=custom_ram_budget_gb,
            )

        cpu_util = float(psutil.cpu_percent(interval=None))
        freq_mhz = self._cached_profile.cpu.frequency_mhz
        try:
            freq = psutil.cpu_freq()
            if freq:
                freq_mhz = round(float(freq.current), 1)
        except Exception:
            pass

        updated_cpu = self._cached_profile.cpu.model_copy(
            update={"utilization_percent": round(cpu_util, 1), "frequency_mhz": freq_mhz}
        )
        updated_ram = detect_ram_profile(
            workload_profile=workload_profile,
            safety_reserve_gb=safety_reserve_gb,
            custom_budget_gb=custom_ram_budget_gb,
        )
        updated_gpus = detect_gpus()
        updated_vols = detect_storage_volumes(include_disk_types=False)

        self._cached_profile = self._cached_profile.model_copy(
            update={
                "cpu": updated_cpu,
                "ram": updated_ram,
                "gpus": updated_gpus,
                "volumes": updated_vols,
                "workload_profile": workload_profile,
            }
        )
        return self._cached_profile

    def get_colibri_native_hw_summary(self) -> dict[str, Any]:
        """Invoke Colibri's native `setup_hw.detect()` if available for cross-checking."""
        try:
            import sys
            from app.utils.paths import get_bundled_colibri_runtime_dir

            rt_dir = str(get_bundled_colibri_runtime_dir())
            if rt_dir not in sys.path:
                sys.path.insert(0, rt_dir)
            import setup_hw  # type: ignore[import-not-found]

            hw = setup_hw.detect()
            return dict(hw.__dict__)
        except Exception as exc:
            logger.debug("Colibri setup_hw import fallback: %s", exc)
            return {}
