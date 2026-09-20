from plat_rand.binary import read_u16
from plat_rand.constants import STARTER_OFFSET, VANILLA_STARTERS
from plat_rand.starters import StarterResult, _find_starter_offset, _read_starters, _write_starters


def test_starter_table_roundtrip() -> None:
    overlay = bytearray(STARTER_OFFSET + 16)
    _write_starters(overlay, VANILLA_STARTERS, STARTER_OFFSET)
    assert _read_starters(overlay, STARTER_OFFSET) == VANILLA_STARTERS
    assert _find_starter_offset(overlay) == STARTER_OFFSET
    _write_starters(overlay, (25, 6, 9), STARTER_OFFSET)
    assert read_u16(overlay, STARTER_OFFSET) == 25


def test_describe_does_not_name_species() -> None:
    result = StarterResult(overlay_id=78, old=VANILLA_STARTERS, new=(25, 6, 9))
    text = result.describe().lower()
    for name in ("turtwig", "chimchar", "piplup", "pikachu", "charizard", "blastoise"):
        assert name not in text


def test_ambiguous_graphics_prefix_leaves_the_briefcase_alone():
    """Two matches must skip the rewrite, not corrupt code at the first one."""
    from plat_rand.constants import STARTER_GRAPHICS_PREFIX
    from plat_rand.starters import _patch_dppt_starter_graphics

    filler = bytes(0x80)
    overlay = bytearray(STARTER_GRAPHICS_PREFIX + filler + STARTER_GRAPHICS_PREFIX + filler)
    before = bytes(overlay)
    notes: list[str] = []
    _patch_dppt_starter_graphics(overlay, (1, 2, 3), notes)
    assert bytes(overlay) == before
    assert "left vanilla" in notes[0]


def test_graphics_prefix_at_the_very_end_is_not_written_past():
    from plat_rand.constants import STARTER_GRAPHICS_PREFIX
    from plat_rand.starters import _patch_dppt_starter_graphics

    overlay = bytearray(bytes(0x40) + STARTER_GRAPHICS_PREFIX + bytes(4))
    before = bytes(overlay)
    notes: list[str] = []
    _patch_dppt_starter_graphics(overlay, (387, 390, 393), notes)
    assert bytes(overlay) == before
    assert "no room" in notes[0]


def test_briefcase_art_is_opt_in():
    """Renegade's guide says the pictures are the one thing not to rewrite."""
    from plat_rand.constants import STARTER_GRAPHICS_PREFIX
    from plat_rand.starters import _patch_graphics_and_cries

    overlay = bytearray(STARTER_GRAPHICS_PREFIX + bytes(0x100))
    before = bytes(overlay)
    notes: list[str] = []
    _patch_graphics_and_cries(overlay, (1, 296, 319), (387, 390, 393), notes)
    assert bytes(overlay) == before, "default build must not touch overlay code"
    assert any("left vanilla" in n for n in notes)

    notes2: list[str] = []
    overlay2 = bytearray(before)
    _patch_graphics_and_cries(overlay2, (1, 296, 319), (387, 390, 393), notes2, True)
    assert bytes(overlay2) != before, "--briefcase-art must still work"
