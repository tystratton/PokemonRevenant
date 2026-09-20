"""Run the full randomizer pipeline on a Platinum / Renegade ROM."""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from pathlib import Path
from random import Random

from plat_rand import __version__
from plat_rand.encounters import EncounterResult, randomize_encounters
from plat_rand.catch_lock import apply_catch_lock
from plat_rand.exp_share import ExpShareResult, apply_party_exp_share
from plat_rand.items import ItemResult, patch_items
from plat_rand.launch import launch_rom
from plat_rand.nuzlocke import NuzlockeResult, apply_nuzlocke_patches
from plat_rand.paths import (
    AutoInputs,
    assert_safe_output,
    default_output_rom,
    iter_renegade_patches,
    rom_patch_hint,
)
from plat_rand.rom import (
    PlatinumRom,
    RomError,
    assert_complete_rom,
    looks_like_renegade_file,
)
from plat_rand.constants import STARTER_OVERLAY_ID, VANILLA_STARTERS
from plat_rand.starters import StarterResult, randomize_starters
from plat_rand.xdelta import PatchError, apply_xdelta


@dataclass
class RandomizeOptions:
    seed: int | None = None
    allow_legendaries: bool = True
    write_lua: bool = True
    apply_renegade: bool = True
    launch: bool = True
    # Per-patch switches, so a crash can be bisected to one subsystem.
    starters: bool = True
    briefcase_art: bool = False
    encounters: bool = True
    items: bool = True
    exp_share: bool = True
    nuzlocke: bool = True
    catch_lock: bool = False


def options_catch_lock_applied(result) -> bool:
    return not any("catch lock" in w for w in result.warnings)


@dataclass
class RandomizeResult:
    input_path: Path
    output_path: Path
    log_path: Path
    seed: int
    title: str
    game_code: str
    renegade: bool
    starters: StarterResult
    encounters: EncounterResult
    items: ItemResult
    nuzlocke: NuzlockeResult
    exp_share: ExpShareResult
    warnings: list[str] = field(default_factory=list)
    patch_path: Path | None = None
    base_path: Path | None = None
    launched: str | None = None

    def log_text(self) -> str:
        lines = [
            f"Platinum Nuzlocke Randomizer {__version__}",
            f"Input:  {self.input_path}",
        ]
        if self.patch_path:
            lines.append(f"Patch:  {self.patch_path}")
        if self.base_path and self.base_path != self.input_path:
            lines.append(f"Base:   {self.base_path}")
        lines.extend(
            [
                f"Output: {self.output_path}",
                f"ROM:    {self.title} ({self.game_code})",
                f"Trainers: {'Renegade Platinum (kept)' if self.renegade else 'NOT Renegade — vanilla trainers'}",
                f"Seed:   {self.seed}",
                "",
                self.starters.describe(),
            ]
        )
        lines.extend(f"  {note}" for note in self.starters.notes)
        lines.append("")
        lines.append(
            f"Wild encounters: {len(self.encounters.changed)} species slots in "
            f"{self.encounters.areas} areas ({self.encounters.path})"
        )
        for change in self.encounters.changed:
            lines.append(f"  {change.describe()}")
        lines.append("")
        lines.extend(self.items.notes)
        lines.append("")
        lines.extend(self.exp_share.notes)
        lines.append("")
        if self.nuzlocke.cave_offset is not None:
            lines.append(f"Nuzlocke cave at ARM9 0x{self.nuzlocke.cave_offset:X}")
        lines.extend(f"  {hook}" for hook in self.nuzlocke.hooks)
        lines.extend(f"  {note}" for note in self.nuzlocke.notes)
        if self.warnings:
            lines.append("")
            lines.append("Warnings:")
            lines.extend(f"  {warning}" for warning in self.warnings)
        if self.launched:
            lines.append("")
            lines.append(self.launched)
        lines.append("")
        lines.append("Rules baked into this ROM:")
        lines.append("  - Renegade Platinum trainer teams and difficulty kept")
        lines.append("  - Wild encounters randomized")
        lines.append("  - Starters randomized; briefcase shows the real ones")
        lines.append("  - The normal Platinum intro plays in full; no scene or story flags are skipped")
        lines.append("  - Whole party shares each fight's exp (split among them)")
        lines.append("  - Rare Candies replaced with Exp. Share")
        lines.append("  - Revives cannot be used")
        lines.append("  - Fainted party Pokémon are deleted after battle (in the ROM)")
        lines.append("  - Wiping freezes the game; start a new randomized ROM for the next run")
        if not options_catch_lock_applied(self):
            lines.append("  - One catch per area: NOT APPLIED (known crash)")
        else:
            lines.append("  - Only the first wild in a named area can be caught; later throws are denied in-game")
        return "\n".join(lines) + "\n"

    def public_text(self) -> str:
        lines = [
            f"Wrote {self.output_path}",
            f"Log   {self.log_path}",
            f"Seed  {self.seed}",
            "Run the randomizer again for a new seed; this file is left as-is.",
            f"Trainers: {'Renegade Platinum (kept)' if self.renegade else 'NOT Renegade — vanilla trainers'}",
            f"Wild encounters: {len(self.encounters.changed)} slots in {self.encounters.areas} areas",
            self.starters.describe(),
        ]
        lines.extend(self.exp_share.notes)
        lines.extend(self.nuzlocke.notes)
        if self.launched:
            lines.append(self.launched)
        elif self.warnings:
            lines.extend(self.warnings)
        return "\n".join(lines) + "\n"


