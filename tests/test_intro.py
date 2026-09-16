from copy import deepcopy
from pathlib import Path
import struct

import pytest

from plat_rand.intro import (
    _BRIEFCASE_X, _BRIEFCASE_Z, _IDENTITY_OFF, _OV73_RAM,
    _OV73_EXIT_NAME_OFF, _OV73_MAIN_OFF, _OV73_MAIN_SKIP,
    _START_LOCATION_OFF, _VAR_ROUTE201, _script_offsets,
    apply_intro_skip, build_transition_setup, script_jump, thumb_bl,
)
from plat_rand.rom import PlatinumRom, RomError


def test_thumb_bl_uses_armv4t_signed_offset():
    assert thumb_bl(0x3D1AA, 0x3A790) == bytes.fromhex("FDF7F1FA")
    for src, dest in [(0x21D0F9A, 0x21D0E24), (0x21D0E28, 0x2025E38)]:
        hi, lo = struct.unpack("<HH", thumb_bl(src, dest))
        delta = ((hi & 0x7FF) << 12) | ((lo & 0x7FF) << 1)
        if delta & (1 << 22):
            delta -= 1 << 23
        assert src + 4 + delta == dest
    with pytest.raises(ValueError):
        thumb_bl(0, 1 << 24)


def test_script_jump_is_relative():
    assert script_jump(0x6A, 0xB7) == bytes.fromhex("160047000000")


def run_transition(blob, state):
    """Execute the setup's control flow, checking real opcode widths/targets."""
    pc, compare = 0, False
    visible, positions = set(), {}
    for _ in range(100):
        op = struct.unpack_from("<H", blob, pc)[0]
        pc += 2
        if op == 2:
            return visible, positions
        if op == 0x11:
            var, value = struct.unpack_from("<HH", blob, pc)
            assert var == _VAR_ROUTE201
            compare = state != value
            pc += 4
        elif op == 0x1C:
            assert blob[pc] == 5  # not equal
            delta = struct.unpack_from("<i", blob, pc + 1)[0]
            pc += 5
            if compare:
                pc += delta
        elif op == 0x16:
            pc += 4 + struct.unpack_from("<i", blob, pc)[0]
        elif op == 0x1F:
            visible.add(struct.unpack_from("<H", blob, pc)[0])
            pc += 2
        elif op == 0x186:
            local, x, z = struct.unpack_from("<HHH", blob, pc)
            positions[local] = (x, z)
            pc += 6
        elif op in (0x188, 0x189):
            pc += 4
        else:
            pytest.fail(f"Unexpected or asynchronous transition opcode {op:x}")
    pytest.fail("Transition did not terminate")


def test_new_game_places_all_four_objects_before_chooser():
    # Jump into appended setup, with original transition represented by End.
    prefix = script_jump(0, 8) + b"\x02\x00"
    blob = prefix + build_transition_setup(8, 6)
    visible, positions = run_transition(blob, 0)
    assert visible == {0x172, 0x178, 0x179, 0x17D}
    assert positions == {2: (114, 853), 5: (113, 853), 6: (112, 853), 12: (112, 854)}


@pytest.mark.parametrize("state", [1, 2, 3, 4])
def test_reentry_does_not_reset_story_or_respawn_characters(state):
    blob = script_jump(0, 8) + b"\x02\x00" + build_transition_setup(8, 6)
    assert run_transition(blob, state) == (set(), {})


@pytest.fixture
def base_rom():
    path = Path(__file__).resolve().parents[1] / "out/_renegade_base.nds"
    if not path.exists():
        pytest.skip("Optional integration check requires user's local Renegade base")
    return PlatinumRom.load(path)


