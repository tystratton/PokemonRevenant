"""Locate the repo, vanilla Platinum, Renegade patches, and a safe output folder."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

VANILLA_NAMES = (
    "Pokemon - Platinum Version (USA).nds",
    "Pokemon - Platinum Version (USA) (Rev 1).nds",
    "Pokemon Platinum.nds",
    "platinum.nds",
)

PATCH_PREFERENCE = (
    "RenegadePlatinum3541.xdelta",
    "RenegadePlatinum4997.xdelta",
    "RP121CompleteWithoutShinyBoost.xdelta",
    "RP121CompleteWithShinyBoost.xdelta",
    "RP121ClassicWithoutShinyBoost.xdelta",
    "RP121ClassicWithShinyBoost.xdelta",
)

# no-intro SHA1 -> patch name hint
PLATINUM_SHA1_HINTS = {
    "ce81046eda7d232513069519cb2085349896dec7": "3541",  # USA Rev 0
    "0862ec35b24de5c7e2dcb88c9eea0873110d755c": "4997",  # USA Rev 1
}

OUTPUT_DIR_NAME = "out"
OUTPUT_ROM_NAME = "RenegadePlatinum-nuzlocke.nds"
RENEGADE_BASE_NAME = "_renegade_base.nds"
# In-use play ROM: never overwrite this even if someone re-runs the tool.
IN_USE_OUTPUT_NAMES = frozenset({OUTPUT_ROM_NAME})


def sha1_file(path: Path) -> str:
    digest = hashlib.sha1()
    with Path(path).open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def rom_patch_hint(path: Path) -> str | None:
    return PLATINUM_SHA1_HINTS.get(sha1_file(path))


def repo_root(start: Path | None = None) -> Path:
    here = (start or Path(__file__)).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / "plat_rand").is_dir() and (candidate / "randomize.py").is_file():
            return candidate
    return Path.cwd()


def output_dir(root: Path | None = None) -> Path:
    return (root or repo_root()) / OUTPUT_DIR_NAME


def default_output_rom(root: Path | None = None) -> Path:
    """Next free output path. Never reuses an existing in-use play ROM."""
    folder = output_dir(root)
    preferred = folder / OUTPUT_ROM_NAME
    if not preferred.is_file():
        return preferred
    index = 2
    while True:
        candidate = folder / f"RenegadePlatinum-nuzlocke-{index}.nds"
        if not candidate.is_file():
            return candidate
        index += 1


def renegade_base_path(root: Path | None = None) -> Path:
    return output_dir(root) / RENEGADE_BASE_NAME


def find_vanilla_rom(root: Path | None = None) -> Path | None:
    root = root or repo_root()
    for name in VANILLA_NAMES:
        path = root / name
        if path.is_file():
            return path
    for path in sorted(root.glob("*.nds")):
        if path.name.startswith("_") or path.parent.name == OUTPUT_DIR_NAME:
            continue
        if "nuzlocke" in path.name.lower() or "renegade" in path.name.lower():
            continue
        return path
    return None


def iter_renegade_patches(root: Path | None = None, hint: str | None = None) -> list[Path]:
    root = root or repo_root()
    found = list(root.rglob("*.xdelta"))
    # Skip tiny QoL add-ons (speed-up / shiny-rate) until a base patch exists.
    baseish = [
        path
        for path in found
        if path.stat().st_size > 1_000_000
        or "3541" in path.name
        or "4997" in path.name
        or "complete" in path.name.lower()
        or "classic" in path.name.lower()
    ]
    if not baseish:
        baseish = found

    def score(path: Path) -> tuple[int, str]:
        name = path.name.lower()
        rank = 50
        if hint and hint.lower() in name:
            rank = 0
        elif name in {item.lower() for item in PATCH_PREFERENCE}:
            rank = 1 + [item.lower() for item in PATCH_PREFERENCE].index(name)
        elif "complete" in name:
            rank = 20
        return (rank, name)

    return sorted(baseish, key=score)


def find_renegade_patch(root: Path | None = None, hint: str | None = None) -> Path | None:
    patches = iter_renegade_patches(root, hint=hint)
    return patches[0] if patches else None


def is_protected_source(path: Path, root: Path | None = None) -> bool:
    """True if this path is a user-supplied clean ROM or patch input."""
    root = (root or repo_root()).resolve()
    resolved = path.resolve()
    if resolved.parent == root and resolved.suffix.lower() == ".nds":
        return True
    relative = str(resolved).lower()
    if "renegadeplatinum" in relative and OUTPUT_DIR_NAME not in resolved.parts:
        return True
    if resolved.name.lower() in {name.lower() for name in VANILLA_NAMES}:
        return True
    return False


def assert_safe_output(path: Path, *sources: Path, root: Path | None = None) -> None:
    resolved = Path(path).resolve()
    root = root or repo_root()
    if is_protected_source(resolved, root):
        raise ValueError(
            f"Refusing to overwrite the clean source file {resolved.name}. "
            f"Output goes in the {OUTPUT_DIR_NAME}/ folder."
        )
    if resolved.name in IN_USE_OUTPUT_NAMES and resolved.is_file():
        raise ValueError(
            f"Refusing to overwrite in-use play ROM {resolved.name}. "
            f"Future seeds go to a new file such as RenegadePlatinum-nuzlocke-2.nds."
        )
    for source in sources:
        if source and resolved == Path(source).resolve():
            raise ValueError(f"Refusing to overwrite source ROM {source}")


@dataclass
class AutoInputs:
    root: Path
    vanilla_rom: Path | None
    renegade_patch: Path | None
    output_rom: Path
    renegade_base: Path

    @classmethod
    def discover(cls, root: Path | None = None) -> AutoInputs:
        root = root or repo_root()
        vanilla = find_vanilla_rom(root)
        hint = rom_patch_hint(vanilla) if vanilla else None
        return cls(
            root=root,
            vanilla_rom=vanilla,
            renegade_patch=find_renegade_patch(root, hint=hint),
            output_rom=default_output_rom(root),
            renegade_base=renegade_base_path(root),
        )
