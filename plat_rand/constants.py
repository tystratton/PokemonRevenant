"""Platinum (Gen 4) ROM constants used by the randomizer."""

from __future__ import annotations

GAME_CODES = {b"CPUE", b"CPUP", b"CPUJ"}

WILD_ENCOUNTER_PATHS = (
    "fielddata/encountdata/pl_enc_data.narc",
    "fielddata/encountdata/d_enc_data.narc",
    "fielddata/encountdata/p_enc_data.narc",
)
SCRIPT_PATHS = (
    "fielddata/script/scr_seq.narc",
    "data/script/scr_seq.narc",
)
ITEM_DATA_PATHS = (
    "itemtool/itemdata/pl_item_data.narc",
    "itemtool/itemdata/item_data.narc",
)
TRAINER_POKE_PATHS = (
    "poketool/trainer/trpoke.narc",
    "poketool/trainer/trdata.narc",
)

# DPPt encounter area: 424 bytes. See pret/pokeplatinum WildEncounters.
ENCOUNTER_FILE_SIZE = 424
GRASS_SLOTS = 12
WATER_SLOTS = 5
WATER_SET_COUNT = 5
WATER_SET_START = 204

STARTER_OVERLAY_ID = 78
STARTER_OFFSET = 0x1BC0
STARTER_SCRIPT_FILE = 427
STARTER_HELD_ITEM_OFFSET = 0x460
STARTER_GRAPHICS_PREFIX = bytes.fromhex("000222402104120C")
STARTER_GRAPHICS_PREFIX_INNER = bytes.fromhex("0290039002200002")
STARTER_CRIES_PREFIX = bytes.fromhex(
    "0004000C10BD0000000000000000000000E000000000000000E0000000000200"
)

# Turtwig, Chimchar, Piplup
VANILLA_STARTERS = (387, 390, 393)

RIVAL_SCRIPT_FILES = (31, 36, 112, 123, 186, 427, 429, 1096)
RIVAL_SCRIPT_MAGIC = bytes.fromhex("DE000C8011000C8083011C0001")
TAG_SCRIPT_FILES = (2, 136, 201, 236)
TAG_SCRIPT_MAGIC_1 = bytes.fromhex("DE000C8028000480")
TAG_SCRIPT_MAGIC_2 = bytes.fromhex("11000C8086011C0001")

ITEM_BALL_SCRIPT_FILE = 404
ITEM_BALL_SKIP = {25, 238, 321, 325, 326}
SCRIPT_LIST_TERMINATOR = 0xFD13
SET_VAR_COMMAND = 0x28
ITEM_SCRIPT_VARIABLE = 0x8008

HIDDEN_ITEM_OFFSET = 0xEA378
HIDDEN_ITEM_COUNT = 257
HIDDEN_ITEM_STRIDE = 8

SHOP_COUNT = 29
SHOP_SKIP = {13, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24}
SHOP_DATA_PREFIX = bytes.fromhex("ED7F0402258004026180040281800402")

ITEM_RARE_CANDY = 50
ITEM_BICYCLE = 73
ITEM_EXP_SHARE = 216
ITEM_POTION = 17
ITEM_REVIVE = 24
ITEM_MAX_REVIVE = 25
ITEM_SACRED_ASH = 32
ITEM_REVIVAL_HERB = 156

REVIVE_ITEMS = (
    ITEM_REVIVE,
    ITEM_MAX_REVIVE,
    ITEM_SACRED_ASH,
    ITEM_REVIVAL_HERB,
)

# Gen 4 item data: battle-use and field-use bytes.
ITEM_FIELD_USE_OFFSET = 4
ITEM_BATTLE_USE_OFFSET = 5

MAX_SPECIES = 493
POKEMON_PARTY_SIZE = 236
PARTY_HP_OFFSET = 0x8E

# US Platinum (CPUE) save pointer used by Action Replay codes.
PLATINUM_US_SAVE_POINTER = 0x02101D40
