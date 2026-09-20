"""Execute the generated Thumb hooks: first sight, revisit, extra throws, save flags."""

from pathlib import Path
import struct

import pytest

from plat_rand.catch_lock import (
    AREA_COUNT,
    MESSAGE,
    RESERVED_FLAGS,
    append_message,
    apply_catch_lock,
    build_ball_check,
    build_message,
    build_start,
)
from plat_rand.binary import thumb_bl
from plat_rand.rom import PlatinumRom

MAP_LABEL = 0x203A138
GET_FLAGS = 0x20507E4
CHECK_FLAG = 0x20507F0
SET_FLAG = 0x205081C
LOAD_MSG = 0x200B1B8
STATE = 0x02100000
WILD = 0
TRAINER = 0x685
LOW_BASE = 0xA44
HIGH_BASE = 0xA69
SPLIT = 0x5C


def flag_id(label: int) -> int:
    return (LOW_BASE if label < SPLIT else HIGH_BASE) + label


def decode_bl(code: bytes, pc: int, base: int) -> int:
    hi, lo = struct.unpack_from("<HH", code, pc)
    delta = ((hi & 0x7FF) << 12) | ((lo & 0x7FF) << 1)
    if delta & (1 << 22):
        delta -= 1 << 23
    return base + pc + 4 + delta


class ThumbCpu:
    """Enough Thumb to run the three catch-lock payloads."""

    def __init__(self, code: bytes, *, base=0x02040000, label=1, battle_type=WILD, flags=None, bag_ok=0):
        self.code = code
        self.base = base
        self.r = [0] * 16
        self.r[4] = 0x02010000  # save* or battle-bag context*
        self.r[5] = 0x02020000  # dto*
        self.battle_type = battle_type
        self.mem = {
            STATE: 0,
            0x02020000: battle_type,   # dto->battleType
            0x02010000: 0x02011000,    # context->battleSys
            0x0201102C: battle_type,
            0x02010022: bag_ok,
        }
        self.flags = set(flags or ())
        self.label = label
        self.checked = []
        self.set_flags = []
        self.messages = []
        self.n, self.z, self.c = 0, 1, 0

    def _set(self, value: int) -> int:
        value &= 0xFFFFFFFF
        self.n = (value >> 31) & 1
        self.z = int(value == 0)
        return value

    def _cmp(self, a: int, b: int) -> None:
        result = (a - b) & 0xFFFFFFFF
        self.n = (result >> 31) & 1
        self.z = int(result == 0)
        self.c = int(a >= b)

    def cond(self, cc: int) -> bool:
        return (
            (cc == 0 and self.z)
            or (cc == 1 and not self.z)
            or (cc == 2 and self.c)
            or (cc == 3 and not self.c)
        )

    def call(self, target: int) -> None:
        if target == MAP_LABEL:
            self.r[0] = self.label
        elif target == GET_FLAGS:
            self.r[0] = 0x02030000
        elif target == CHECK_FLAG:
            self.checked.append(self.r[1])
            self.r[0] = int(self.r[1] in self.flags)
        elif target == SET_FLAG:
            self.set_flags.append(self.r[1])
            self.flags.add(self.r[1])
        elif target == LOAD_MSG:
            self.messages.append(self.r[1])
        else:
            raise AssertionError(f"unexpected BL {target:#x}")
        self._set(self.r[0])

    def run(self, extra_r=None) -> int:
        if extra_r:
            for reg, value in extra_r.items():
                self.r[reg] = value
        pc = 0
        for _ in range(200):
            if pc >= len(self.code):
                raise AssertionError("fell off the payload")
            op = struct.unpack_from("<H", self.code, pc)[0]
            nxt = pc + 2
            if op & 0xF800 == 0xF000:
                self.call(decode_bl(self.code, pc, self.base))
                nxt = pc + 4
            elif op & 0xFE00 == 0xB400:
                pass
            elif op & 0xFE00 == 0xBC00:
                if op & 0x100:
                    return self.r[0]
            elif op & 0xF800 == 0x2000:
                self.r[(op >> 8) & 7] = self._set(op & 0xFF)
            elif op & 0xFFC0 == 0x1C00:
                self.r[op & 7] = self._set(self.r[(op >> 3) & 7])
            elif op & 0xF800 == 0x6000:
                self.mem[self.r[(op >> 3) & 7] + ((op >> 6) & 0x1F) * 4] = self.r[op & 7]
            elif op & 0xF800 == 0x4800:
                loc = ((pc + 4) & ~3) + (op & 0xFF) * 4
                self.r[(op >> 8) & 7] = struct.unpack_from("<I", self.code, loc)[0]
            elif op & 0xF800 == 0x6800:
                addr = self.r[(op >> 3) & 7] + ((op >> 6) & 0x1F) * 4
                self.r[op & 7] = self._set(self.mem.get(addr, 0))
            elif op == 0x4208:
                self._set(self.r[0] & self.r[1])
            elif op & 0xF800 == 0x2800:
                self._cmp(self.r[(op >> 8) & 7], op & 0xFF)
            elif op & 0xFFC0 == 0x1800:
                self.r[op & 7] = self._set(self.r[(op >> 3) & 7] + self.r[(op >> 6) & 7])
            elif op & 0xF800 == 0x3000:
                self.r[(op >> 8) & 7] = self._set(self.r[(op >> 8) & 7] + (op & 0xFF))
            elif op & 0xFE00 == 0x7800:
                self.r[op & 7] = self._set(self.mem[self.r[(op >> 3) & 7]])
            elif op & 0xF800 == 0xE000:
                nxt = pc + 4 + ((op & 0x7FF) << 1)
                if op & 0x400:
                    nxt -= 1 << 12
            elif op & 0xF000 == 0xD000:
                if self.cond((op >> 8) & 0xF):
                    delta = op & 0xFF
                    nxt = pc + 4 + ((delta - 256 if delta >= 128 else delta) << 1)
            elif op != 0x46C0:
                raise AssertionError(f"unhandled opcode {op:#06x} at {pc:#x}")
            pc = nxt
        raise AssertionError("hook did not return")


