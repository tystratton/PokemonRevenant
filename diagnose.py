#!/usr/bin/env python3
"""Report what is actually inside a built ROM.

Run:  python3 diagnose.py out/RenegadePlatinum-nuzlocke.nds
Paste the output when a ROM misbehaves; it says which patches are present
rather than which ones the source code would apply.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

INTRO_MARKER = b"PLAT_INTRO_SKIP_V4"
CATCH_MARKER = b"LOCK"
VANILLA_START = bytes.fromhex("9F010000FFFFFFFF040000000600000000000000")
START_OFFSET = 0xEA12C
ROUTE_201 = 342


def main(paths: list[str]) -> int:
    if not paths:
        print("usage: python3 diagnose.py <rom.nds> [...]")
        return 2
    for name in paths:
        path = Path(name)
        print(f"\n=== {path.name} ===")
        if not path.is_file():
            print("  MISSING")
            continue
        raw = path.read_bytes()
        print(f"  size   {len(raw):,} bytes")
        print(f"  sha1   {hashlib.sha1(raw).hexdigest()}")
        print(f"  title  {raw[0:12].decode('ascii', 'replace')}  code {raw[12:16].decode('ascii', 'replace')}")
        declared = int.from_bytes(raw[0x80:0x84], "little")
        if declared and len(raw) < declared:
            print(f"  !! TRUNCATED: header declares {declared:,} bytes")

        hits = raw.count(INTRO_MARKER)
        print(f"  intro skip marker .......... {'PRESENT x%d  <-- intro skip IS in this ROM' % hits if hits else 'absent'}")

        try:
            from plat_rand.rom import PlatinumRom
            rom = PlatinumRom.load(path)
            arm9 = bytes(rom.arm9)
            block = arm9[START_OFFSET:START_OFFSET + 20]
            if block == VANILLA_START:
                print("  new-game spawn ............. vanilla (Twinleaf bedroom)")
            else:
                dest = int.from_bytes(block[0:4], "little")
                where = "Route 201 briefcase" if dest == ROUTE_201 else f"map {dest}"
                print(f"  new-game spawn ............. MOVED -> {where}  <-- intro skip spawn patch")
            print(f"  catch-lock state block ..... {'present' if CATCH_MARKER in arm9 or raw.count(CATCH_MARKER) else 'not found'}")
        except Exception as exc:  # a diagnostic must never be the thing that fails
            print(f"  (could not parse ARM9: {type(exc).__name__}: {exc})")

        log = path.with_suffix(path.suffix + ".log")
        if log.is_file():
            rules = [l for l in log.read_text(encoding="utf-8", errors="replace").splitlines()
                     if l.strip().startswith("- ")]
            print("  log says this ROM contains:")
            for rule in rules:
                print(f"    {rule.strip()}")
        else:
            print("  (no .log beside this ROM)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
