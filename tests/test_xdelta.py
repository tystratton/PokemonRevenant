import pytest

from plat_rand import xdelta
from plat_rand.xdelta import PatchError, ensure_xdelta3


@pytest.fixture
def root(tmp_path):
    (tmp_path / "tools").mkdir()
    return tmp_path


def test_posix_ignores_a_vendored_windows_exe(root, monkeypatch):
    """A Windows binary left by an earlier run must not be run on Linux."""
    (root / "tools" / "xdelta3.exe").write_bytes(b"MZ")
    monkeypatch.setattr(xdelta.os, "name", "posix")
    monkeypatch.setattr(xdelta.shutil, "which", lambda name: "/usr/bin/xdelta3")
    assert str(ensure_xdelta3(root)) == "/usr/bin/xdelta3"


def test_posix_without_xdelta3_explains_how_to_install(root, monkeypatch):
    (root / "tools" / "xdelta3.exe").write_bytes(b"MZ")
    monkeypatch.setattr(xdelta.os, "name", "posix")
    monkeypatch.setattr(xdelta.shutil, "which", lambda name: None)
    with pytest.raises(PatchError, match="apt-get install"):
        ensure_xdelta3(root)


def test_posix_prefers_a_vendored_posix_binary(root, monkeypatch):
    local = root / "tools" / "xdelta3"
    local.write_bytes(b"\x7fELF")
    monkeypatch.setattr(xdelta.os, "name", "posix")
    monkeypatch.setattr(xdelta.shutil, "which", lambda name: "/usr/bin/xdelta3")
    assert ensure_xdelta3(root) == local


def test_windows_uses_the_vendored_exe(root, monkeypatch):
    exe = root / "tools" / "xdelta3.exe"
    exe.write_bytes(b"MZ")
    monkeypatch.setattr(xdelta.os, "name", "nt")
    monkeypatch.setattr(xdelta.shutil, "which", lambda name: None)
    assert ensure_xdelta3(root) == exe
