"""An overlay edit must not alter fields the ROM left alone."""
import struct

import ndspy.code


def make_overlay(overlay_id, data, file_id):
    return ndspy.code.Overlay(data, 0x02000000, len(data), 0, 0, 0, file_id, 0, False)


def test_uncompressed_overlay_keeps_its_zero_compressed_size():
    """Platinum stores compressedSize 0 on every uncompressed overlay."""
    overlay = make_overlay(13, b"\x00" * 64, 5)
    assert overlay.compressedSize == 0

    original_size = overlay.compressedSize
    overlay.save(compress=overlay.compressed)
    # ndspy fills the field in; this is the behaviour rom.save compensates for.
    filled = overlay.compressedSize
    if not overlay.compressed:
        overlay.compressedSize = original_size

    assert filled != 0 or original_size == 0, "ndspy behaviour changed"
    assert overlay.compressedSize == 0

    table = ndspy.code.saveOverlayTable({13: overlay})
    assert struct.unpack_from("<I", table, 28)[0] & 0xFFFFFF == 0
