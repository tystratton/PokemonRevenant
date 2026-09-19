"""Apply an official Renegade Platinum xdelta patch without touching the source ROM."""

from __future__ import annotations

import os
import shutil
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
    """Locate xdelta3: PATH first, then a vendored copy, then the Windows build."""
    folder = tools_dir(root)
    windows = os.name == "nt"
    # A vendored .exe is unusable off Windows; running it gives Permission
    # denied, so never offer it to a POSIX host that has a real xdelta3.
    vendored = (
        ("xdelta3.exe", "xdelta3-3.2.0-x86_64.exe", "xdelta.exe")
        if windows
        else ("xdelta3", "xdelta")
    )
    for name in vendored:
        candidate = folder / name
        if candidate.is_file():
            return candidate
    # Linux/macOS/WSL and Codespaces install xdelta3 through a package manager.
    found = shutil.which("xdelta3") or shutil.which("xdelta")
    if found:
        return Path(found)
    if not windows:
        raise PatchError(
            "xdelta3 was not found. Install it first:\n"
            "  Debian/Ubuntu/Codespaces:  sudo apt-get install -y xdelta3\n"
            "  macOS:                     brew install xdelta"
        )
    zip_path = folder / XDELTA_ZIP_NAME
    urllib.request.urlretrieve(XDELTA_URL, zip_path)
    with zipfile.ZipFile(zip_path) as archive:
        for info in archive.infolist():
            if info.filename.lower().endswith(".exe"):
                dest = folder / "xdelta3.exe"
                dest.write_bytes(archive.read(info))
                return dest
    raise PatchError("Downloaded xdelta3 zip did not contain an .exe")


def _decode_with_pyxdelta(source: Path, patch: Path, dest: Path, missing: PatchError) -> str:
    """Decode with the pyxdelta wheel. Returns "" on success, else the error."""
    try:
        import pyxdelta
    except ImportError:
        raise PatchError(
            f"{missing}\n"
            "  Or, with no package manager:  pip install pyxdelta"
        ) from missing
    if not pyxdelta.decode(str(source), str(patch), str(dest)):
        return "pyxdelta could not apply this patch to this source"
    return ""


def apply_xdelta(source: Path, patch: Path, dest: Path, root: Path | None = None) -> Path:
    source = Path(source)
    patch = Path(patch)
    dest = Path(dest)
    if dest.resolve() == source.resolve():
        raise PatchError("Refusing to apply a patch onto the source ROM path")
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"Applying {patch.name} -> {dest.name} (source ROM is not modified)")
    try:
        exe = ensure_xdelta3(root)
    except PatchError as missing:
        # No binary: fall back to the pip-installable decoder, so a container
        # without working apt can still patch.
        detail = _decode_with_pyxdelta(source, patch, dest, missing)
    else:
        command = [str(exe), "-d", "-f", "-s", str(source), str(patch), str(dest)]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        detail = (completed.stderr or completed.stdout or "").strip() if completed.returncode else ""
    if detail or not dest.is_file() or dest.stat().st_size < 1_000_000:
        detail = detail or "unknown xdelta error"
        # A half-written base must not be mistaken for a usable one next run.
        dest.unlink(missing_ok=True)
        raise PatchError(
            f"Could not apply {patch.name} to {source.name}. {detail}\n"
            "The Platinum dump may be the other US revision (Rev 0 vs Rev 1)."
        )
    return dest
