"""Start a new game at the Route 201 starter chooser (US Platinum/Renegade).

Reference: pret/pokeplatinum's field_map_change.c, script_manager.c,
rowan_intro_app.c and scripts_route_201.s.  Transition scripts are
synchronous; only the on-frame script may launch the starter application.

Reload the two scene NPCs after ReturnToField, while the screen is black,
to avoid exhausting the field heap during map reconstruction.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field

from plat_rand.binary import read_u16, read_u32, write_u32
from plat_rand.constants import ITEM_BICYCLE, SCRIPT_LIST_TERMINATOR, SCRIPT_PATHS, STARTER_SCRIPT_FILE
from plat_rand.rom import RomError

_START_LOCATION_OFF = 0xEA12C
_START_LOCATION_SIG = bytes.fromhex("9F010000FFFFFFFF040000000600000000000000")
_ROUTE_201 = 342
_BRIEFCASE_X, _BRIEFCASE_Z = 113, 854
_ROUTE_201_INIT_FILE = 909
_ROUTE_201_EVENT_FILE = 328
_VAR_ROUTE201 = 0x4086
_OV57_ROWAN_PTR_OFF = 0x44
_OV73_TEMPLATE = 0x020F6824
_NEWSAVE_TEMPLATE = 0x020EA10C
_OV73_RAM = 0x021D0D80
_OV73_MAIN_OFF = 0xA0
_OV73_MAIN_SIG = bytes.fromhex("78B583B0")
_OV73_MAIN_SKIP = bytes.fromhex("01207047")
_OV73_EXIT_NAME_OFF = 0x21A
_OV73_EXIT_NAME_SIG = bytes.fromhex("606854F64CFF")
_OV73_EXIT_RESUME = 0x244
# Reuse the now-unreachable Main body, not arbitrary zero-filled ARM9 data.
_IDENTITY_OFF = 0xA4
_GET_TRAINER_INFO = 0x25E38
_SAVE_TABLE_MISC = 0x2783C
_MARKER = b"PLAT_INTRO_SKIP_V4"

@dataclass
class IntroResult:
    patched: bool = False
    notes: list[str] = field(default_factory=list)

def thumb_bl(src: int, dest: int) -> bytes:
    """ARMv4T Thumb BL (ARM9 has no Thumb-2 branch encoding)."""
    offset = dest - (src + 4)
    if offset % 2 or not -(1 << 22) <= offset < (1 << 22):
        raise ValueError("Thumb BL target is unaligned or out of range")
    return ((0xF000 | ((offset >> 12) & 0x7FF)).to_bytes(2, "little")
            + (0xF800 | ((offset >> 1) & 0x7FF)).to_bytes(2, "little"))

def _thumb_b(src: int, dest: int) -> bytes:
    offset = dest - (src + 4)
    if offset % 2 or not -2048 <= offset <= 2046:
        raise ValueError("Thumb B target is unaligned or out of range")
    return (0xE000 | ((offset >> 1) & 0x7FF)).to_bytes(2, "little")

def _strh(rd: int, rn: int, byte_off: int) -> bytes:
    imm5 = byte_off // 2
    return (0x8000 | (imm5 << 6) | (rn << 3) | rd).to_bytes(2, "little")


def _build_identity_payload(cave: int) -> bytes:
    """Thumb hook; r4 is RowanIntro, with SaveData* at +4."""
    parts = bytearray.fromhex("20B56068")

    def bl(dest: int) -> None:
        parts.extend(thumb_bl(0x02000000 + cave + len(parts), 0x02000000 + dest))

    def name(codes: tuple[int, ...]) -> None:
        for i, code in enumerate(codes):
            # English Gen 4 characters exceed one byte.
            parts.extend(bytes((code >> 8, 0x21)))
            parts.extend(bytes.fromhex("0902"))
            parts.extend(bytes((code & 0xFF, 0x31)))
            parts.extend(_strh(1, 5, i * 2))
        parts.extend(bytes.fromhex("0021491E"))
        parts.extend(_strh(1, 5, len(codes) * 2))

    bl(_GET_TRAINER_INFO)
    parts.extend(bytes.fromhex("051C"))
    name((0x137, 0x153, 0x153))  # Moo
    parts.extend(bytes.fromhex("012129766068"))  # female at +0x18, then SaveData*
    bl(_SAVE_TABLE_MISC)
    parts.extend(bytes.fromhex("0721090224314018051C"))  # MiscSaveBlock + 0x724
    name((0x12C, 0x145, 0x156, 0x156, 0x15D))  # Barry
    parts.extend(bytes.fromhex("20BD"))
    return bytes(parts)


def _u16(value: int) -> bytes:
    return value.to_bytes(2, "little")


def _cmd(opcode: int, *args: int) -> bytes:
    return _u16(opcode) + b"".join(_u16(arg) for arg in args)


def script_jump(src: int, dest: int) -> bytes:
    return _cmd(0x16) + (dest - src - 6).to_bytes(4, "little", signed=True)


def _script_offsets(data: bytes) -> list[int]:
    offsets = []
    cursor = 0
    while cursor + 2 <= len(data):
        if read_u16(data, cursor) == SCRIPT_LIST_TERMINATOR:
            if not offsets or any(o < cursor + 2 or o >= len(data) for o in offsets):
                break
            return offsets
        if cursor + 4 > len(data):
            break
        offsets.append(cursor + 4 + read_u32(data, cursor))
        cursor += 4
    raise RomError("Invalid Route 201 script table; intro skip was not applied")


def build_transition_setup(src: int, original: int) -> bytes:
    # Nonzero story state: run the original gender setup without touching NPCs.
    parts = bytearray(_cmd(0x11, _VAR_ROUTE201, 0))
    parts += _cmd(0x1C) + b"\x05" + (original - (src + 13)).to_bytes(4, "little", signed=True)
    # IDs and flags verified against the Route 201 event records. ID 5 is Rowan!
    for local_id, flag, x, z, direction in (
        (2, 0x172, 114, 853, 1),  # Barry, south
        (5, 0x178, 113, 853, 1),  # Rowan, south
        (6, 0x179, 112, 853, 3),  # Lucas/Dawn, east
        (12, 0x17D, 112, 854, 1), # briefcase
    ):
        parts += _cmd(0x1F, flag)
        parts += _cmd(0x186, local_id, x, z)
        parts += _cmd(0x189, local_id, direction)
        parts += _cmd(0x188, local_id, 0xE + direction)
    # Preserve the original gender-dependent graphics slot setup.
    parts += script_jump(src + len(parts), original)
    return bytes(parts)


def _patch_scene(rom) -> None:
    path, narc = rom.get_narc(*SCRIPT_PATHS)
    scripts = bytearray(narc.files[STARTER_SCRIPT_FILE])
    offsets = _script_offsets(scripts)
    if len(offsets) < 16 or scripts[offsets[0]:offsets[0] + 4] != bytes.fromhex("4d010040"):
        raise RomError("Route 201 was already modified or is unsupported. Rebuild from the clean Renegade base.")
    case = offsets[12]
    if scripts[case:case + 26] != bytes.fromhex("6000bc000600010000000000bd001e007d0165000c00b400b500"):
        raise RomError("Route 201 starter scene does not match the supported ROM")
    if bytes(narc.files[_ROUTE_201_INIT_FILE]) != bytes.fromhex("0201000000000000"):
        raise RomError("Route 201 map initialization is unsupported")
    _, events = rom.get_narc("fielddata/eventdata/zone_event.narc")
    data = events.files[_ROUTE_201_EVENT_FILE]
    if read_u32(data, 0) != 0 or len(data) < 8 + read_u32(data, 4) * 32:
        raise RomError("Route 201 object table is unsupported")
    records = {read_u16(data, o): data[o:o + 32] for o in range(8, 8 + read_u32(data, 4) * 32, 32)
               if read_u16(data, o + 8) in (0x172, 0x178, 0x179, 0x17D)}
    for local_id, gfx, flag in ((2, 148, 0x172), (5, 99, 0x178), (6, 101, 0x179), (12, 174, 0x17D)):
        rec = records.get(local_id, b"")
        if len(rec) != 32 or read_u16(rec, 2) != gfx or read_u16(rec, 8) != flag:
            raise RomError("Route 201 characters were modified. Rebuild from the clean Renegade base.")

    # Both outcomes of the first battle converge here before healing/warping.
    # Finish the skipped town/house/lake events together, without granting the
    # Pokedex or skipping Mom's later journal/parcel sequence.
    finish_signature = bytes.fromhex("2800864002002800a440030003001e00")
    if scripts.count(finish_signature) != 1:
        raise RomError("First rival battle ending is unsupported")
    finish = scripts.index(finish_signature)
    cleanup = len(scripts)
    for var, value in (
        (0x4086, 4),  # finished following Barry
        (0x40A4, 5), # home after the running-shoes introduction
        (0x4070, 2), # disable guitarist's forced Barry reminder
        (0x40E6, 1), # disable Barry's front-door collision
        (0x40A3, 1), # finished upstairs at Barry's house
        (0x4082, 1), # finished lakefront walk
        (0x4095, 1), # finished first visit to Lake Verity
    ):
        scripts += _cmd(0x28, var, value)
    for flag in (0xEA, 0x172, 0x174, 0x176, 0x196, 0x1F2):
        scripts += _cmd(0x1E, flag)
    scripts += script_jump(len(scripts), finish + 12)
    scripts[finish:finish + 6] = script_jump(finish, cleanup)

    setup = len(scripts)
    scripts += build_transition_setup(setup, offsets[0])
    write_u32(scripts, 0, setup - 4)

    # Keep character textures out of the field renderer's temporary rebuild
    # allocations. Otherwise Field1 runs out of memory and a NARC read through
    # NULL overwrites ITCM. Restore both actors before the original fade-in.
    if scripts[case + 26:case + 28] != _cmd(0xA1):
        raise RomError("Starter scene ReturnToField instruction is unsupported")
    chooser = len(scripts)
    scripts += scripts[case:case + 14]
    scripts += _cmd(0x65, 5) + _cmd(0x65, 6)
    scripts += scripts[case + 14:case + 28]
    scripts += _cmd(0x64, 5) + _cmd(0x64, 6)
    scripts += script_jump(len(scripts), case + 28)
    write_u32(scripts, 48, chooser - 52)

    bootstrap = len(scripts)
    # State 2 is normal progress after the rival battle; never retrigger there.
    scripts += _cmd(0x28, _VAR_ROUTE201, 1)
    scripts += _cmd(0x15A)
    scripts += _cmd(0x7B, ITEM_BICYCLE, 1, 0x800C)
    scripts += script_jump(len(scripts), chooser)
    write_u32(scripts, 4, bootstrap - 8)
    scripts += _MARKER
    narc.files[STARTER_SCRIPT_FILE] = bytes(scripts)
    narc.files[_ROUTE_201_INIT_FILE] = (
        b"\x01" + (6).to_bytes(4, "little") + bytes.fromhex("020100000000")
        + _cmd(_VAR_ROUTE201, 0, 2) + b"\x00\x00"
    )
    rom.set_narc(path, narc)


def _apply(rom) -> None:
    if bytes(rom.arm9[_START_LOCATION_OFF:_START_LOCATION_OFF + 20]) != _START_LOCATION_SIG:
        raise RomError("Intro skip requires the clean US Platinum/Renegade base, not a previously randomized ROM")
    ov57 = rom.overlay_data(57)
    if read_u32(ov57, _OV57_ROWAN_PTR_OFF) != _OV73_TEMPLATE:
        raise RomError("New-game application chain is unsupported")
    ov73 = rom.overlay_data(73)
    if (bytes(ov73[_OV73_MAIN_OFF:_OV73_MAIN_OFF + 4]) != _OV73_MAIN_SIG
            or bytes(ov73[_OV73_EXIT_NAME_OFF:_OV73_EXIT_NAME_OFF + 6]) != _OV73_EXIT_NAME_SIG):
        raise RomError("Naming overlay is unsupported; rebuild from the clean base")
    _patch_scene(rom)
    payload = _build_identity_payload(_OV73_RAM + _IDENTITY_OFF - 0x02000000)
    if _IDENTITY_OFF + len(payload) >= 0x1FC:
        raise RomError("Identity hook exceeds the skipped naming code")
    ov73[_OV73_MAIN_OFF:_OV73_MAIN_OFF + 4] = _OV73_MAIN_SKIP
    ov73[_IDENTITY_OFF:_IDENTITY_OFF + len(payload)] = payload
    ov73[_OV73_EXIT_NAME_OFF:_OV73_EXIT_NAME_OFF + 4] = thumb_bl(
        _OV73_RAM + _OV73_EXIT_NAME_OFF, _OV73_RAM + _IDENTITY_OFF)
    ov73[_OV73_EXIT_NAME_OFF + 4:_OV73_EXIT_NAME_OFF + 6] = _thumb_b(
        _OV73_EXIT_NAME_OFF + 4, _OV73_EXIT_RESUME)
    rom.mark_overlay_dirty(73)
    rom.arm9[_START_LOCATION_OFF:_START_LOCATION_OFF + 20] = b"".join(
        v.to_bytes(4, "little") for v in (_ROUTE_201, 0xFFFFFFFF, _BRIEFCASE_X, _BRIEFCASE_Z, 2))


def apply_intro_skip(rom) -> IntroResult:
    """Apply atomically; a missing scene must never leave a broken spawn patch."""
    staged = deepcopy(rom)
    try:
        _apply(staged)
    except (FileNotFoundError, IndexError, KeyError, AttributeError) as exc:
        raise RomError("Required intro resources are missing; no intro changes were applied") from exc
    rom.__dict__.update(staged.__dict__)
    return IntroResult(True, [
        "New Game opens the three-Pokemon suitcase automatically (Moo / Barry)",
        "Starter scene characters are positioned before the map loads",
        "Running shoes and bicycle given once; Barry intro errands completed after either battle outcome",
    ])
