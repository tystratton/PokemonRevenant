"""Persistent first-encounter rule for the supported US Renegade layout.

References: pret field_battle_data_transfer.c and battle_sub_menus/battle_bag.c.
Area identity is MapHeader_GetMapLabelTextID, shared by floors of one location.
"""
from copy import deepcopy
import struct
from plat_rand.intro import thumb_bl
from plat_rand.nuzlocke import _find_code_cave
from plat_rand.rom import RomError

AREA_COUNT = 126
RESERVED_FLAGS = tuple(range(0xA44, 0xAA0)) + tuple(range(0xAC5, 0xAE7))
MESSAGE = "First encounter already used\nin this area!"


class Thumb:
    def __init__(self, address):
        self.address, self.code = address, bytearray()
        self.labels, self.fixups, self.literals = {}, [], []
    def emit(self, *words):
        for word in words: self.code += struct.pack("<H", word)
    def call(self, address):
        self.code += thumb_bl(self.address + len(self.code), address)
    def label(self, name): self.labels[name] = len(self.code)
    def branch(self, name, cond=None):
        self.fixups.append((len(self.code), name, cond)); self.emit(0)
    def literal(self, reg, value):
        self.literals.append((len(self.code), reg, value)); self.emit(0)
    def finish(self):
        for pos, name, cond in self.fixups:
            delta = self.labels[name] - pos - 4
            assert delta % 2 == 0 and -256 <= delta <= 254
            word = 0xE000 | ((delta // 2) & 0x7FF) if cond is None else 0xD000 | (cond << 8) | ((delta // 2) & 255)
            struct.pack_into("<H", self.code, pos, word)
        while len(self.code) % 4: self.emit(0x46C0)
        for pos, reg, value in self.literals:
            delta = self.address + len(self.code) - ((self.address + pos + 4) & ~3)
            assert delta % 4 == 0 and 0 <= delta <= 1020
            struct.pack_into("<H", self.code, pos, 0x4800 | reg << 8 | delta // 4)
            self.code += struct.pack("<I", value)
        return bytes(self.code)


def build_start(address, state):
    t = Thumb(address)
    t.emit(0xB5F8)  # preserve r3-r7,lr; r4=save, r5=dto
    t.call(0x203A138)  # original map-label lookup
    t.emit(0x1C06)
    t.literal(7, state)
    t.emit(0x2000, 0x6038, 0x6828)
    t.literal(1, 0x685)  # trainer/link/frontier/Pal Park/tutorial
    t.emit(0x4208); t.branch("done", 1)
    t.emit(0x2E7E); t.branch("done", 2)
    t.emit(0x1C20); t.call(0x20507E4)  # SaveData_GetVarsFlags
    t.emit(0x1C04, 0x1C31, 0x295C); t.branch("low", 3)
    t.literal(0, 0xA69); t.branch("flag")
    t.label("low"); t.literal(0, 0xA44)
    t.label("flag"); t.emit(0x1809, 0x1C0D, 0x1C20)
    t.call(0x20507F0)  # check previous encounter
    t.emit(0x6038, 0x1C20, 0x1C29)
    t.call(0x205081C)  # consume area on first sight, not first catch
    t.label("done"); t.emit(0x1C30, 0xBDF8)
    return t.finish()


def build_ball_check(address, state):
    t = Thumb(address)
    t.emit(0xB50E)  # preserve r1-r3,lr
    t.emit(0x6820, 0x6AC0)  # context->battleSys->battleType
    t.literal(1, 0x685)
    t.emit(0x4208); t.branch("normal", 1)
    t.literal(0, state); t.emit(0x6800, 0x2800); t.branch("normal", 0)
    t.emit(0x2001, 0xBD0E)
    t.label("normal"); t.emit(0x1C20, 0x3022, 0x7800, 0xBD0E)
    return t.finish()


def build_message(address, state, message_id):
    t = Thumb(address)
    t.emit(0xB508)
    t.literal(3, state); t.emit(0x681B, 0x2B00); t.branch("load", 0)
    t.emit(0x2100 | message_id)
    t.label("load"); t.call(0x200B1B8); t.emit(0xBD08)
    return t.finish()


def append_message(data):
    count, seed = struct.unpack_from("<HH", data)
    entries = []
    for i in range(count):
        key = (seed * 765 * (i + 1)) & 65535; key |= key << 16
        offset, length = struct.unpack_from("<II", data, 4 + i * 8)
        offset ^= key; length ^= key
        entries.append(data[offset:offset + length * 2])
    codes = []
    for char in MESSAGE:
        if "A" <= char <= "Z": code = 0x12B + ord(char) - ord("A")
        elif "a" <= char <= "z": code = 0x145 + ord(char) - ord("a")
        else: code = {" ": 0x1DE, "!": 0x1AB, "\n": 0xE000}[char]
        codes.append(code)
    codes.append(0xFFFF)
    entries.append(b"".join(struct.pack("<H", code ^ (((count + 1) * 596947 + i * 18749) & 65535)) for i, code in enumerate(codes)))
    result = bytearray(struct.pack("<HH", count + 1, seed))
    offset = 4 + len(entries) * 8
    for i, entry in enumerate(entries):
        key = (seed * 765 * (i + 1)) & 65535; key |= key << 16
        result += struct.pack("<II", offset ^ key, (len(entry) // 2) ^ key)
        offset += len(entry)
    return bytes(result) + b"".join(entries), count


def apply_catch_lock(rom):
    staged = deepcopy(rom)
    a = staged.arm9
    if a[0x52284:0x52288] != thumb_bl(0x2052284, 0x203A138):
        raise RomError("Unsupported encounter initialization")
    ov = staged.overlay_data(13); base = staged.overlays[13].ramAddress
    check = 0x2226B8A - base; msg = 0x2226B9A - base
    if (ov[check:check + 8] != bytes.fromhex("201c223000780128")
            or ov[msg:msg + 4] != thumb_bl(0x2226B9A, 0x200B1B8)):
        raise RomError("Unsupported battle bag; catch restriction not applied")
    # These unknown flags are inside the existing saved flag block. Reject a
    # base whose field scripts use them; never overwrite story progress.
    _, scripts = staged.get_narc("fielddata/script/scr_seq.narc")
    for data in scripts.files:
        for i in range(len(data) - 3):
            if data[i:i+2] in (b"\x1e\0", b"\x1f\0", b"\x20\0", b"\x21\0") and int.from_bytes(data[i+2:i+4], "little") in RESERVED_FLAGS:
                raise RomError("Encounter save flags conflict with field scripts")
    start_size = len(build_start(0x2000000, 0))
    start_off = _find_code_cave(bytes(a), start_size + 4)
    if start_off is None: raise RomError("No encounter state storage")
    state_off = start_off + start_size
    state = 0x2000000 + state_off
    a[start_off:state_off] = build_start(0x2000000 + start_off, state)
    a[state_off:state_off+4] = b"LOCK"
    def install(builder, *args):
        size = len(builder(0x2000000, state, *args))
        off = _find_code_cave(bytes(a), size)
        if off is None: raise RomError("No space for encounter hook")
        payload = builder(0x2000000 + off, state, *args)
        a[off:off+len(payload)] = payload
        return 0x2000000 + off
    start = 0x2000000 + start_off
    ball = install(build_ball_check)
    path, messages = staged.get_narc("msgdata/pl_msg.narc")
    messages.files[2], message_id = append_message(messages.files[2])
    message = install(build_message, message_id)
    a[0x52284:0x52288] = thumb_bl(0x2052284, start)
    ov[check:check+8] = thumb_bl(0x2226B8A, ball) + bytes.fromhex("0128c046")
    ov[msg:msg+4] = thumb_bl(0x2226B9A, message)
    a[state_off:state_off+4] = bytes(4)
    staged.mark_overlay_dirty(13); staged.set_narc(path, messages)
    rom.__dict__.update(staged.__dict__)
    return "First wild encounter per named area is catchable; later ball attempts show a message. Area progress is saved in-game."
