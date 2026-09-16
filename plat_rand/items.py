"""Remove Rare Candies, keep Exp. Share, and disable revives."""

from __future__ import annotations

from dataclasses import dataclass, field

from plat_rand.binary import find_unique, read_relative_pointer, read_u16, write_u16
from plat_rand.constants import (
    HIDDEN_ITEM_COUNT,
    HIDDEN_ITEM_OFFSET,
    HIDDEN_ITEM_STRIDE,
    ITEM_BALL_SCRIPT_FILE,
    ITEM_BALL_SKIP,
    ITEM_BATTLE_USE_OFFSET,
    ITEM_DATA_PATHS,
    ITEM_EXP_SHARE,
    ITEM_FIELD_USE_OFFSET,
    ITEM_RARE_CANDY,
    ITEM_SCRIPT_VARIABLE,
    REVIVE_ITEMS,
    SCRIPT_LIST_TERMINATOR,
    SCRIPT_PATHS,
    SET_VAR_COMMAND,
    SHOP_COUNT,
    SHOP_DATA_PREFIX,
    SHOP_SKIP,
)
from plat_rand.rom import PlatinumRom


@dataclass
class ItemResult:
    rare_candies_replaced: int = 0
    revives_disabled: int = 0
    notes: list[str] = field(default_factory=list)


def _replace_item_id(value: int) -> int:
    return ITEM_EXP_SHARE if value == ITEM_RARE_CANDY else value


def _patch_item_balls(rom: PlatinumRom, result: ItemResult) -> None:
    try:
        path, narc = rom.get_narc(*SCRIPT_PATHS)
    except FileNotFoundError as exc:
        result.notes.append(str(exc))
        return
    if ITEM_BALL_SCRIPT_FILE >= len(narc.files):
        result.notes.append("Item-ball script file is missing")
        return

    scripts = bytearray(narc.files[ITEM_BALL_SCRIPT_FILE])
    offset = 0
    skip_iter = iter(sorted(ITEM_BALL_SKIP))
    next_skip = next(skip_iter, None)
    index = 0
    while offset + 4 <= len(scripts):
        if read_u16(scripts, offset) == SCRIPT_LIST_TERMINATOR:
            break
        dest = read_relative_pointer(scripts, offset)
        offset += 4
        if next_skip == index:
            next_skip = next(skip_iter, None)
            index += 1
            continue
        index += 1
        if dest < 0 or dest + 6 > len(scripts):
            continue
        command = read_u16(scripts, dest)
        variable = read_u16(scripts, dest + 2)
        if command != SET_VAR_COMMAND or variable != ITEM_SCRIPT_VARIABLE:
            continue
        item = read_u16(scripts, dest + 4)
        replaced = _replace_item_id(item)
        if replaced != item:
            write_u16(scripts, dest + 4, replaced)
            result.rare_candies_replaced += 1
    narc.files[ITEM_BALL_SCRIPT_FILE] = bytes(scripts)
    rom.set_narc(path, narc)


def _looks_like_item_table(arm9: bytearray, offset: int, count: int) -> bool:
    for index in range(min(8, count)):
        item = read_u16(arm9, offset + index * HIDDEN_ITEM_STRIDE)
        if item > 536:
            return False
    return True


def _patch_hidden_items(rom: PlatinumRom, result: ItemResult) -> None:
    offset = HIDDEN_ITEM_OFFSET
    end = offset + HIDDEN_ITEM_COUNT * HIDDEN_ITEM_STRIDE
    if end > len(rom.arm9) or not _looks_like_item_table(rom.arm9, offset, HIDDEN_ITEM_COUNT):
        result.notes.append("Hidden-item table offset does not match this ARM9; skipped")
        return
    for index in range(HIDDEN_ITEM_COUNT):
        item_at = offset + index * HIDDEN_ITEM_STRIDE
        item = read_u16(rom.arm9, item_at)
        replaced = _replace_item_id(item)
        if replaced != item:
            write_u16(rom.arm9, item_at, replaced)
            result.rare_candies_replaced += 1


def _patch_shops(rom: PlatinumRom, result: ItemResult) -> None:
    start = find_unique(rom.arm9, SHOP_DATA_PREFIX)
    if start is None:
        # Prefix plus the first item word can move in Renegade; try prefix-only scan.
        hits = []
        needle = SHOP_DATA_PREFIX
        idx = rom.arm9.find(needle)
        if idx >= 0:
            hits.append(idx)
        if len(hits) != 1:
            result.notes.append("Shop table not found (typical on some Renegade builds)")
            return
        start = hits[0]
    offset = start + len(SHOP_DATA_PREFIX)
    for shop in range(SHOP_COUNT):
        while offset + 2 <= len(rom.arm9) and read_u16(rom.arm9, offset) != 0xFFFF:
            item = read_u16(rom.arm9, offset)
            if shop not in SHOP_SKIP:
                replaced = _replace_item_id(item)
                if replaced != item:
                    write_u16(rom.arm9, offset, replaced)
                    result.rare_candies_replaced += 1
            offset += 2
        offset += 2


def _disable_revives(rom: PlatinumRom, result: ItemResult) -> None:
    try:
        path, narc = rom.get_narc(*ITEM_DATA_PATHS)
    except FileNotFoundError as exc:
        result.notes.append(str(exc))
        return
    for item_id in REVIVE_ITEMS:
        if item_id >= len(narc.files):
            continue
        entry = bytearray(narc.files[item_id])
        if len(entry) <= ITEM_BATTLE_USE_OFFSET:
            continue
        entry[ITEM_FIELD_USE_OFFSET] = 0
        entry[ITEM_BATTLE_USE_OFFSET] = 0
        narc.files[item_id] = bytes(entry)
        result.revives_disabled += 1
    rom.set_narc(path, narc)
    result.notes.append("Revive / Max Revive / Revival Herb / Sacred Ash can no longer be used")


def patch_items(rom: PlatinumRom) -> ItemResult:
    result = ItemResult()
    _patch_item_balls(rom, result)
    _patch_hidden_items(rom, result)
    _patch_shops(rom, result)
    _disable_revives(rom, result)
    result.notes.append(
        f"Replaced {result.rare_candies_replaced} Rare Candies with Exp. Share"
    )
    return result
