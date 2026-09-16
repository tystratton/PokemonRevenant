"""Randomize the Lake Verity / briefcase starters and rival checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from random import Random

from plat_rand.binary import find_all, read_u16, write_u16
from plat_rand.constants import (
    RIVAL_SCRIPT_FILES,
    RIVAL_SCRIPT_MAGIC,
    SCRIPT_PATHS,
    STARTER_CRIES_PREFIX,
    STARTER_GRAPHICS_PREFIX,
    STARTER_GRAPHICS_PREFIX_INNER,
    STARTER_OFFSET,
    STARTER_OVERLAY_ID,
    TAG_SCRIPT_FILES,
    TAG_SCRIPT_MAGIC_1,
    TAG_SCRIPT_MAGIC_2,
    VANILLA_STARTERS,
)
from plat_rand.rom import PlatinumRom
from plat_rand.species import species_pool


@dataclass
class StarterResult:
    overlay_id: int
    old: tuple[int, int, int]
    new: tuple[int, int, int]
    notes: list[str] = field(default_factory=list)

    def describe(self) -> str:
        return "Starters randomized (see them on the briefcase in-game)"


def _read_starters(overlay: bytes, offset: int = STARTER_OFFSET) -> tuple[int, int, int]:
    if offset + 12 > len(overlay):
        return VANILLA_STARTERS
    return (
        read_u16(overlay, offset),
        read_u16(overlay, offset + 4),
        read_u16(overlay, offset + 8),
    )


def _write_starters(overlay: bytearray, starters: tuple[int, int, int], offset: int) -> None:
    write_u16(overlay, offset, starters[0])
    write_u16(overlay, offset + 4, starters[1])
    write_u16(overlay, offset + 8, starters[2])


def _find_starter_offset(overlay: bytes) -> int:
    if STARTER_OFFSET + 12 <= len(overlay):
        current = _read_starters(overlay, STARTER_OFFSET)
        if all(1 <= sid <= 493 for sid in current):
            return STARTER_OFFSET

    packed = b"".join(sid.to_bytes(4, "little") for sid in VANILLA_STARTERS)
    hits = find_all(overlay, packed)
    if hits:
        return hits[0]

    packed16 = b"".join(sid.to_bytes(2, "little") for sid in VANILLA_STARTERS)
    hits = find_all(overlay, packed16)
    if hits:
        return hits[0]
    return STARTER_OFFSET


def _patch_rival_scripts(rom: PlatinumRom, starters: tuple[int, int, int], notes: list[str]) -> None:
    try:
        path, narc = rom.get_narc(*SCRIPT_PATHS)
    except FileNotFoundError as exc:
        notes.append(str(exc))
        return

    patched = 0
    for file_id in RIVAL_SCRIPT_FILES:
        if file_id >= len(narc.files):
            continue
        blob = bytearray(narc.files[file_id])
        for hit in find_all(blob, RIVAL_SCRIPT_MAGIC):
            write_u16(blob, hit + 0x8, starters[0])
            write_u16(blob, hit + 0x15, starters[1])
            patched += 1
        narc.files[file_id] = bytes(blob)

    for file_id in TAG_SCRIPT_FILES:
        if file_id >= len(narc.files):
            continue
        blob = bytearray(narc.files[file_id])
        for hit in find_all(blob, TAG_SCRIPT_MAGIC_1):
            second = hit + len(TAG_SCRIPT_MAGIC_1) + 2
            if blob[second : second + len(TAG_SCRIPT_MAGIC_2)] != TAG_SCRIPT_MAGIC_2:
                continue
            write_u16(blob, hit + 0xE, starters[1])
            existing = read_u16(blob, hit + 0x21)
            if existing == VANILLA_STARTERS[0]:
                write_u16(blob, hit + 0x21, starters[0])
            else:
                write_u16(blob, hit + 0x21, starters[2])
            patched += 1
        narc.files[file_id] = bytes(blob)

    rom.set_narc(path, narc)
    notes.append(f"Updated {patched} rival/tag starter checks")


def _patch_dppt_starter_graphics(overlay: bytearray, starters: tuple[int, int, int], notes: list[str]) -> None:
    """Rewrite the briefcase sprite routine so it can show any Gen 4 species.

    Port of Universal Pokémon Randomizer ZX's DPPt starter-graphics fix.
    """
    offset = overlay.find(STARTER_GRAPHICS_PREFIX)
    if offset < 0:
        notes.append("Starter briefcase pictures left vanilla (graphics prefix not found)")
        return

    offset += len(STARTER_GRAPHICS_PREFIX)
    write_u16(overlay, offset + 0xC, read_u16(overlay, offset + 0xA))
    if offset % 4 == 0:
        overlay[offset + 0xC] = (overlay[offset + 0xC] - 1) & 0xFF
    write_u16(overlay, offset + 0xA, read_u16(overlay, offset + 0x8))
    overlay[offset + 0xA] = (overlay[offset + 0xA] - 1) & 0xFF
    write_u16(overlay, offset + 0x8, read_u16(overlay, offset + 0x6))
    write_u16(overlay, offset + 0x6, read_u16(overlay, offset + 0x4))
    write_u16(overlay, offset + 0x4, read_u16(overlay, offset + 0x2))
    write_u16(overlay, offset + 0x2, 0x6828)
    write_u16(overlay, offset, 0x182D)

    offset += 0x16
    write_u16(overlay, offset, 0x6828)
    offset += 0xA

    for index, species in enumerate(starters):
        starter_diff = species - (4 * (index + 1))
        instr1 = 0x3200
        instr2 = 0x3200
        if starter_diff < 0:
            instr1 |= 0x800
            starter_diff = abs(starter_diff)
        elif starter_diff > 255:
            instr2 |= 0xFF
            starter_diff -= 255
        instr1 |= starter_diff & 0xFF
        overlay[offset] = (4 * (index + 1)) & 0xFF
        write_u16(overlay, offset + 2, read_u16(overlay, offset + 4))
        write_u16(overlay, offset + 4, instr1)
        write_u16(overlay, offset + 8, instr2)
        offset += 0xE

    overlay[offset] = 1
    inner = overlay.find(STARTER_GRAPHICS_PREFIX_INNER)
    if inner >= 0:
        inner += len(STARTER_GRAPHICS_PREFIX_INNER)
        overlay[inner + 1] = 0x68
    notes.append("Updated starter briefcase pictures to match the randomized species")


def _patch_graphics_and_cries(
    overlay: bytearray,
    starters: tuple[int, int, int],
    old: tuple[int, int, int],
    notes: list[str],
) -> None:
    cry = overlay.find(STARTER_CRIES_PREFIX)
    if cry >= 0:
        offset = cry + len(STARTER_CRIES_PREFIX)
        if offset + 12 <= len(overlay):
            for i, species in enumerate(starters):
                overlay[offset + i * 4 : offset + i * 4 + 4] = species.to_bytes(4, "little")
            notes.append("Updated starter cry table")
    else:
        packed = b"".join(sid.to_bytes(4, "little") for sid in old)
        hits = [hit for hit in find_all(overlay, packed) if hit != STARTER_OFFSET]
        if hits:
            for hit in hits:
                for i, species in enumerate(starters):
                    overlay[hit + i * 4 : hit + i * 4 + 4] = species.to_bytes(4, "little")
            notes.append(f"Updated {len(hits)} extra starter ID tables (cries/sprites)")

    _patch_dppt_starter_graphics(overlay, starters, notes)


def randomize_starters(
    rom: PlatinumRom,
    rng: Random,
    *,
    allow_legendaries: bool = True,
) -> StarterResult:
    overlay_id = STARTER_OVERLAY_ID
    try:
        overlay = rom.overlay_data(overlay_id)
    except FileNotFoundError:
        # Renegade / shifted overlay tables: search every overlay for the vanilla trio.
        overlay_id, overlay = _discover_starter_overlay(rom)

    offset = _find_starter_offset(overlay)
    old = _read_starters(overlay, offset)
    pool = species_pool(allow_legendaries=allow_legendaries)
    new = (
        rng.choice(pool),
        rng.choice(pool),
        rng.choice(pool),
    )
    _write_starters(overlay, new, offset)
    notes = [f"Wrote starter IDs in overlay {overlay_id} at 0x{offset:X}"]
    _patch_graphics_and_cries(overlay, new, old, notes)
    rom.mark_overlay_dirty(overlay_id)
    _patch_rival_scripts(rom, new, notes)
    return StarterResult(overlay_id=overlay_id, old=old, new=new, notes=notes)


def _discover_starter_overlay(rom: PlatinumRom) -> tuple[int, bytearray]:
    packed = b"".join(sid.to_bytes(4, "little") for sid in VANILLA_STARTERS)
    overlays = rom.nds.loadArm9Overlays()
    for overlay_id, overlay in overlays.items():
        if packed in overlay.data or all(
            sid.to_bytes(2, "little") in overlay.data for sid in VANILLA_STARTERS
        ):
            rom.overlays[overlay_id] = overlay
            if not isinstance(overlay.data, bytearray):
                overlay.data = bytearray(overlay.data)
            return overlay_id, overlay.data
    raise FileNotFoundError("Could not find the starter overlay in this ROM")
