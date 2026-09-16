"""Patch overlay 16 so the whole living party shares battle exp (split)."""

from __future__ import annotations

from dataclasses import dataclass, field

from plat_rand.binary import write_u16

# Demonic722 "EXP Share All" for US Platinum: mark every party slot as a
# participant. Leave the original divide in place so the pot is split.
_SIG = bytes.fromhex("12F0D8FD")
_MASK_REL = 0x12C0C  # orrs r0, r1  -> movs r0, #0x3F  (all 6 party slots)
_NOP_REL = 0x143C  # divide/filter BL — must stay so exp stays split
_MASK_OLD = 0x4308
_MASK_NEW = 0x203F
_NOP_OLD = 0xF6A0
_NOP_UNSPLIT = 0xE000  # old "full exp each" patch; revert if present
BATTLE_OVERLAY_ID = 16


@dataclass
class ExpShareResult:
    overlay_id: int = BATTLE_OVERLAY_ID
    notes: list[str] = field(default_factory=list)
    patched: bool = False


def apply_party_exp_share(rom) -> ExpShareResult:
    """Whole living party gets exp, split between however many are getting it."""
    result = ExpShareResult()
    try:
        overlay = rom.overlay_data(BATTLE_OVERLAY_ID)
    except FileNotFoundError:
        result.notes.append("Battle overlay 16 is missing; party Exp Share was not patched")
        return result

    sig = overlay.find(_SIG)
    if sig < 0:
        result.notes.append("Battle exp signature not found; party Exp Share was not patched")
        return result

    mask_at = sig + _MASK_REL
    nop_at = sig + _NOP_REL
    if max(mask_at + 2, nop_at + 2) > len(overlay):
        result.notes.append("Battle overlay is shorter than the exp-share patch expects")
        return result

    mask_now = int.from_bytes(overlay[mask_at : mask_at + 2], "little")
    nop_now = int.from_bytes(overlay[nop_at : nop_at + 2], "little")
    changed = False

    if mask_now == _MASK_OLD:
        write_u16(overlay, mask_at, _MASK_NEW)
        changed = True
    elif mask_now != _MASK_NEW:
        result.notes.append(
            f"Battle exp mask was not the expected instruction ({mask_now:#06x}); left unchanged"
        )
        return result

    if nop_now == _NOP_UNSPLIT:
        write_u16(overlay, nop_at, _NOP_OLD)
        changed = True
    elif nop_now != _NOP_OLD:
        result.notes.append(
            f"Battle exp divide instruction was unexpected ({nop_now:#06x}); "
            "party still shares, split may be wrong"
        )

    if changed:
        rom.mark_overlay_dirty(BATTLE_OVERLAY_ID)

    result.patched = True
    result.notes.append(
        "Whole living party shares each fight's exp (split by how many get it)"
    )
    return result
