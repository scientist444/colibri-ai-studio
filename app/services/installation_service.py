"""Colibri Engine Installation & Provisioning Service."""

from __future__ import annotations

import logging
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Callable

import httpx

from app.constants import COLIBRI_GITHUB_RELEASES_URL
from app.core.backend_adapter import ColibriBackendAdapter

logger = logging.getLogger(__name__)


class InstallationService:
    """Downloads, verifies, and extracts official Colibri Windows engine releases."""

    def __init__(self, adapter: ColibriBackendAdapter) -> None:
        self.adapter = adapter

    def fetch_latest_windows_release_info(self) -> dict[str, Any]:
        """Query GitHub Releases API for the latest Colibri Windows x86_64 release assets."""
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "ColibriAIStudio/1.0",
        }
        with httpx.Client(timeout=15.0, headers=headers, follow_redirects=True) as client:
            resp = client.get(f"{COLIBRI_GITHUB_RELEASES_URL}/latest")
            if resp.status_code == 404:
                # Fallback to listing all releases if /latest is not marked
                resp_all = client.get(COLIBRI_GITHUB_RELEASES_URL, params={"per_page": 5})
                resp_all.raise_for_status()
                releases = resp_all.json()
                release = releases[0] if isinstance(releases, list) and releases else {}
            else:
                resp.raise_for_status()
                release = resp.json()

        tag = str(release.get("tag_name") or "")
        assets = release.get("assets") or []

        base_zip: dict[str, Any] | None = None
        cuda_zip: dict[str, Any] | None = None
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            name = str(asset.get("name") or "").lower()
            if "windows-x86_64" in name and name.endswith(".zip"):
                if "cuda" in name:
                    cuda_zip = asset
                else:
                    base_zip = asset

        return {
            "tag_name": tag,
            "name": str(release.get("name") or tag),
            "published_at": str(release.get("published_at") or ""),
            "base_asset": base_zip,
            "cuda_asset": cuda_zip,
        }

    def install_colibri_release(
        self,
        include_cuda: bool = False,
        on_progress: Callable[[str, float], None] | None = None,
    ) -> dict[str, Any]:
        """Download and unpack the official Colibri Windows release into `adapter.engine_dir`."""
        self.adapter.ensure_control_plane_provisioned()
        if on_progress:
            on_progress("Querying official GitHub release...", 5.0)

        rel_info = self.fetch_latest_windows_release_info()
        base_asset = rel_info.get("base_asset")
        cuda_asset = rel_info.get("cuda_asset")

        if not isinstance(base_asset, dict) or not base_asset.get("browser_download_url"):
            raise RuntimeError(
                "Could not locate a prebuilt Windows x86_64 release zip on GitHub. "
                "Bundled Colibri Python control plane is already provisioned."
            )

        assets_to_install = [base_asset]
        if include_cuda and isinstance(cuda_asset, dict) and cuda_asset.get("browser_download_url"):
            assets_to_install.append(cuda_asset)

        target_dir = self.adapter.engine_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        for idx, asset in enumerate(assets_to_install):
            asset_name = str(asset.get("name") or "colibri-windows.zip")
            url = str(asset["browser_download_url"])
            expected_size = int(asset.get("size") or 0)

            with tempfile.NamedTemporaryFile(prefix="colibri_rel_", suffix=".zip", delete=False) as tmp_f:
                tmp_zip = Path(tmp_f.name)

            try:
                with httpx.Client(timeout=120.0, follow_redirects=True) as client:
                    with client.stream("GET", url) as resp:
                        resp.raise_for_status()
                        downloaded = 0
                        with open(tmp_zip, "wb") as out_f:
                            for chunk in resp.iter_bytes(chunk_size=512 * 1024):
                                if not chunk:
                                    continue
                                out_f.write(chunk)
                                downloaded += len(chunk)
                                if on_progress and expected_size > 0:
                                    pct = 10.0 + (idx * 40.0) + ((downloaded / expected_size) * 35.0)
                                    on_progress(
                                        f"Downloading {asset_name} ({downloaded / (1024*1024):.1f} MB)...",
                                        min(90.0, pct),
                                    )

                if not zipfile.is_zipfile(tmp_zip):
                    raise RuntimeError(f"Downloaded archive {asset_name} is not a valid ZIP file.")

                if on_progress:
                    on_progress(f"Extracting {asset_name}...", 92.0)

                with zipfile.ZipFile(tmp_zip, "r") as zf:
                    for member in zf.infolist():
                        # Strip single top-level directory prefix if present in release archive
                        parts = Path(member.filename).parts
                        if not parts:
                            continue
                        rel_parts = parts[1:] if (len(parts) > 1 and parts[0].startswith("colibri")) else parts
                        if not rel_parts:
                            continue
                        dest_path = target_dir.joinpath(*rel_parts)
                        if member.is_dir():
                            dest_path.mkdir(parents=True, exist_ok=True)
                        else:
                            dest_path.parent.mkdir(parents=True, exist_ok=True)
                            with zf.open(member) as src_s, open(dest_path, "wb") as dst_s:
                                dst_s.write(src_s.read())
            finally:
                try:
                    if tmp_zip.exists():
                        tmp_zip.unlink()
                except OSError:
                    pass

        self.adapter.ensure_control_plane_provisioned()
        if on_progress:
            on_progress("Running Colibri diagnostics...", 98.0)

        status = self.adapter.detect_installed_engine_binaries()
        if on_progress:
            on_progress("Installation complete!", 100.0)
        return status
