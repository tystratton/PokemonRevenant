from pathlib import Path

import pytest

from plat_rand.paths import (
    OUTPUT_ROM_NAME,
    assert_safe_output,
    default_output_rom,
    is_protected_source,
    repo_root,
)


def test_root_nds_is_protected() -> None:
    root = repo_root()
    vanilla = root / "Pokemon - Platinum Version (USA).nds"
    assert is_protected_source(vanilla, root)


def test_out_folder_is_not_a_source_rom() -> None:
    root = repo_root()
    output = root / "out" / OUTPUT_ROM_NAME
    assert not is_protected_source(output, root)


def test_in_use_play_rom_is_not_overwritten() -> None:
    root = repo_root()
    playing = root / "out" / OUTPUT_ROM_NAME
    if playing.is_file():
        with pytest.raises(ValueError, match="in-use"):
            assert_safe_output(playing, vanilla_if_present(root), root=root)
        nxt = default_output_rom(root)
        assert nxt.resolve() != playing.resolve()
        assert not nxt.is_file()
    else:
        assert default_output_rom(root).name == OUTPUT_ROM_NAME


def vanilla_if_present(root: Path) -> Path:
    return root / "Pokemon - Platinum Version (USA).nds"
