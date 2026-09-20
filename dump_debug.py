#!/usr/bin/env python3
"""Extract the few regions the randomizer touches, for off-machine analysis.

Run:  python3 dump_debug.py out/_renegade_base.nds out/RenegadePlatinum-nuzlocke.nds
Then: git add debug_dump && git commit -m "debug dump" && git push

Writes a few MB, not a ROM, so it can be committed and diffed.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from plat_rand.rom import PlatinumRom
from plat_rand.constants import SCRIPT_PATHS, WILD_ENCOUNTER_PATHS

OUT = Path("debug_dump")
# Route 201 starter scene, its map init, and the rival/tag script files.
SCRIPT_FILES = (427, 909, 429, 1096, 31, 36, 112, 123, 186)
OVERLAYS = (13, 78)


def dump(rom_path: Path, label: str) -> None:
    folder = OUT / label
    folder.mkdir(parents=True, exist_ok=True)
    rom = PlatinumRom.load(rom_path)
    lines = [f"source {rom_path.name}",
             f"size   {rom_path.stat().st_size}",
             f"sha1   {hashlib.sha1(rom_path.read_bytes()).hexdigest()}"]

    (folder / "arm9.bin").write_bytes(bytes(rom.arm9))
    lines.append(f"arm9 {len(rom.arm9)} bytes")

    for overlay_id in OVERLAYS:
        try:
            data = bytes(rom.overlay_data(overlay_id))
        except Exception as exc:
            lines.append(f"overlay {overlay_id}: UNAVAILABLE {exc}")
            continue
        (folder / f"overlay_{overlay_id}.bin").write_bytes(data)
        lines.append(f"overlay {overlay_id}: {len(data)} bytes")

    try:
        _, scripts = rom.get_narc(*SCRIPT_PATHS)
        for index in SCRIPT_FILES:
            if index < len(scripts.files):
                (folder / f"script_{index}.bin").write_bytes(bytes(scripts.files[index]))
                lines.append(f"script {index}: {len(scripts.files[index])} bytes")
    except Exception as exc:
        lines.append(f"scripts: UNAVAILABLE {exc}")

    try:
        path, enc = rom.get_narc(*WILD_ENCOUNTER_PATHS)
        blob = b"".join(bytes(f) for f in enc.files)
        (folder / "encounters.bin").write_bytes(blob)
        lines.append(f"encounters: {len(enc.files)} areas, {len(blob)} bytes ({path})")
    except Exception as exc:
        lines.append(f"encounters: UNAVAILABLE {exc}")

    try:
        events = rom.get_file("fielddata/eventdata/zone_event.narc")
        (folder / "zone_event.narc").write_bytes(bytes(events))
        lines.append(f"zone_event: {len(events)} bytes")
    except Exception as exc:
        lines.append(f"zone_event: UNAVAILABLE {exc}")

    (folder / "MANIFEST.txt").write_text("\n".join(lines) + "\n")
    print(f"[{label}] " + "; ".join(lines[1:3]))
    for line in lines[3:]:
        print(f"   {line}")


def main(argv: list[str]) -> int:
    if len(argv) < 1:
        print("usage: python3 dump_debug.py <base.nds> [built.nds]")
        return 2
    labels = ("base", "built", "third")
    for label, name in zip(labels, argv):
        path = Path(name)
        if not path.is_file():
            print(f"missing: {path}")
            return 1
        dump(path, label)
    total = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    print(f"\nWrote {OUT}/  ({total:,} bytes total) — commit and push this folder.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
