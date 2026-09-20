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
- The normal Platinum intro, exactly as Renegade ships it (name yourself, watch the Rowan scene, pick from the briefcase)
- Whole party shares each fight's exp (split among whoever is getting it)
- Rare Candies replaced with Exp. Share
- Revives unusable
- Fainted party Pokémon deleted after battle (baked into the `.nds`)
- Wipe freezes the game. Run the randomizer again for a new seed and a new file
- One catch per area is **off by default** — its hook still crashes on the first loading-screen map transition. `--catch-lock` forces it on

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

- Uses **Complete** Renegade (normal 1/8192 shiny rate) when that patch is present.
- The randomizer does not print starter names. Look at the briefcase in-game.
- If an emulator is installed (BizHawk / melonDS / DeSmuME), the ROM is launched after a run. Use `--no-launch` to skip that.
- Death and wipe live in the `.nds`. DeSmuME is enough. Run `python randomize.py` again for a new seed; the previous play file is not overwritten.
- The one-catch-per-area rule is in the `.nds` and is saved with the game. The matching `.lua` is unused for that.

This repo does not include Nintendo ROMs. You supply Platinum; Renegade is applied from Drayanoâ€™s official patch that you copied in.

## The Lake Verity crash

The one-catch-per-area hook replaces the `BL MapHeader_GetMapLabelTextID` at
ARM9 `0x52284`. It used to read `[r5, #0]` for the battle type, on the
strength of a comment saying `r5=dto`.

`r5` is not a finished struct there. The enclosing function at `0x020521b8`
takes it as its output parameter and is still filling it in; nothing writes
`[r5, #0]` before that call site, so the hook tested uninitialised memory and
let whatever was in that slot decide whether it ran.

The intro skip hid this for as long as it existed: it warped New Game to the
Route 201 briefcase and set `0x4095`, *finished first visit to Lake Verity*,
so nobody ever walked out of that lake. Removing the skip did not break the
hook, it exposed it.

That read is gone, but it was not the whole story: the crash survives its
removal. Bisection is unambiguous that `apply_catch_lock` is responsible, so
the feature is off by default until the real cause is found.

Ruled out so far: the hook payloads are byte-identical to what the source
generates; the code caves sit in ARM9 section 0 data, not BSS, and do not
overlap any of the 122 overlays' RAM ranges; the save flags land inside the
364-byte array the resolver at `0x2050870` bounds-checks; the appended
message bank decodes byte-identically for all 49 original entries.

Still unexamined: which of the seven entry points into `0x02052314` runs on a
map transition, and what the hook does to save state when it fires there.

## No intro skip

Earlier builds skipped the intro: they warped New Game straight to the Route 201
briefcase and bulk-set the story variables and flags for everything in between
(Twinleaf, both houses, the lakefront walk, the first Lake Verity visit).
Those forced values did not match the state the real scripts leave behind, so
later events read the game as further along than it was: the Jubilife trainer
school was broken, Lake Verity could not be revisited, and Jubilife had no
working exit. The skip has been removed entirely rather than patched around —
the intro now runs normally and every story variable is set by the game's own
scripts.

Nothing else changed: randomized wilds and starters, party exp share, Rare
Candy to Exp. Share, unusable Revives, fainted-mon deletion, the wipe freeze and
the one-catch-per-area rule are all still applied.

The running shoes and bicycle that the skip handed out at the start are gone
with it; you get them from the normal intro instead.

An in-progress save made on an intro-skip ROM keeps the bad story state — it is
stored in the save file, not the ROM. Generate a new ROM and start a **New
Game** to get the fixed progression.
