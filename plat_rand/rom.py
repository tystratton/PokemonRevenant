"""Load and save a Platinum / Renegade Platinum NDS ROM."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import ndspy.code
import ndspy.codeCompression
import ndspy.narc
import ndspy.rom

from plat_rand.constants import GAME_CODES, TRAINER_POKE_PATHS


class RomError(ValueError):
    """The file is not a usable Platinum ROM."""


def peek_title(path: str | Path) -> str:
    with Path(path).open("rb") as handle:
        return handle.read(12).decode("ascii", "replace").strip("\x00 ")


# NDS header: total used ROM size. A complete dump is never smaller than this.
_USED_SIZE_OFFSET = 0x80
_PLAUSIBLE_USED_SIZE = range(1 << 20, (256 << 20) + 1)


def declared_rom_size(path: str | Path) -> int | None:
    """Bytes of real data the NDS header claims, or None if it reads as junk."""
    with Path(path).open("rb") as handle:
        handle.seek(_USED_SIZE_OFFSET)
        field = handle.read(4)
    if len(field) < 4:
        return None
    declared = int.from_bytes(field, "little")
    return declared if declared in _PLAUSIBLE_USED_SIZE else None


def assert_complete_rom(path: str | Path) -> None:
    """Reject a half-transferred dump before xdelta blames the wrong revision."""
    path = Path(path)
    declared = declared_rom_size(path)
    actual = path.stat().st_size
    if declared is not None and actual < declared:
        raise RomError(
            f"{path.name} is incomplete: {actual:,} bytes on disk, but its own "
            f"header declares {declared:,} bytes of ROM data "
            f"({actual / declared:.0%} present). The download or upload was cut "
            "short; re-transfer the file and check its size before using it."
        )


def looks_like_renegade_file(path: str | Path) -> bool:
    title = peek_title(path).upper()
    return "RENEGADE" in title


@dataclass
class PlatinumRom:
    path: Path
    nds: ndspy.rom.NintendoDSRom
    arm9: bytearray
    arm9_was_compressed: bool
    overlays: dict[int, ndspy.code.Overlay] = field(default_factory=dict)
    dirty_overlays: set[int] = field(default_factory=set)

    @classmethod
    def load(cls, path: str | Path) -> PlatinumRom:
        path = Path(path)
        nds = ndspy.rom.NintendoDSRom.fromFile(str(path))
        raw_code = bytes(nds.idCode or b"")[:4]
        raw_name = bytes(nds.name or b"")
        if raw_code not in GAME_CODES:
            title = raw_name.decode("ascii", "replace").strip()
            if b"PLAT" not in raw_name.upper() and "PLAT" not in title.upper():
                raise RomError(
                    f"{path.name} does not look like Pokémon Platinum "
                    f"(game code {raw_code!r}, title {title!r})."
                )
        raw_arm9 = nds.arm9
        decompressed = ndspy.codeCompression.decompress(raw_arm9)
        return cls(
            path=path,
            nds=nds,
            arm9=bytearray(decompressed),
            arm9_was_compressed=decompressed != raw_arm9,
        )

    @property
    def title(self) -> str:
        return self.nds.name.decode("ascii", "replace").strip("\x00 ")

    @property
    def game_code(self) -> str:
        return self.nds.idCode[:4].decode("ascii", "replace")

    @property
    def is_renegade(self) -> bool:
        blob = self.title.upper()
        if "RENEGADE" in blob:
            return True
        try:
            trainers = self.get_file(*TRAINER_POKE_PATHS)
        except FileNotFoundError:
            return False
        # Vanilla US Platinum trpoke.narc is 28600 bytes. Renegade grows it.
        return len(trainers) > 35_000

    def list_filenames(self) -> list[str]:
        names: list[str] = []

        def walk(folder, prefix: str = "") -> None:
            for name, child in folder.folders:
                walk(child, f"{prefix}{name}/")
            for name in folder.files:
                names.append(f"{prefix}{name}")

        walk(self.nds.filenames)
        return names

    def find_file(self, *candidates: str) -> str:
        for name in candidates:
            try:
                self.nds.getFileByName(name)
                return name
            except (ValueError, KeyError):
                continue
        available = self.list_filenames()
        lowered = {item.lower(): item for item in available}
        for name in candidates:
            if name.lower() in lowered:
                return lowered[name.lower()]
            tail = name.rsplit("/", 1)[-1].lower()
            for item in available:
                if item.lower().endswith("/" + tail) or item.lower() == tail:
                    return item
        raise FileNotFoundError(
            "Could not find any of: " + ", ".join(candidates)
        )

    def get_file(self, *candidates: str) -> bytes:
        return self.nds.getFileByName(self.find_file(*candidates))

    def set_file(self, name: str, data: bytes) -> None:
        self.nds.setFileByName(name, data)

    def get_narc(self, *candidates: str) -> tuple[str, ndspy.narc.NARC]:
        name = self.find_file(*candidates)
        return name, ndspy.narc.NARC(self.nds.getFileByName(name))

    def set_narc(self, name: str, narc: ndspy.narc.NARC) -> None:
        self.nds.setFileByName(name, narc.save())

    def get_overlay(self, overlay_id: int) -> ndspy.code.Overlay:
        if overlay_id not in self.overlays:
            loaded = self.nds.loadArm9Overlays({overlay_id})
            if overlay_id not in loaded:
                raise FileNotFoundError(f"ARM9 overlay {overlay_id} is missing")
            self.overlays[overlay_id] = loaded[overlay_id]
        return self.overlays[overlay_id]

    def overlay_data(self, overlay_id: int) -> bytearray:
        overlay = self.get_overlay(overlay_id)
        if not isinstance(overlay.data, bytearray):
            overlay.data = bytearray(overlay.data)
        return overlay.data

    def mark_overlay_dirty(self, overlay_id: int) -> None:
        self.dirty_overlays.add(overlay_id)

    def save(self, path: str | Path) -> None:
        if self.arm9_was_compressed:
            self.nds.arm9 = ndspy.codeCompression.compress(bytes(self.arm9), isArm9=True)
        else:
            self.nds.arm9 = bytes(self.arm9)

        if self.dirty_overlays:
            table = self.nds.loadArm9Overlays()
            for overlay_id in self.dirty_overlays:
                overlay = self.overlays.get(overlay_id) or table[overlay_id]
                table[overlay_id] = overlay
                # Overlay.save fills compressedSize in from the data length.
                # Platinum stores 0 there for every uncompressed overlay, so
                # writing a real size makes the patched entries the only ones
                # in the table that disagree with the rest. Keep what was
                # there; saving a whole table must not edit untouched fields.
                original_size = overlay.compressedSize
                self.nds.files[overlay.fileID] = overlay.save(compress=overlay.compressed)
                if not overlay.compressed:
                    overlay.compressedSize = original_size
            self.nds.arm9OverlayTable = ndspy.code.saveOverlayTable(table)

        self.nds.saveToFile(str(path))
