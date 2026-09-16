from plat_rand.binary import read_u16, write_u16
from plat_rand.constants import ITEM_EXP_SHARE, ITEM_RARE_CANDY
from plat_rand.items import _replace_item_id


def test_rare_candy_becomes_exp_share() -> None:
    assert _replace_item_id(ITEM_RARE_CANDY) == ITEM_EXP_SHARE
    assert _replace_item_id(ITEM_EXP_SHARE) == ITEM_EXP_SHARE
    assert _replace_item_id(17) == 17


def test_u16_roundtrip() -> None:
    buf = bytearray(4)
    write_u16(buf, 2, ITEM_RARE_CANDY)
    assert read_u16(buf, 2) == ITEM_RARE_CANDY
