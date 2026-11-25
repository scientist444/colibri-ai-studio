"""Storage volume management, disk space verification, and bounded SSD/NVMe benchmark."""

from __future__ import annotations

import logging
import os
import random
import shutil
import tempfile
import time
from pathlib import Path

logger = logging.getLogger(__name__)


class StorageManager:
    """Manages model storage directories, free space checks, and read throughput tests."""

    @staticmethod
    def get_free_space_gb(directory: Path | str) -> float:
        """Return free disk space in GB for the volume containing `directory`."""
        target = Path(directory).resolve()
        while not target.exists() and target.parent != target:
            target = target.parent
        try:
            usage = shutil.disk_usage(str(target))
            return round(usage.free / (1024**3), 2)
        except OSError as exc:
            logger.warning("Failed to query disk usage for %s: %s", directory, exc)
            return 0.0

    @staticmethod
    def check_sufficient_space(
        directory: Path | str,
        required_gb: float,
        safety_margin_gb: float = 2.0,
    ) -> tuple[bool, float, str]:
        """Verify if `directory` has at least `required_gb + safety_margin_gb` free."""
        free_gb = StorageManager.get_free_space_gb(directory)
        needed = round(required_gb + safety_margin_gb, 2)
        if free_gb >= needed:
            return True, free_gb, f"{free_gb:.1f} GB available ({needed:.1f} GB required with safety margin)."
        return (
            False,
            free_gb,
            f"Insufficient disk space: {free_gb:.1f} GB free, but {needed:.1f} GB is required.",
        )

    @staticmethod
    def calculate_directory_size_bytes(directory: Path | str) -> int:
        """Calculate total bytes occupied by files in a directory."""
        root = Path(directory)
        if not root.exists():
            return 0
        if root.is_file():
            return root.stat().st_size
        total = 0
        try:
            for dirpath, _, filenames in os.walk(root):
                for fname in filenames:
                    fpath = Path(dirpath) / fname
                    try:
                        if not fpath.is_symlink():
                            total += fpath.stat().st_size
                    except OSError:
                        pass
        except OSError:
            pass
        return total

    @staticmethod
    def run_bounded_read_benchmark(
        target_dir: Path | str,
        size_mb: int = 64,
    ) -> dict[str, float]:
        """Run a safe, bounded temporary file sequential and 4KB-block random read benchmark.

        Creates a temporary file of `size_mb` MB (default 64 MB), measures sequential read
        and random 256 KB expert-page read speeds, and deletes the temporary file in `finally`.
        """
        folder = Path(target_dir)
        folder.mkdir(parents=True, exist_ok=True)
        size_mb = max(16, min(size_mb, 256))
        chunk_size = 1024 * 1024  # 1 MB
        total_bytes = size_mb * chunk_size
        buf = os.urandom(chunk_size)

        tmp_fd, tmp_path_str = tempfile.mkstemp(prefix=".colibri_io_bench_", suffix=".tmp", dir=str(folder))
        tmp_path = Path(tmp_path_str)
        try:
            # 1. Write test payload and flush to disk
            t_w0 = time.perf_counter()
            with os.fdopen(tmp_fd, "wb") as f:
                for _ in range(size_mb):
                    f.write(buf)
                f.flush()
                os.fsync(f.fileno())
            write_elapsed = max(0.001, time.perf_counter() - t_w0)
            write_mb_s = round(size_mb / write_elapsed, 1)

            # 2. Sequential read measurement
            t_r0 = time.perf_counter()
            read_bytes = 0
            with open(tmp_path, "rb", buffering=0) as f:
                while True:
                    data = f.read(chunk_size)
                    if not data:
                        break
                    read_bytes += len(data)
            seq_elapsed = max(0.001, time.perf_counter() - t_r0)
            seq_read_mb_s = round((read_bytes / (1024 * 1024)) / seq_elapsed, 1)

            # 3. Random 256 KB expert-slice read measurement
            slice_size = 256 * 1024
            num_slices = 128
            max_offset = max(0, total_bytes - slice_size)
            offsets = [
                (random.randint(0, max_offset // 4096) * 4096) if max_offset >= 4096 else 0
                for _ in range(num_slices)
            ]
            t_rand0 = time.perf_counter()
            rand_bytes = 0
            with open(tmp_path, "rb", buffering=0) as f:
                for off in offsets:
                    f.seek(off)
                    chunk = f.read(slice_size)
                    rand_bytes += len(chunk)
            rand_elapsed = max(0.001, time.perf_counter() - t_rand0)
            rand_read_mb_s = round((rand_bytes / (1024 * 1024)) / rand_elapsed, 1)

            return {
                "seq_read_mb_s": seq_read_mb_s,
                "rand_read_mb_s": rand_read_mb_s,
                "seq_write_mb_s": write_mb_s,
                "tested_mb": float(size_mb),
            }
        finally:
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except OSError:
                pass
