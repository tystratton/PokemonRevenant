from plat_rand.binary import write_u16
from plat_rand.exp_share import (
    _MASK_NEW,
    _MASK_OLD,
    _MASK_REL,
    _NOP_OLD,
    _NOP_REL,
    _NOP_UNSPLIT,
    _SIG,
)


def test_split_patch_only_changes_the_participant_mask() -> None:
    overlay = bytearray(0x20000)
    sig = 0x58FC
    overlay[sig : sig + 4] = _SIG
    write_u16(overlay, sig + _MASK_REL, _MASK_OLD)
    write_u16(overlay, sig + _NOP_REL, _NOP_OLD)
    write_u16(overlay, sig + _MASK_REL, _MASK_NEW)
    assert int.from_bytes(overlay[sig + _MASK_REL : sig + _MASK_REL + 2], "little") == 0x203F
    assert int.from_bytes(overlay[sig + _NOP_REL : sig + _NOP_REL + 2], "little") == _NOP_OLD
    assert _NOP_UNSPLIT != _NOP_OLD
