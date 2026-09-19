import struct

import pytest

from plat_rand.binary import thumb_bl


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
