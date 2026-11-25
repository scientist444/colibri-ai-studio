"""Windows Desktop shortcut creation and verification using Windows Shell APIs."""

from __future__ import annotations

import ctypes
import logging
import os
from ctypes import wintypes
from pathlib import Path

logger = logging.getLogger(__name__)

# FOLDERID_Desktop = {B4BFCC3A-DB2C-424C-B029-7FE99A87C641}
class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


FOLDERID_Desktop = GUID(
    0xB4BFCC3A,
    0xDB2C,
    0x424C,
    (ctypes.c_ubyte * 8)(0xB0, 0x29, 0x7F, 0xE9, 0x9A, 0x87, 0xC6, 0x41),
)


def get_windows_desktop_dir() -> Path:
    """Resolve the active user's Windows Desktop directory (including OneDrive redirection)."""
    if os.name == "nt":
        try:
            shell32 = ctypes.windll.shell32
            ole32 = ctypes.windll.ole32
            path_ptr = ctypes.c_wchar_p()
            hr = shell32.SHGetKnownFolderPath(
                ctypes.byref(FOLDERID_Desktop),
                0,
                None,
                ctypes.byref(path_ptr),
            )
            if hr == 0 and path_ptr.value:
                desktop = Path(path_ptr.value)
                ole32.CoTaskMemFree(path_ptr)
                if desktop.exists():
                    return desktop
        except Exception as exc:
            logger.debug("SHGetKnownFolderPath fallback triggered: %s", exc)

        try:
            import win32com.client  # type: ignore[import-untyped]

            shell = win32com.client.Dispatch("WScript.Shell")
            desktop_str = shell.SpecialFolders("Desktop")
            if desktop_str:
                return Path(desktop_str)
        except Exception as exc:
            logger.debug("WScript.Shell SpecialFolders fallback triggered: %s", exc)

    fallback = Path.home() / "Desktop"
    return fallback


def create_desktop_shortcut(
    target_exe: Path,
    working_dir: Path | None = None,
    icon_path: Path | None = None,
    shortcut_name: str = "Colibri AI Studio.lnk",
    description: str = "Launch Colibri AI Studio — Local AI Workstation",
    desktop_dir: Path | None = None,
) -> Path:
    """Create a Windows `.lnk` shortcut on the user's Desktop and verify it."""
    target_exe = target_exe.resolve()
    if working_dir is None:
        working_dir = target_exe.parent.resolve()
    if icon_path is None or not icon_path.exists():
        icon_path = target_exe

    resolved_desktop = desktop_dir or get_windows_desktop_dir()
    resolved_desktop.mkdir(parents=True, exist_ok=True)
    shortcut_path = resolved_desktop / shortcut_name

    import pythoncom  # type: ignore[import-untyped]
    import win32com.client  # type: ignore[import-untyped]

    pythoncom.CoInitialize()
    try:
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(str(shortcut_path))
        shortcut.Targetpath = str(target_exe)
        shortcut.WorkingDirectory = str(working_dir)
        shortcut.IconLocation = f"{icon_path},0"
        shortcut.Description = description
        shortcut.Save()
    finally:
        pythoncom.CoUninitialize()

    if not shortcut_path.exists():
        raise RuntimeError(f"Failed to create desktop shortcut at {shortcut_path}")

    logger.info("Created desktop shortcut at %s -> %s", shortcut_path, target_exe)
    return shortcut_path


def verify_desktop_shortcut(shortcut_path: Path) -> dict[str, str]:
    """Read back a Windows `.lnk` file's properties for verification."""
    if not shortcut_path.exists():
        raise FileNotFoundError(f"Shortcut does not exist: {shortcut_path}")

    import pythoncom  # type: ignore[import-untyped]
    import win32com.client  # type: ignore[import-untyped]

    pythoncom.CoInitialize()
    try:
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(str(shortcut_path))
        return {
            "shortcut_path": str(shortcut_path),
            "target_path": str(shortcut.Targetpath),
            "working_directory": str(shortcut.WorkingDirectory),
            "icon_location": str(shortcut.IconLocation),
            "description": str(shortcut.Description),
        }
    finally:
        pythoncom.CoUninitialize()
