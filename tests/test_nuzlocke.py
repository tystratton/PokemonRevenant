from pathlib import Path

import pytest

from plat_rand.binary import thumb_bl
from plat_rand.nuzlocke import (
    _ARM9_RAM,
    _BATTLE_COPY_OFF,
    _BIZHAWK_LUA,
    _PARTY_COPY_OFF,
    _PARTY_COPY_SIG,
    apply_nuzlocke_patches,
    build_party_sweep_payload,
)
from plat_rand.rom import PlatinumRom


def test_payload_is_aligned_and_halts() -> None:
    payload = build_party_sweep_payload()
    assert len(payload) % 2 == 0
    assert payload[-2:] == bytes.fromhex("fee7")


def test_lua_does_not_mutate_game_memory() -> None:
    assert "No Lua helper is needed" in _BIZHAWK_LUA
    assert "memory.write" not in _BIZHAWK_LUA
    assert "while true" not in _BIZHAWK_LUA


def test_real_rom_hooks_party_copy() -> None:
    path = Path(__file__).resolve().parents[1] / "out/_renegade_base.nds"
    if not path.exists():
        pytest.skip("Optional integration check requires user's local Renegade base")
    rom = PlatinumRom.load(path)
    assert bytes(rom.arm9[_PARTY_COPY_OFF : _PARTY_COPY_OFF + 8]) == _PARTY_COPY_SIG
    result = apply_nuzlocke_patches(rom)
    assert result.cave_offset is not None
    assert bytes(rom.arm9[_PARTY_COPY_OFF:_PARTY_COPY_OFF + 8]) == _PARTY_COPY_SIG
    assert rom.arm9[_BATTLE_COPY_OFF:_BATTLE_COPY_OFF + 4] == thumb_bl(
        _ARM9_RAM + _BATTLE_COPY_OFF, _ARM9_RAM + result.cave_offset)
    assert "No emulator script required" in " ".join(result.notes)
    assert "local function sweep" not in _BIZHAWK_LUA
