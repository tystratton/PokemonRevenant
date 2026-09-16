"""Apply an official Renegade Platinum xdelta patch without touching the source ROM."""

from __future__ import annotations

import subprocess
import urllib.request
import zipfile
from pathlib import Path

from plat_rand.paths import repo_root

XDELTA_URL = "https://github.com/jmacd/xdelta/releases/download/v3.2.0/xdelta3-3.2.0-windows-x86_64.zip"
XDELTA_ZIP_NAME = "xdelta3-3.2.0-windows-x86_64.zip"


class PatchError(RuntimeError):
    """xdelta3 failed to apply the Renegade patch."""


def tools_dir(root: Path | None = None) -> Path:
    path = (root or repo_root()) / "tools"
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_xdelta3(root: Path | None = None) -> Path:
    folder = tools_dir(root)
    for name in ("xdelta3.exe", "xdelta3-3.2.0-x86_64.exe", "xdelta.exe"):
        candidate = folder / name
        if candidate.is_file():
            return candidate
    zip_path = folder / XDELTA_ZIP_NAME
    urllib.request.urlretrieve(XDELTA_URL, zip_path)
    with zipfile.ZipFile(zip_path) as archive:
        for info in archive.infolist():
            if info.filename.lower().endswith(".exe"):
                dest = folder / "xdelta3.exe"
                dest.write_bytes(archive.read(info))
                return dest
    raise PatchError("Downloaded xdelta3 zip did not contain an .exe")


def apply_xdelta(source: Path, patch: Path, dest: Path, root: Path | None = None) -> Path:
    source = Path(source)
    patch = Path(patch)
    dest = Path(dest)
    if dest.resolve() == source.resolve():
        raise PatchError("Refusing to apply a patch onto the source ROM path")
    dest.parent.mkdir(parents=True, exist_ok=True)
    exe = ensure_xdelta3(root)
    print(f"Applying {patch.name} -> {dest.name} (source ROM is not modified)")
    command = [str(exe), "-d", "-f", "-s", str(source), str(patch), str(dest)]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0 or not dest.is_file() or dest.stat().st_size < 1_000_000:
        detail = (completed.stderr or completed.stdout or "unknown xdelta error").strip()
        raise PatchError(
            f"Could not apply {patch.name} to {source.name}. {detail}\n"
            "The Platinum dump may be the other US revision (Rev 0 vs Rev 1)."
        )
    return dest
