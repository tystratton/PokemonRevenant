"""Nuzlocke ROM hooks: delete fainted party mons, halt the game on wipe."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from plat_rand.intro import thumb_bl

_HELPER_LUA = Path(__file__).resolve().parent / "nuzlocke_helper.lua"
_ARM9_RAM = 0x02000000
# pret Party_Copy / JimB16 CopyPkmnParty — Thumb, still at the vanilla US address.
_PARTY_COPY_OFF = 0x7A21C
_PARTY_COPY_SIG = bytes.fromhex("18B4041C0B1CB222")


def _lua_source() -> str:
    return _HELPER_LUA.read_text(encoding="utf-8")


_BIZHAWK_LUA = _lua_source()


@dataclass
class NuzlockeResult:
    cave_offset: int | None = None
    hooks: list[str] = field(default_factory=list)
    lua_path: str | None = None
    notes: list[str] = field(default_factory=list)


# Only this call writes the player's completed battle party to the save.
_BATTLE_COPY_OFF = 0x5272C
_GET_VALUE = 0x74470
_REMOVE_SLOT = 0x7A080


def build_party_sweep_payload(address: int = 0) -> bytes:
    """Thumb call-site replacement: copy, then remove fainted non-eggs safely."""
    code = bytearray()
    labels = {}
    branches = []

    def emit(*words):
        for word in words:
            code.extend(word.to_bytes(2, "little"))

    def call(target):
        code.extend(thumb_bl(_ARM9_RAM + address + len(code), _ARM9_RAM + target))

    def label(name):
        labels[name] = len(code)

    def branch(name, condition=None):
        branches.append((len(code), name, condition))
        emit(0)

    emit(0xB570, 0x1C0C)  # push r4-r6,lr; r4=destination
    call(_PARTY_COPY_OFF)
    emit(0x6865, 0x2D00)  # count; empty copies are not a battle defeat
    branch("return", 0)
    label("loop")
    emit(0x3D01, 0x20EC, 0x4368, 0x1900, 0x3008, 0x1C06)
    emit(0x214C, 0x2200)  # MON_DATA_IS_EGG, NULL
    call(_GET_VALUE)
    emit(0x2800)
    branch("next", 1)
    emit(0x1C30, 0x21A3, 0x2200)  # Pokemon_GetValue(mon, HP, NULL)
    call(_GET_VALUE)
    emit(0x2800)
    branch("next", 1)
    emit(0x1C20, 0x1C29)
    call(_REMOVE_SLOT)
    label("next")
    emit(0x2D00)
    branch("loop", 1)
    emit(0x6860, 0x2800)
    branch("halt", 0)
    label("return")
    emit(0xBD70)
    label("halt")
    branch("halt")
    for at, name, condition in branches:
        delta = labels[name] - at - 4
        word = (0xE000 | ((delta // 2) & 0x7FF)) if condition is None else (0xD000 | (condition << 8) | ((delta // 2) & 0xFF))
        code[at:at + 2] = word.to_bytes(2, "little")
    return bytes(code)


def _find_code_cave(arm9: bytes, size: int) -> int | None:
    # Require alignment for executable Thumb code.
    for idx in range(0x4000, len(arm9) - size - 0x40, 4):
        if arm9[idx:idx + size] == bytes(size):
            return idx
    return None


def apply_nuzlocke_patches(rom, lua_path: Path | None = None) -> NuzlockeResult:
    result = NuzlockeResult()
    from plat_rand.rom import RomError
    expected = thumb_bl(_ARM9_RAM + _BATTLE_COPY_OFF, _ARM9_RAM + _PARTY_COPY_OFF)
    if (bytes(rom.arm9[_BATTLE_COPY_OFF:_BATTLE_COPY_OFF + 4]) != expected
            or bytes(rom.arm9[_PARTY_COPY_OFF:_PARTY_COPY_OFF + 8]) != _PARTY_COPY_SIG):
        raise RomError("Unsupported battle-result hook; rebuild from the clean base")
    cave = _find_code_cave(bytes(rom.arm9), 128)
    if cave is None:
        raise RomError("No space for the battle-result hook")
    payload = build_party_sweep_payload(cave)
    rom.arm9[cave:cave + len(payload)] = payload
    rom.arm9[_BATTLE_COPY_OFF:_BATTLE_COPY_OFF + 4] = thumb_bl(
        _ARM9_RAM + _BATTLE_COPY_OFF, _ARM9_RAM + cave)
    result.cave_offset = cave
    result.hooks = [f"Hooked battle-result Party_Copy call at ARM9 0x{_BATTLE_COPY_OFF:X}"]
    result.notes = ["Fainted Pokemon are removed after battle; a full wipe freezes the game. No emulator script required."]

    if lua_path is not None:
        dest = Path(lua_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(_lua_source(), encoding="utf-8")
        result.lua_path = str(dest)
        result.notes.append(f"Wrote optional helper {dest.name}")
    return result
