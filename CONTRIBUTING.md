# Contributing to Colibri AI Studio

Thank you for your interest in contributing to **Colibri AI Studio**!

## Development Setup (Windows 10/11)

1. Ensure Python **3.11+** is installed.
2. Create and activate a virtual environment:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
3. Install dependencies:
   ```powershell
   pip install -r requirements-dev.txt
   ```
4. Run the test suite:
   ```powershell
   pytest tests
   ```

## Coding & Design Standards

- **Type Hints:** Use full Python type hints across all modules.
- **No Blocking on the Main Thread:** Network requests, downloads, hardware benchmarks, and inference streaming must run inside `QThread` workers or asynchronous helpers.
- **Professional Workstation UI:** All UI modules under `app/ui/` must remain emoji-free (`test_no_emojis_in_ui_codebase` enforces this) and respect all 5 Liquid Glass themes in `app/ui/liquid_glass.py`.
- **Colibri Engine Isolation:** Keep Colibri CLI/API interactions isolated inside `app/core/backend_adapter.py`, `app/core/colibri_manager.py`, and `app/core/colibri_api.py`.

## Pull Request Checklist

- [ ] `pytest tests` passes with zero failures.
- [ ] New features include unit or `pytest-qt` tests.
- [ ] Documentation (`README.md` / docstrings) is updated where relevant.
