# Platinum Nuzlocke Randomizer

Drop a clean US Platinum `.nds` in the project root and keep a Renegade Platinum `.xdelta` nearby (you already have both). Then:

```bat
python randomize.py
```

The tool **applies Renegade Platinum Complete automatically**, randomizes wilds and starters, and writes a new file under `out\`. If `RenegadePlatinum-nuzlocke.nds` already exists, the next run writes `RenegadePlatinum-nuzlocke-2.nds` (and so on) so an in-progress play file is never overwritten.

Your clean root ROM is never overwritten.

## What you boot

- Renegade Platinum trainer teams and difficulty
- Randomized wild encounters (same levels)
- Randomized starters (briefcase shows the real ones)
- New Game skips the intro and opens the three-Pokemon suitcase automatically (girl named Moo, rival Barry, running shoes and bicycle already given)
- Whole party shares each fight's exp (split among whoever is getting it)
- Rare Candies replaced with Exp. Share
- Revives unusable
- Fainted party Pokémon deleted after battle (baked into the `.nds`)
- Wipe freezes the game. Run the randomizer again for a new seed and a new file
- Only the first wild Pokémon in a named area can be caught; later throws show "First encounter already used in this area!"

## Install once

```bat
pip install -r requirements.txt
```

## Run

```bat
python randomize.py
```

Or double-click `randomize.bat`. Optional:

```bat
python randomize.py --seed 12345
python randomize.py --gui
```

Outputs stay in `out\`. Intermediate patched Renegade is `out\_renegade_base.nds` so later seeds do not re-apply the xdelta.

## Notes

- For the intro fix, boot a newly generated ROM and start **New Game**. Old save states retain the broken scene state. Press Start at the title screen; the suitcase opens automatically after loading.

- Uses **Complete** Renegade (normal 1/8192 shiny rate) when that patch is present.
- The randomizer does not print starter names. Look at the briefcase in-game.
- If an emulator is installed (BizHawk / melonDS / DeSmuME), the ROM is launched after a run. Use `--no-launch` to skip that.
- Death and wipe live in the `.nds`. DeSmuME is enough. Run `python randomize.py` again for a new seed; the previous play file is not overwritten.
- The one-catch-per-area rule is in the `.nds` and is saved with the game. The matching `.lua` is unused for that.

This repo does not include Nintendo ROMs. You supply Platinum; Renegade is applied from Drayanoâ€™s official patch that you copied in.

## Intro-skip fix

The skip now initializes the Route 201 characters and uses an on-frame script to
open the suitcase once. Rowan and the counterpart are removed while the screen
is black and restored after the field renderer reloads. This avoids a failed
character-texture allocation that otherwise overwrites instruction memory.
The native starter grant, dialogue, rival battle, and return home are preserved.
The identity hook uses Gen 4 character codes and lives in skipped overlay code.
Unsupported layouts fail before changing the ROM.

References: [Route 201 scripts](https://github.com/pret/pokeplatinum/blob/main/res/field/scripts/scripts_route_201.s),
[map script lifecycle](https://github.com/pret/pokeplatinum/blob/main/include/constants/init_script_types.h),
and [character texture allocation](https://github.com/pret/pokeplatinum/blob/main/src/overlay005/ov5_021ECC20.c).

Validation: 22 tests passed. The complete randomized build was booted in
DeSmuME from the title screen through suitcase selection, the scene, Barry's
battle, and the return home. The chosen seed was kept at 1583383857.
