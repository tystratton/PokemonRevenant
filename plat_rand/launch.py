"""Open the randomized ROM in a local DS emulator if one is installed."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

_EXE_NAMES = (
    "EmuHawk.exe",
    "EmuHawk",
    "melonDS.exe",
    "melonDS",
    "DeSmuME.exe",
    "DeSmuME",
    "desmume.exe",
    "retroarch.exe",
    "retroarch",
)

_EXTRA_DIRS = (
    Path(os.environ.get("ProgramFiles", r"C:\Program Files")),
    Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")),
    Path(os.environ.get("LOCALAPPDATA", "")),
    Path.home() / "AppData" / "Local" / "Programs",
    Path.home() / "scoop" / "apps",
    Path.home() / "Desktop",
    Path.home() / "Downloads",
    Path(r"C:\BizHawk"),
    Path(r"C:\melonDS"),
    Path(r"C:\Emulators"),
)


def find_emulator() -> Path | None:
    for name in _EXE_NAMES:
        found = shutil.which(name)
        if found:
            return Path(found)
    for folder in _EXTRA_DIRS:
        if not folder or not folder.is_dir():
            continue
        for name in ("EmuHawk.exe", "melonDS.exe", "DeSmuME.exe", "retroarch.exe"):
            direct = folder / name
            if direct.is_file():
                return direct
            try:
                for child in folder.iterdir():
                    candidate = child / name if child.is_dir() else child
                    if candidate.is_file() and candidate.name.lower() == name.lower():
                        return candidate
            except OSError:
                continue
    return None


def launch_rom(rom_path: Path, lua_path: Path | None = None) -> str | None:
    """Start the ROM. Returns a short status string, or None if nothing launched."""
    emulator = find_emulator()
    if emulator is None:
        return None
    args = [str(emulator), str(rom_path)]
    if lua_path and lua_path.is_file() and "emuhawk" in emulator.name.lower():
        args = [str(emulator), f"--lua={lua_path}", str(rom_path)]
    try:
        subprocess.Popen(args, cwd=str(rom_path.parent))
    except OSError as exc:
        return f"Tried to launch {emulator.name} but it failed: {exc}"
    return f"Launched {emulator.name} with {rom_path.name}"
