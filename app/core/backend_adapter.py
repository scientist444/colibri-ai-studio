"""Colibri Backend Adapter (backend_adapter.py).

Isolates all Colibri CLI invocations (`coli setup`, `coli status`, `coli doctor`,
`coli plan`, `coli tune`, `coli import`, `coli serve`, `coli stop`) and version detection.
Supports running Colibri's pure-Python control plane in both source mode and frozen
PyInstaller mode (via `--colibri-python-helper`) so no system-wide Python is required.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from app.utils.paths import (
    get_bundled_colibri_runtime_dir,
    get_default_engine_dir,
    is_frozen,
)

logger = logging.getLogger(__name__)

CREATE_NO_WINDOW: int = 0x08000000 if os.name == "nt" else 0


class ColibriBackendAdapter:
    """Adapter layer isolating Colibri CLI and runtime scripts from the GUI."""

    def __init__(self, engine_dir: Path | str | None = None) -> None:
        self.engine_dir: Path = Path(engine_dir) if engine_dir else get_default_engine_dir()
        self.engine_dir.mkdir(parents=True, exist_ok=True)
        self.ensure_control_plane_provisioned()

    def ensure_control_plane_provisioned(self) -> None:
        """Copy bundled official Colibri Python control-plane scripts into `engine_dir` if missing."""
        bundled = get_bundled_colibri_runtime_dir()
        if not bundled.exists():
            return
        coli_target = self.engine_dir / "coli"
        version_target = self.engine_dir / "version.py"
        if not coli_target.exists() or not version_target.exists():
            try:
                for item in bundled.iterdir():
                    dest = self.engine_dir / item.name
                    if item.is_dir():
                        shutil.copytree(item, dest, dirs_exist_ok=True)
                    else:
                        shutil.copy2(item, dest)
            except Exception as exc:
                logger.warning("Failed provisioning Colibri control-plane scripts: %s", exc)

    def get_python_runner_prefix(self) -> list[str]:
        """Return command prefix to execute a Python script even inside a frozen PyInstaller exe."""
        if is_frozen():
            return [sys.executable, "--colibri-python-helper"]
        return [sys.executable]

    def build_coli_command(self, args: list[str]) -> list[str]:
        """Build a full command line to invoke `coli` with the given arguments."""
        coli_script = self.engine_dir / "coli"
        if not coli_script.exists():
            coli_script = get_bundled_colibri_runtime_dir() / "coli"
        return [*self.get_python_runner_prefix(), str(coli_script), *args]

    def get_version(self) -> str:
        """Detect installed Colibri version."""
        for base in (self.engine_dir, get_bundled_colibri_runtime_dir()):
            ver_file = base / "version.py"
            if ver_file.exists():
                try:
                    namespace: dict[str, Any] = {}
                    exec(ver_file.read_text(encoding="utf-8"), namespace)
                    for key in ("__version__", "COLIBRI_VERSION", "VERSION"):
                        if key in namespace:
                            return str(namespace[key])
                except Exception:
                    pass
        return "unknown"

    def detect_installed_engine_binaries(self) -> dict[str, Any]:
        """Inspect `engine_dir` for native Colibri C inference binaries and GPU libraries."""
        binaries: list[str] = []
        for exe_name in (
            "colibri.exe",
            "qwen36.exe",
            "qwen38.exe",
            "deepseek_v4.exe",
            "deepseek_v41.exe",
            "glm53.exe",
            "mimo.exe",
            "inkling.exe",
            "kimi_k3.exe",
            "olmoe.exe",
            "qwenimage.exe",
        ):
            if (self.engine_dir / exe_name).exists():
                binaries.append(exe_name)

        has_control_plane = (self.engine_dir / "coli").exists() and (
            self.engine_dir / "openai_server.py"
        ).exists()
        has_vulkan_shaders = (self.engine_dir / "shaders").is_dir() and any(
            (self.engine_dir / "shaders").glob("*.spv")
        )
        has_cuda_dll = (self.engine_dir / "coli_cuda.dll").exists()

        return {
            "engine_dir": str(self.engine_dir),
            "version": self.get_version(),
            "control_plane_ready": has_control_plane,
            "native_binaries": binaries,
            "has_native_binaries": len(binaries) > 0,
            "has_vulkan_shaders": has_vulkan_shaders,
            "has_cuda_plugin": has_cuda_dll,
        }

    def run_coli_json(self, args: list[str], timeout: float = 30.0) -> dict[str, Any]:
        """Execute a `coli` command with `--json` and parse its output."""
        cmd = self.build_coli_command(args)
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        proc = subprocess.run(
            cmd,
            cwd=str(self.engine_dir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
            creationflags=CREATE_NO_WINDOW,
        )
        stdout = proc.stdout.strip()
        if stdout:
            try:
                parsed = json.loads(stdout)
                return parsed if isinstance(parsed, dict) else {"items": parsed}
            except json.JSONDecodeError:
                # Locate first JSON object or array in stdout
                for start_char, end_char in (("{", "}"), ("[", "]")):
                    s_idx = stdout.find(start_char)
                    e_idx = stdout.rfind(end_char)
                    if s_idx != -1 and e_idx > s_idx:
                        try:
                            parsed = json.loads(stdout[s_idx : e_idx + 1])
                            return parsed if isinstance(parsed, dict) else {"items": parsed}
                        except json.JSONDecodeError:
                            pass
        return {
            "returncode": proc.returncode,
            "stdout": stdout,
            "stderr": proc.stderr.strip(),
        }

    def run_doctor(
        self,
        model_dir: Path | str | None = None,
        deep: bool = False,
        ram_gb: float | None = None,
        ctx_tokens: int | None = None,
    ) -> dict[str, Any]:
        """Run `coli doctor --json` for a model directory or general engine diagnostics."""
        if model_dir and Path(model_dir).exists():
            args = ["doctor", "--model", str(model_dir), "--json"]
            if deep:
                args.append("--deep")
            if ram_gb is not None and ram_gb > 0:
                args.extend(["--ram", str(ram_gb)])
            if ctx_tokens is not None and ctx_tokens > 0:
                args.extend(["--ctx", str(ctx_tokens)])
            return self.run_coli_json(args, timeout=45.0)
        return self.detect_installed_engine_binaries()

    def run_plan(
        self,
        model_dir: Path | str,
        ram_gb: float | None = None,
        vram_gb: float | None = None,
        ctx_tokens: int = 4096,
        policy: str = "balanced",
    ) -> dict[str, Any]:
        """Run `coli plan --model <dir> --json`."""
        args = ["plan", "--model", str(model_dir), "--json", "--ctx", str(ctx_tokens), "--policy", policy]
        if ram_gb is not None and ram_gb > 0:
            args.extend(["--ram", str(ram_gb)])
        if vram_gb is not None and vram_gb >= 0:
            args.extend(["--vram", str(vram_gb)])
        return self.run_coli_json(args, timeout=30.0)

    def run_status(self) -> dict[str, Any]:
        """Run `coli status --json`."""
        return self.run_coli_json(["status", "--json"], timeout=10.0)

    def import_gguf(
        self,
        gguf_path: Path | str,
        output_dir: Path | str,
        mode: str = "link",
    ) -> tuple[bool, str]:
        """Import a `.gguf` file or directory into Colibri format using `coli import`."""
        args = ["import", str(gguf_path), "--out", str(output_dir), "--mode", mode]
        cmd = self.build_coli_command(args)
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(self.engine_dir),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=600.0,
                env=env,
                creationflags=CREATE_NO_WINDOW,
            )
            combined = (proc.stdout + "\n" + proc.stderr).strip()
            return proc.returncode == 0, combined
        except Exception as exc:
            return False, str(exc)

    def inspect_gguf_architecture(self, gguf_path: Path | str) -> dict[str, Any]:
        """Read GGUF header metadata using Colibri's `tools/gguf_header.py`."""
        try:
            rt_tools = str(get_bundled_colibri_runtime_dir() / "tools")
            if rt_tools not in sys.path:
                sys.path.insert(0, rt_tools)
            import gguf_header  # type: ignore[import-not-found]

            hdr = gguf_header.read_gguf_header(str(gguf_path))
            arch = str(hdr.metadata.get("general.architecture") or "")
            name = str(hdr.metadata.get("general.name") or Path(gguf_path).stem)
            return {
                "valid_gguf": True,
                "architecture": arch,
                "name": name,
                "tensor_count": hdr.n_tensors,
                "version": hdr.version,
            }
        except Exception as exc:
            return {"valid_gguf": False, "error": str(exc)}