def test_real_rom_uses_frame_task_and_preserves_starter_continuation(base_rom):
    rom = base_rom
    path, before = rom.get_narc("fielddata/script/scr_seq.narc")
    original = before.files[427]
    case = _script_offsets(original)[12]
    events = rom.get_file("fielddata/eventdata/zone_event.narc")
    arm9 = bytes(rom.arm9)
    assert apply_intro_skip(rom).patched
    _, after = rom.get_narc(path)
    patched = after.files[427]
    # Original scene code is intact; only entries 1, 2 and 13 are redirected.
    assert patched[8:48] == original[8:48]
    finish = original.index(bytes.fromhex("2800864002002800a440030003001e00"))
    assert patched[52:finish] == original[52:finish]
    assert patched[finish + 6:len(original)] == original[finish + 6:]
    # Follow the shared battle-ending branch and inspect the resulting story
    # state, rather than assuming the appended code is actually reachable.
    pc = finish
    values, flags = {}, set()
    for _ in range(30):
        if pc == finish + 12:
            break
        op = struct.unpack_from("<H", patched, pc)[0]
        if op == 0x16:
            pc += 6 + struct.unpack_from("<i", patched, pc + 2)[0]
        elif op == 0x28:
            var, value = struct.unpack_from("<HH", patched, pc + 2)
            values[var] = value
            pc += 6
        elif op == 0x1E:
            flags.add(struct.unpack_from("<H", patched, pc + 2)[0])
            pc += 4
        else:
            pytest.fail(f"Unexpected battle cleanup opcode {op:x}")
    assert pc == finish + 12  # original heal/warp continues
    assert values == {0x4086: 4, 0x40A4: 5, 0x4070: 2, 0x40E6: 1,
                      0x40A3: 1, 0x4082: 1, 0x4095: 1}
    assert flags == {0xEA, 0x172, 0x174, 0x176, 0x196, 0x1F2}
    assert rom.get_file("fielddata/eventdata/zone_event.narc") == events
    init = after.files[909]
    assert init[0] == 1
    table = 5 + struct.unpack_from("<I", init, 1)[0]
    assert struct.unpack_from("<HHH", init, table) == (_VAR_ROUTE201, 0, 2)
    assert init[table + 6:] == b"\x00\x00"  # never retrigger at story state 2
    bootstrap = _script_offsets(patched)[1]
    assert patched[bootstrap:bootstrap + 16] == bytes.fromhex("2800864001005a017b00490001000c80")
    chooser = _script_offsets(patched)[12]
    assert patched[bootstrap + 16:bootstrap + 22] == script_jump(bootstrap + 16, chooser)
    # Release actor textures before starting the app. Re-add them only after
    # ReturnToField, then resume the original fade-in and starter grant.
    assert patched[chooser:chooser + 14] == original[case:case + 14]
    assert patched[chooser + 14:chooser + 22] == bytes.fromhex("6500050065000600")
    assert patched[chooser + 22:chooser + 36] == original[case + 14:case + 28]
    assert patched[chooser + 36:chooser + 44] == bytes.fromhex("6400050064000600")
    assert patched[chooser + 44:chooser + 50] == script_jump(chooser + 44, case + 28)
    assert rom.arm9[:_START_LOCATION_OFF] == arm9[:_START_LOCATION_OFF]
    assert rom.arm9[_START_LOCATION_OFF + 20:] == arm9[_START_LOCATION_OFF + 20:]
    assert struct.unpack_from("<II", rom.arm9, _START_LOCATION_OFF + 8) == (_BRIEFCASE_X, _BRIEFCASE_Z)
    ov = rom.overlay_data(73)
    assert ov[_OV73_MAIN_OFF:_OV73_MAIN_OFF + 4] == _OV73_MAIN_SKIP
    assert ov[_OV73_EXIT_NAME_OFF:_OV73_EXIT_NAME_OFF + 4] == thumb_bl(
        _OV73_RAM + _OV73_EXIT_NAME_OFF, _OV73_RAM + _IDENTITY_OFF)


def test_unsupported_scene_is_atomic(base_rom):
    path, narc = base_rom.get_narc("fielddata/script/scr_seq.narc")
    narc.files[909] = b"unsupported"
    base_rom.set_narc(path, narc)
    before = deepcopy(base_rom)
    with pytest.raises(RomError):
        apply_intro_skip(base_rom)
    assert base_rom.arm9 == before.arm9
    assert base_rom.nds.files == before.nds.files
    assert base_rom.dirty_overlays == before.dirty_overlays
    assert base_rom.overlays == before.overlays
