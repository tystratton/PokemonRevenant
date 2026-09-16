from random import Random

from plat_rand.binary import read_u32, write_u32
from plat_rand.constants import ENCOUNTER_FILE_SIZE
from plat_rand.encounters import randomize_encounter_table
from plat_rand.species import SPECIES_NAMES, species_pool


def _blank_area(grass_rate: int = 25, species: int = 399) -> bytearray:
    data = bytearray(ENCOUNTER_FILE_SIZE)
    write_u32(data, 0, grass_rate)
    for slot in range(12):
        write_u32(data, 4 + slot * 8, 3)  # level
        write_u32(data, 4 + slot * 8 + 4, species)
    write_u32(data, WATER_SURF := 204, 10)
    for slot in range(5):
        write_u32(data, 208 + slot * 8, (4 << 8) | 8)
        write_u32(data, 208 + slot * 8 + 4, species)
    _ = WATER_SURF
    return data


def test_species_table_covers_gen4() -> None:
    assert len(SPECIES_NAMES) == 494
    assert SPECIES_NAMES[25] == "Pikachu"
    assert SPECIES_NAMES[387] == "Turtwig"
    assert SPECIES_NAMES[493] == "Arceus"


def test_randomize_keeps_levels_and_rates() -> None:
    original = _blank_area()
    table = bytearray(original)
    changes = randomize_encounter_table(table, Random(1), species_pool(), area=7)
    assert changes
    assert read_u32(table, 0) == 25
    assert read_u32(table, 4) == 3
    assert read_u32(table, 8) != 0
    assert all(change.area == 7 for change in changes)


def test_empty_area_is_left_alone() -> None:
    table = _blank_area(grass_rate=0)
    write_u32(table, 204, 0)
    changes = randomize_encounter_table(table, Random(2), species_pool(), area=0)
    grass_species = [read_u32(table, 8 + slot * 8) for slot in range(12)]
    assert grass_species == [399] * 12
    assert all(change.kind != "Grass" for change in changes)
