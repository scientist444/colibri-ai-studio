"""Entry point for Colibri AI Studio (`main.py`).

Supports:
- Normal Desktop GUI launch (`python main.py` or `ColibriAIStudio.exe`)
- Embedded Python helper mode (`ColibriAIStudio.exe --colibri-python-helper <script> [args...]`)
  and any child `[sys.executable, <script.py>, ...]` or `[sys.executable, "-c", ...]` spawned
  by Colibri's pure-Python control plane (`coli`, `openai_server.py`, `setup_hw.py`, `doctor.py`, etc.)
  so it runs inside the packaged executable without requiring a system-wide Python installation
  or spawning unintended GUI windows.
- Packaged startup smoke test (`ColibriAIStudio.exe --smoke-test`)
"""

from __future__ import annotations

import io
import os
import runpy
import sys
from pathlib import Path


def _ensure_standard_streams() -> None:
    """Ensure sys.stdout and sys.stderr are valid streams when running under PyInstaller `--windowed`."""
    if sys.stdout is None:
        sys.stdout = io.StringIO()
    if sys.stderr is None:
        sys.stderr = io.StringIO()


def _flush_standard_streams() -> None:
    for s in (sys.stdout, sys.stderr):
        try:
            if s is not None:
                s.flush()
        except Exception:
            pass


def _run_colibri_python_helper(helper_args: list[str]) -> int:
    """Execute a Colibri control-plane Python script or `-c` snippet inside the frozen runtime."""
    os.environ["COLIBRI_PYTHON_HELPER_ACTIVE"] = "1"
    _ensure_standard_streams()
    if not helper_args:
        return 1

    if helper_args[0] == "-c":
        if len(helper_args) < 2:
            return 1
        code_str = helper_args[1]
        sys.argv = ["-c", *helper_args[2:]]
        try:
            exec(code_str, {"__name__": "__main__"})
            _flush_standard_streams()
            return 0
        except SystemExit as exc:
            _flush_standard_streams()
            code = exc.code
            return int(code) if isinstance(code, int) else (0 if code is None else 1)

    script_path = Path(helper_args[0]).resolve()
    if not script_path.exists():
        sys.stderr.write(f"Colibri helper script not found: {script_path}\n")
        _flush_standard_streams()
        return 1

    script_dir = str(script_path.parent)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)

    sys.argv = [str(script_path), *helper_args[1:]]
    try:
        runpy.run_path(str(script_path), run_name="__main__")
        _flush_standard_streams()
        return 0
    except SystemExit as exc:
        _flush_standard_streams()
        code = exc.code
        return int(code) if isinstance(code, int) else (0 if code is None else 1)


def _is_direct_script_invocation(arg1: str) -> bool:
    """Return True if arg1 is a Python script or Colibri's `coli` launcher spawned via sys.executable."""
    lower = arg1.lower()
    if lower == "-c" or lower.endswith(".py"):
        return True
    try:
        p = Path(arg1)
        if p.name.lower() in ("coli", "setup_hw.py", "doctor.py", "autotune.py", "openai_server.py"):
            return True
    except Exception:
        pass
    return False


def main() -> int:
    if len(sys.argv) >= 2 and sys.argv[1] == "--colibri-python-helper":
        return _run_colibri_python_helper(sys.argv[2:])

    if len(sys.argv) >= 2 and (
        os.environ.get("COLIBRI_PYTHON_HELPER_ACTIVE") == "1"
        or _is_direct_script_invocation(sys.argv[1])
    ):
        return _run_colibri_python_helper(sys.argv[1:])

    smoke_test = "--smoke-test" in sys.argv
    if smoke_test and "QT_QPA_PLATFORM" not in os.environ:
        pass

    from app.bootstrap import run_gui_application

    return run_gui_application(smoke_test=smoke_test)


if __name__ == "__main__":
    raise SystemExit(main())
