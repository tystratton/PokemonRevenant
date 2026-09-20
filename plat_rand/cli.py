"""Command-line and drag-and-drop entry points."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from plat_rand import __version__
from plat_rand.pipeline import RandomizeOptions, randomize_auto, randomize_rom
from plat_rand.rom import RomError
from plat_rand.xdelta import PatchError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="plat-rand",
        description=(
            "Apply Renegade Platinum, then randomize wilds/starters with "
            "nuzlocke rules. Clean .nds files in the project root are never overwritten."
        ),
    )
    parser.add_argument("rom", nargs="?", help="Optional input .nds; omitted = auto-detect")
    parser.add_argument("-o", "--output", help="Output .nds (default: out/RenegadePlatinum-nuzlocke.nds)")
    parser.add_argument("--seed", type=int, help="RNG seed (random if omitted)")
    parser.add_argument(
        "--count",
        type=int,
        default=1,
        metavar="N",
        help="Generate N ROMs, each with its own seed (default: 1)",
    )
    parser.add_argument(
        "--no-legendaries",
        action="store_true",
        help="Keep legendaries/mythicals out of encounters and starters",
    )
    parser.add_argument("--no-lua", action="store_true", help="Do not write the BizHawk helper .lua")
    parser.add_argument("--no-renegade", action="store_true", help="Do not auto-apply the Renegade patch")
    parser.add_argument("--no-launch", action="store_true", help="Do not open an emulator after writing the ROM")
    skips = parser.add_argument_group(
        "bisecting a crash",
        "Disable one patch at a time to find which one a misbehaving ROM dislikes.",
    )
    for flag, help_text in (
        ("starters", "randomized starters and the briefcase sprite/cry rewrite"),
        ("encounters", "wild encounter randomization"),
        ("items", "Rare Candy -> Exp. Share and unusable Revives"),
        ("exp-share", "whole-party exp sharing"),
        ("nuzlocke", "fainted-mon deletion and the wipe freeze"),
        ("catch-lock", "one catch per area"),
    ):
        skips.add_argument(f"--no-{flag}", action="store_true", help=f"Skip {help_text}")
    parser.add_argument(
        "--briefcase-art",
        action="store_true",
        help="Also rewrite the briefcase sprite code (Renegade's guide advises against it)",
    )
    parser.add_argument("--gui", action="store_true", help="Open the window")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def run_cli(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.gui:
        from plat_rand.gui import run_gui

        run_gui(
            initial_rom=args.rom,
            initial_output=args.output,
            initial_seed=args.seed,
        )
        return 0

    if args.count < 1:
        parser.error("--count must be at least 1")
    if args.count > 1 and args.output:
        parser.error("--output names a single file; drop it when using --count")
    if args.count > 1 and args.seed is not None:
        parser.error("--seed fixes one shuffle; drop it when using --count")

    options = RandomizeOptions(
        seed=args.seed,
        allow_legendaries=not args.no_legendaries,
        write_lua=not args.no_lua,
        apply_renegade=not args.no_renegade,
        # Opening N emulators at once helps nobody.
        launch=not args.no_launch and args.count == 1,
        starters=not args.no_starters,
        briefcase_art=args.briefcase_art,
        encounters=not args.no_encounters,
        items=not args.no_items,
        exp_share=not args.no_exp_share,
        nuzlocke=not args.no_nuzlocke,
        catch_lock=not args.no_catch_lock,
    )

    results = []
    for index in range(args.count):
        if args.count > 1:
            print(f"--- ROM {index + 1} of {args.count} ---")
        try:
            if args.rom:
                result = randomize_rom(Path(args.rom), args.output, options)
            else:
                result = randomize_auto(options)
        except (RomError, FileNotFoundError, OSError, PatchError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            # Keep whatever already succeeded; report it before giving up.
            for done in results:
                print(f"  kept {done.output_path}", file=sys.stderr)
            return 1
        results.append(result)

    for result in results:
        print(result.public_text())
    if len(results) > 1:
        print(f"Wrote {len(results)} ROMs:")
        for result in results:
            print(f"  {result.output_path}  (seed {result.seed})")
    return 0
