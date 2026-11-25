"""Automated Build, Packaging, Smoke-Test & Windows Desktop Deployment Script (`scripts/build_deploy.py`).

Steps:
1. Verify Python 3.11+ environment and dependencies
2. Run the automated `pytest` test suite
3. Package `dist/ColibriAIStudio.exe` with PyInstaller (`--onefile --windowed`) bundling `assets/` and `app/ui/theme.qss`
4. Run packaged executable startup smoke test (`dist/ColibriAIStudio.exe --smoke-test`)
5. Run packaged Colibri Python helper verification (`dist/ColibriAIStudio.exe --colibri-python-helper ...`)
6. Create and verify the Windows Desktop shortcut (`Colibri AI Studio.lnk`)
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.utils.windows_shortcut import (  # noqa: E402
    create_desktop_shortcut,
    get_windows_desktop_dir,
    verify_desktop_shortcut,
)
from scripts.generate_logo import generate_all_logo_assets  # noqa: E402


def run_step(description: str, cmd: list[str], cwd: Path = ROOT_DIR) -> None:
    print(f"\n=== {description} ===")
    print("Command:", " ".join(f'"{c}"' if " " in c else c for c in cmd))
    proc = subprocess.run(cmd, cwd=str(cwd))
    if proc.returncode != 0:
        raise RuntimeError(f"Step failed ({description}) with exit code {proc.returncode}")


def build_and_deploy(skip_tests: bool = False) -> dict[str, str]:
    python_exe = sys.executable
    dist_dir = ROOT_DIR / "dist"
    build_dir = ROOT_DIR / "build"

    print("\n=== Generating Official Colibri AI Studio Logo Assets (SVG, PNG, ICO) ===")
    logo_paths = generate_all_logo_assets()
    icon_path = logo_paths["ico"]
    print(f"Logo assets ready: {icon_path}")

    if not skip_tests:
        run_step("Running Automated Test Suite (pytest)", [python_exe, "-m", "pytest", "tests"])

    # Build PyInstaller command
    sep = ";" if os.name == "nt" else ":"
    pyinstaller_cmd = [
        python_exe,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name",
        "ColibriAIStudio",
        "--distpath",
        str(dist_dir),
        "--workpath",
        str(build_dir),
        "--add-data",
        f"{ROOT_DIR / 'assets'}{sep}assets",
        "--add-data",
        f"{ROOT_DIR / 'app' / 'ui' / 'theme.qss'}{sep}app/ui",
        "--hidden-import",
        "pynvml",
        "--hidden-import",
        "keyring.backends.Windows",
        "--hidden-import",
        "win32com.client",
        "--hidden-import",
        "pythoncom",
    ]
    if icon_path.exists():
        pyinstaller_cmd.extend(["--icon", str(icon_path)])
    pyinstaller_cmd.append(str(ROOT_DIR / "main.py"))

    run_step("Packaging Standalone Windows Executable (PyInstaller)", pyinstaller_cmd)

    exe_path = dist_dir / "ColibriAIStudio.exe"
    if not exe_path.exists():
        raise FileNotFoundError(f"Expected packaged executable not found at: {exe_path}")

    # Verify packaged embedded Python helper (`--colibri-python-helper`)
    coli_script = ROOT_DIR / "assets" / "colibri_runtime" / "coli"
    run_step(
        "Verifying Packaged Embedded Colibri Python Helper (--colibri-python-helper)",
        [str(exe_path), "--colibri-python-helper", str(coli_script), "setup", "--list", "--json"],
    )

    # Verify packaged GUI startup smoke test (`--smoke-test`)
    run_step(
        "Running Packaged Executable GUI Startup Smoke Test (--smoke-test)",
        [str(exe_path), "--smoke-test"],
    )

    # Create and verify Windows Desktop Shortcut (`Colibri AI Studio.lnk`)
    print("\n=== Creating & Verifying Windows Desktop Shortcut ===")
    desktop_dir = get_windows_desktop_dir()
    shortcut_path = create_desktop_shortcut(
        target_exe=exe_path,
        working_dir=dist_dir,
        icon_path=icon_path if icon_path.exists() else exe_path,
        shortcut_name="Colibri AI Studio.lnk",
        desktop_dir=desktop_dir,
    )
    verified = verify_desktop_shortcut(shortcut_path)
    print(f"Shortcut created at: {verified['shortcut_path']}")
    print(f"Shortcut target:     {verified['target_path']}")
    print(f"Working directory:   {verified['working_directory']}")

    return {
        "executable_path": str(exe_path),
        "executable_size_mb": f"{exe_path.stat().st_size / (1024 * 1024):.2f} MB",
        "shortcut_path": str(shortcut_path),
        "shortcut_target": verified["target_path"],
    }


if __name__ == "__main__":
    skip = "--skip-tests" in sys.argv
    summary = build_and_deploy(skip_tests=skip)
    print("\n=== DEPLOYMENT COMPLETE ===")
    for k, v in summary.items():
        print(f"  {k}: {v}")
