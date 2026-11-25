# Third-Party Licenses & Attribution Notices

**Colibri AI Studio** integrates with the open-source **Colibri** inference engine and uses the following open-source libraries:

---

## 1. Colibri Inference Engine
- **Project:** [JustVugg/colibri](https://github.com/JustVugg/colibri)
- **License:** Apache License 2.0
- **Usage:** Official Colibri Python control-plane scripts (`coli`, `setup_catalog.py`, `setup_hw.py`, `resource_plan.py`, `family_registry.py`, `doctor.py`, `autotune.py`, `openai_server.py`, `tools/gguf_import.py`) and prebuilt Windows inference binaries downloaded on user request.

---

## 2. Python Runtime & Libraries

| Package | License | Purpose |
|---|---|---|
| **PyQt6** | GPL v3 / Riverbank Commercial | Desktop GUI framework |
| **psutil** | BSD-3-Clause | CPU, RAM, disk, and process telemetry |
| **nvidia-ml-py (`pynvml`)** | BSD-3-Clause | NVIDIA GPU & VRAM telemetry |
| **httpx** | BSD-3-Clause | Asynchronous/streaming HTTP & SSE client |
| **huggingface_hub** | Apache-2.0 | Hugging Face model metadata discovery |
| **Pydantic** | MIT | Settings and data model validation |
| **markdown-it-py** | MIT | Safe CommonMark Markdown parsing |
| **Pygments** | BSD-2-Clause | Code block syntax highlighting |
| **keyring** | MIT | Windows Credential Manager integration |
| **pywin32** | PSF | Windows Shell COM `.lnk` desktop shortcut creation |
| **Pillow** | HPND / MIT-CMU | Icon and image asset generation |
| **PyInstaller** | GPLv2-or-later with Bootloader Exception | Standalone Windows `.exe` packaging |
| **pytest / pytest-qt** | MIT | Automated unit and GUI test suite |

---

## 3. Model Weights Notice
Model weights discovered or downloaded through **Colibri AI Studio** are subject to their respective upstream repository licenses on Hugging Face (e.g., Apache-2.0, MIT, DeepSeek License, GLM License, or custom research licenses). Always review the license displayed on each model card in the Model Hub before commercial use.