def _ensure_renegade_base(
    source: Path,
    options: RandomizeOptions,
    warnings: list[str],
) -> tuple[Path, Path | None]:
    if looks_like_renegade_file(source):
        return source, None
    if not options.apply_renegade:
        warnings.append("Renegade patch was skipped; trainer teams are whatever is in the input ROM.")
        return source, None

    inputs = AutoInputs.discover()
    if inputs.renegade_base.is_file() and inputs.renegade_base.stat().st_size >= 80_000_000:
        warnings.append(f"Reusing patched Renegade base at {inputs.renegade_base.name}")
        return inputs.renegade_base, inputs.renegade_patch

    try:
        hint = rom_patch_hint(source)
    except OSError:
        hint = None
    patches = iter_renegade_patches(inputs.root, hint=hint)
    if not patches:
        raise RomError(
            "Need a Renegade Platinum .xdelta next to the project so trainer "
            "difficulty can be applied automatically."
        )

    assert_safe_output(inputs.renegade_base, source)
    errors: list[str] = []
    for patch in patches:
        try:
            apply_xdelta(source, patch, inputs.renegade_base)
            if not looks_like_renegade_file(inputs.renegade_base):
                warnings.append(
                    f"Applied {patch.name}; header title is still not 'RENEGADE' "
                    "but the patch was written."
                )
            return inputs.renegade_base, patch
        except PatchError as exc:
            errors.append(str(exc))
    raise PatchError("None of the Renegade patches applied to this Platinum dump.\n" + "\n".join(errors))


def randomize_rom(
    input_path: str | Path,
    output_path: str | Path | None = None,
    options: RandomizeOptions | None = None,
) -> RandomizeResult:
    options = options or RandomizeOptions()
    input_path = Path(input_path)
    output_path = Path(output_path) if output_path else default_output_rom()
    seed = options.seed if options.seed is not None else secrets.randbits(32)
    rng = Random(seed)
    warnings: list[str] = []

    assert_complete_rom(input_path)
    base_path, patch_path = _ensure_renegade_base(input_path, options, warnings)
    assert_safe_output(output_path, input_path, base_path)

    print(f"Randomizing {base_path.name} -> {output_path}")
    rom = PlatinumRom.load(base_path)
    if not rom.is_renegade:
        warnings.append(
            "The ROM that was randomized does not look like Renegade Platinum. "
            "Trainer teams may still be vanilla."
        )

    skipped: list[str] = []

    def note_skip(name: str) -> None:
        skipped.append(name)
        warnings.append(f"{name} was skipped (--no-{name.replace(' ', '-')}).")

    if options.starters:
        starters = randomize_starters(
            rom, rng, allow_legendaries=options.allow_legendaries,
            briefcase_art=options.briefcase_art,
        )
    else:
        note_skip("starters")
        vanilla = tuple(VANILLA_STARTERS)
        starters = StarterResult(STARTER_OVERLAY_ID, vanilla, vanilla,
                                 ["Starters left vanilla"])
    if options.encounters:
        encounters = randomize_encounters(rom, rng, allow_legendaries=options.allow_legendaries)
    else:
        note_skip("encounters")
        encounters = EncounterResult(path="(skipped)")
    if options.items:
        items = patch_items(rom)
    else:
        note_skip("items")
        items = ItemResult(notes=["Item changes skipped"])
    if options.exp_share:
        exp_share = apply_party_exp_share(rom)
    else:
        note_skip("exp share")
        exp_share = ExpShareResult(notes=["Party exp share skipped"])
    lua_file = output_path.with_suffix(".lua") if options.write_lua else None
    if options.nuzlocke:
        nuzlocke = apply_nuzlocke_patches(rom, lua_path=lua_file)
    else:
        note_skip("nuzlocke")
        nuzlocke = NuzlockeResult(notes=["Nuzlocke death rules skipped"])
    if options.catch_lock:
        nuzlocke.notes.append(apply_catch_lock(rom))
    else:
        note_skip("catch lock")
        nuzlocke.notes.append(
            "One catch per area is OFF: its hook still crashes on the first "
            "loading-screen map transition. Force it on with --catch-lock."
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    rom.save(output_path)
    launched = None
    if options.launch:
        lua_path = Path(nuzlocke.lua_path) if nuzlocke.lua_path else None
        launched = launch_rom(output_path, lua_path)
        if launched is None:
            warnings.append(
                "No DS emulator was found on PATH. Open the new .nds yourself; "
                "in BizHawk also load the matching .lua next to it."
            )
    result = RandomizeResult(
        input_path=input_path,
        output_path=output_path,
        log_path=output_path.with_suffix(output_path.suffix + ".log"),
        seed=seed,
        title=rom.title,
        game_code=rom.game_code,
        renegade=rom.is_renegade,
        starters=starters,
        encounters=encounters,
        items=items,
        nuzlocke=nuzlocke,
        exp_share=exp_share,
        warnings=warnings,
        patch_path=patch_path,
        base_path=base_path,
        launched=launched,
    )
    result.log_path.write_text(result.log_text(), encoding="utf-8")
    return result


def randomize_auto(options: RandomizeOptions | None = None) -> RandomizeResult:
    inputs = AutoInputs.discover()
    if not inputs.vanilla_rom:
        raise RomError(
            "Put your clean Pokémon Platinum .nds in the project root "
            "(for example 'Pokemon - Platinum Version (USA).nds')."
        )
    return randomize_rom(inputs.vanilla_rom, inputs.output_rom, options)
