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
        "--no-legendaries",
        action="store_true",
        help="Keep legendaries/mythicals out of encounters and starters",
    )
    parser.add_argument("--no-lua", action="store_true", help="Do not write the BizHawk helper .lua")
    parser.add_argument("--no-renegade", action="store_true", help="Do not auto-apply the Renegade patch")
    parser.add_argument("--no-launch", action="store_true", help="Do not open an emulator after writing the ROM")
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

    options = RandomizeOptions(
        seed=args.seed,
        allow_legendaries=not args.no_legendaries,
        write_lua=not args.no_lua,
        apply_renegade=not args.no_renegade,
        launch=not args.no_launch,
    )
    try:
        if args.rom:
            result = randomize_rom(Path(args.rom), args.output, options)
        else:
            result = randomize_auto(options)
    except (RomError, FileNotFoundError, OSError, PatchError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(result.public_text())
    return 0
