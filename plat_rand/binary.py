"""Little-endian helpers and byte-pattern search."""

from __future__ import annotations


def read_u16(data: bytes | bytearray, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 2], "little")


def read_s32(data: bytes | bytearray, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 4], "little", signed=True)


def read_u32(data: bytes | bytearray, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 4], "little")


def write_u16(data: bytearray, offset: int, value: int) -> None:
    data[offset : offset + 2] = int(value & 0xFFFF).to_bytes(2, "little")


def write_u32(data: bytearray, offset: int, value: int) -> None:
    data[offset : offset + 4] = int(value & 0xFFFFFFFF).to_bytes(4, "little")


def read_relative_pointer(data: bytes | bytearray, offset: int) -> int:
    return read_s32(data, offset) + offset + 4


def find_all(haystack: bytes | bytearray, needle: bytes) -> list[int]:
    if not needle:
        return []
    hits: list[int] = []
    start = 0
    while True:
        idx = haystack.find(needle, start)
        if idx < 0:
            return hits
        hits.append(idx)
        start = idx + 1


def find_unique(haystack: bytes | bytearray, needle: bytes) -> int | None:
    hits = find_all(haystack, needle)
    return hits[0] if len(hits) == 1 else None


def thumb_bl(src: int, dest: int) -> bytes:
    """ARMv4T Thumb BL (ARM9 has no Thumb-2 branch encoding)."""
    offset = dest - (src + 4)
    if offset % 2 or not -(1 << 22) <= offset < (1 << 22):
        raise ValueError("Thumb BL target is unaligned or out of range")
    return ((0xF000 | ((offset >> 12) & 0x7FF)).to_bytes(2, "little")
            + (0xF800 | ((offset >> 1) & 0x7FF)).to_bytes(2, "little"))
