"""Verification script for packaged `dist/ColibriAIStudio.exe` and Desktop Shortcut (`scripts/verify_build.py`)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.utils.windows_shortcut import get_windows_desktop_dir, verify_desktop_shortcut  # noqa: E402


def verify_all() -> int:
    exe_path = ROOT_DIR / "dist" / "ColibriAIStudio.exe"
    if not exe_path.exists():
        print(f"[FAIL] Executable missing: {exe_path}")
        return 1

    size_mb = exe_path.stat().st_size / (1024 * 1024)
    print(f"[OK] Executable exists: {exe_path} ({size_mb:.2f} MB)")

    # 1. Smoke test GUI launch
    proc = subprocess.run([str(exe_path), "--smoke-test"], cwd=str(ROOT_DIR))
    if proc.returncode != 0:
        print(f"[FAIL] GUI smoke test failed with code {proc.returncode}")
        return 1
    print("[OK] Packaged GUI startup smoke test passed (--smoke-test)")

    # 2. Verify Desktop shortcut
    shortcut_path = get_windows_desktop_dir() / "Colibri AI Studio.lnk"
    if not shortcut_path.exists():
        print(f"[FAIL] Desktop shortcut missing: {shortcut_path}")
        return 1

    info = verify_desktop_shortcut(shortcut_path)
    print(f"[OK] Desktop shortcut verified: {info['shortcut_path']} -> {info['target_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(verify_all())
