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
