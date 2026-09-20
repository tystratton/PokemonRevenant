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


def test_ambiguous_signature_leaves_the_battle_overlay_alone():
    """A 4-byte anchor driving a write 0x12C0C away must be unique."""
    from plat_rand.exp_share import _SIG, _MASK_REL, _MASK_OLD, apply_party_exp_share

    overlay = bytearray(_MASK_REL + 0x2000)
    overlay[0x10:0x14] = _SIG
    overlay[0x20:0x24] = _SIG  # a second, decoy match
    overlay[0x10 + _MASK_REL:0x10 + _MASK_REL + 2] = _MASK_OLD.to_bytes(2, "little")
    before = bytes(overlay)

    class FakeRom:
        def overlay_data(self, _id):
            return overlay

    result = apply_party_exp_share(FakeRom())
    assert bytes(overlay) == before
    assert not result.patched
    assert "ambiguous" in result.notes[0]