def start(label=1, battle_type=WILD, flags=None):
    cpu = ThumbCpu(build_start(0x02040000, STATE), base=0x02040000, label=label, battle_type=battle_type, flags=flags)
    result = cpu.run()
    return cpu, result


def ball(cpu, bag_ok=0):
    check = ThumbCpu(
        build_ball_check(0x02040100, STATE),
        base=0x02040100,
        battle_type=cpu.battle_type,
        bag_ok=bag_ok,
    )
    check.mem[STATE] = cpu.mem[STATE]
    return check.run()


def message(cpu, original=7, message_id=40):
    msg = ThumbCpu(build_message(0x02040200, STATE, message_id), base=0x02040200)
    msg.mem[STATE] = cpu.mem[STATE]
    msg.run(extra_r={1: original})
    return msg.messages[-1]


def test_first_encounter_allows_the_ball_and_consumes_the_area():
    cpu, label = start(label=3)
    assert label == 3
    assert cpu.checked == [flag_id(3)]
    assert cpu.set_flags == [flag_id(3)]
    assert cpu.mem[STATE] == 0
    assert ball(cpu, bag_ok=0) == 0
    assert message(cpu, original=9, message_id=40) == 9


def test_revisit_denies_the_ball_and_uses_the_lock_message():
    cpu, _ = start(label=3, flags={flag_id(3)})
    assert cpu.mem[STATE] == 1
    assert ball(cpu) == 1
    assert message(cpu, original=9, message_id=40) == 40


def test_repeated_throws_in_the_same_battle_stay_denied():
    cpu, _ = start(label=10, flags={flag_id(10)})
    assert ball(cpu) == 1
    assert ball(cpu) == 1
    assert message(cpu, message_id=40) == 40


@pytest.mark.parametrize(
    "label, expected",
    [
        (0, LOW_BASE),
        (91, LOW_BASE + 91),
        (92, HIGH_BASE + 92),
        (125, HIGH_BASE + 125),
    ],
)
def test_save_flag_ids_cover_named_areas_without_overlap(label, expected):
    cpu, _ = start(label=label)
    assert expected in RESERVED_FLAGS
    assert cpu.checked == [expected]
    assert cpu.set_flags == [expected]


def test_out_of_range_labels_do_not_touch_save_flags():
    skipped, _ = start(label=AREA_COUNT)
    assert skipped.checked == []
    assert skipped.set_flags == []
    assert skipped.mem[STATE] == 0


def test_start_hook_never_reads_the_struct_it_is_handed():
    """[r5, #0] is uninitialised at this call site; reading it crashed the game.

    The battle-type filter moved to the ball check, which reads the battle
    type from the battle-bag context, a struct that is fully built by then.
    """
    payload = build_start(0x02000000, STATE)
    for pc in range(0, len(payload) - 1, 2):
        op = struct.unpack_from("<H", payload, pc)[0]
        # 0x6800-0x68FF is LDR rX, [rY, #imm]; r5 as base is the bug.
        if op & 0xF800 == 0x6800:
            base = (op >> 3) & 7
            assert base != 5, f"start hook loads through r5 at +0x{pc:X}"


def test_ball_check_still_filters_trainer_battles():
    trainer, _ = start(label=3, battle_type=TRAINER)
    assert ball(trainer, bag_ok=4) == 4


def test_deny_message_is_appended_to_the_battle_text_bank():
    header = struct.pack("<HH", 1, 1) + struct.pack("<II", 12 ^ 0x00020002, 1 ^ 0x00020002) + b"\x00\x00"
    blob, message_id = append_message(header)
    assert message_id == 1
    count, seed = struct.unpack_from("<HH", blob)
    assert count == 2
    key = (seed * 765 * 2) & 65535
    key |= key << 16
    offset, length = struct.unpack_from("<II", blob, 12)
    raw = blob[(offset ^ key) : (offset ^ key) + (length ^ key) * 2]
    codes = []
    for i in range(0, len(raw), 2):
        codes.append(struct.unpack_from("<H", raw, i)[0] ^ (((2) * 596947 + (i // 2) * 18749) & 65535))
    assert codes[-1] == 0xFFFF
    assert MESSAGE.split()[0] == "First"


def test_real_rom_installs_start_ball_and_message_hooks():
    path = Path(__file__).resolve().parents[1] / "out/_renegade_base.nds"
    if not path.exists():
        pytest.skip("Optional integration check requires user's local Renegade base")
    rom = PlatinumRom.load(path)
    note = apply_catch_lock(rom)
    assert "saved in-game" in note
    start_bl = rom.arm9[0x52284:0x52288]
    assert start_bl != thumb_bl(0x2052284, 0x203A138)
    ov = rom.overlay_data(13)
    base = rom.overlays[13].ramAddress
    check = 0x2226B8A - base
    assert ov[check + 4 : check + 8] == bytes.fromhex("0128c046")
    _, messages = rom.get_narc("msgdata/pl_msg.narc")
    count = struct.unpack_from("<H", messages.files[2])[0]
    assert count >= 2
