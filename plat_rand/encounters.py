"""Randomize DPPt wild encounter tables."""

from __future__ import annotations

from dataclasses import dataclass, field
from random import Random

from plat_rand.binary import read_u32, write_u32
from plat_rand.constants import (
    ENCOUNTER_FILE_SIZE,
    GRASS_SLOTS,
    MAX_SPECIES,
    WATER_SET_COUNT,
    WATER_SET_START,
    WATER_SLOTS,
    WILD_ENCOUNTER_PATHS,
)
from plat_rand.rom import PlatinumRom
from plat_rand.species import species_name, species_pool


WATER_NAMES = ("Surf", "Unused", "Old Rod", "Good Rod", "Super Rod")


@dataclass
class SlotChange:
    area: int
    kind: str
    slot: int
    old: int
    new: int

    def describe(self) -> str:
        return (
            f"Area {self.area:03d} {self.kind} [{self.slot}] "
            f"{species_name(self.old)} -> {species_name(self.new)}"
        )


@dataclass
class EncounterResult:
    path: str
    areas: int = 0
    changed: list[SlotChange] = field(default_factory=list)


def _valid_species(value: int) -> bool:
    return 1 <= value <= MAX_SPECIES


def _replace_species(data: bytearray, offset: int, rng: Random, pool: list[int]) -> int | None:
    old = read_u32(data, offset)
    if not _valid_species(old):
        return None
    new = rng.choice(pool)
    write_u32(data, offset, new)
    return new


def randomize_encounter_table(
    table: bytearray,
    rng: Random,
    pool: list[int],
    area: int,
) -> list[SlotChange]:
    if len(table) < ENCOUNTER_FILE_SIZE:
        return []

    changes: list[SlotChange] = []
    grass_rate = read_u32(table, 0)
    if grass_rate != 0:
        for slot in range(GRASS_SLOTS):
            offset = 4 + slot * 8 + 4
            old = read_u32(table, offset)
            new = _replace_species(table, offset, rng, pool)
            if new is not None and old != new:
                changes.append(SlotChange(area, "Grass", slot, old, new))

        # Swarm, day/night, radar, dual-slot replacements.
        for index in range(20):
            if 2 <= index <= 5:
                continue
            offset = 100 + index * 4 + (24 if index >= 10 else 0)
            old = read_u32(table, offset)
            new = _replace_species(table, offset, rng, pool)
            if new is not None and old != new:
                changes.append(SlotChange(area, "Special", index, old, new))

        for index in range(4):
            offset = 108 + index * 4
            old = read_u32(table, offset)
            new = _replace_species(table, offset, rng, pool)
            if new is not None and old != new:
                changes.append(SlotChange(area, "Time", index, old, new))

    offset = WATER_SET_START
    for water_id in range(WATER_SET_COUNT):
        rate = read_u32(table, offset)
        offset += 4
        kind = WATER_NAMES[water_id]
        for slot in range(WATER_SLOTS):
            species_off = offset + slot * 8 + 4
            if rate != 0 and water_id != 1:
                old = read_u32(table, species_off)
                new = _replace_species(table, species_off, rng, pool)
                if new is not None and old != new:
                    changes.append(SlotChange(area, kind, slot, old, new))
        offset += WATER_SLOTS * 8
    return changes


def randomize_encounters(
    rom: PlatinumRom,
    rng: Random,
    *,
    allow_legendaries: bool = True,
) -> EncounterResult:
    path, narc = rom.get_narc(*WILD_ENCOUNTER_PATHS)
    pool = species_pool(allow_legendaries=allow_legendaries)
    result = EncounterResult(path=path, areas=len(narc.files))
    for index, raw in enumerate(narc.files):
        table = bytearray(raw)
        result.changed.extend(randomize_encounter_table(table, rng, pool, index))
        narc.files[index] = bytes(table)
    rom.set_narc(path, narc)
    return result
