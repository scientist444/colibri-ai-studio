"""Local Model Registry Service (model_registry.py).

Scans the user's configured model storage directory, syncs with SQLite,
and supports importing local GGUF files or existing model folders.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.constants import SUPPORTED_CONFIG_MODEL_TYPES
from app.core.backend_adapter import ColibriBackendAdapter
from app.core.download_manager import DownloadManager
from app.core.storage_manager import StorageManager
from app.database.repositories import InstalledModelsRepository
from app.models.model_metadata import InstalledModelRecord

logger = logging.getLogger(__name__)


class ModelRegistryService:
    """Discovers and manages locally installed Colibri models."""

    def __init__(
        self,
        models_repo: InstalledModelsRepository,
        adapter: ColibriBackendAdapter,
    ) -> None:
        self.models_repo = models_repo
        self.adapter = adapter

    def scan_and_sync_models_dir(self, models_dir: Path | str) -> list[InstalledModelRecord]:
        """Scan `models_dir` for valid model subdirectories and sync database records."""
        root = Path(models_dir)
        if not root.exists():
            return self.models_repo.list_models()

        existing_by_path = {
            Path(m.local_path).resolve(): m
            for m in self.models_repo.list_models()
            if Path(m.local_path).exists()
        }

        for sub in sorted(root.iterdir()):
            if not sub.is_dir() or sub.name.startswith("."):
                continue
            resolved = sub.resolve()
            if resolved in existing_by_path:
                continue

            cfg_file = sub / "config.json"
            idx_file = sub / "model_index.json"
            gguf_files = list(sub.glob("*.gguf"))

            if not cfg_file.exists() and not idx_file.exists() and not gguf_files:
                continue

            family = "qwen36"
            arch = ""
            if cfg_file.exists():
                try:
                    cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
                    mt = str(cfg.get("model_type") or "").lower()
                    arch = mt
                    family = SUPPORTED_CONFIG_MODEL_TYPES.get(mt, "qwen36")
                except Exception:
                    pass

            size_b = StorageManager.calculate_directory_size_bytes(sub)
            verified, _ = DownloadManager.verify_model_integrity(sub)

            rec = InstalledModelRecord(
                model_id=sub.name,
                display_name=sub.name.replace("--", "/"),
                hf_repo=sub.name.replace("--", "/") if "--" in sub.name else "",
                local_path=str(resolved),
                family=family,
                architecture=arch,
                quantization="GGUF" if gguf_files else "INT4 / FP8",
                size_bytes=size_b,
                verified=verified,
                source_type="local_scan",
            )
            self.models_repo.upsert_model(rec)

        return self.models_repo.list_models()

    def import_local_gguf_file(
        self,
        gguf_file: Path | str,
        models_dir: Path | str,
        copy_mode: str = "link",
    ) -> tuple[bool, str, InstalledModelRecord | None]:
        """Inspect and import a local `.gguf` file via `coli import`."""
        src = Path(gguf_file).resolve()
        if not src.exists():
            return False, f"File not found: {src}", None

        header_info = self.adapter.inspect_gguf_architecture(src)
        if not header_info.get("valid_gguf"):
            return False, f"Invalid GGUF file: {header_info.get('error', 'Unknown error')}", None

        arch = str(header_info.get("architecture") or "unknown")
        model_name = src.stem
        out_dir = Path(models_dir).resolve() / f"imported-{model_name}"

        ok, output = self.adapter.import_gguf(src, out_dir, mode=copy_mode)
        if not ok:
            return False, f"GGUF import failed:\n{output}", None

        size_b = StorageManager.calculate_directory_size_bytes(out_dir) or src.stat().st_size
        rec = InstalledModelRecord(
            model_id=f"imported-{model_name}".lower(),
            display_name=f"{model_name} (Imported GGUF)",
            hf_repo="",
            local_path=str(out_dir),
            family="qwen36",
            architecture=arch,
            quantization="GGUF",
            size_bytes=size_b,
            verified=True,
            source_type="gguf_import",
            notes=f"Imported from {src.name} (arch={arch})",
        )
        self.models_repo.upsert_model(rec)
        return True, output, rec
