import os
import stat

import pytest
import throwaway

posix = pytest.mark.skipif(os.name == "nt" or os.geteuid() == 0,
                           reason="needs a POSIX folder that refuses unlinks, which root ignores")


@posix
@pytest.mark.parametrize("name", ["0 locked", "~ locked"])
def test_ignoring_errors_removes_everything_it_can(tmp_path, name):
    top = tmp_path / "copy"
    locked = top / name
    locked.mkdir(parents=True)
    (locked / "f").write_text("x", encoding="utf-8")
    # Folders on both sides: shutil removes a folder's files before walking its subfolders.
    siblings = [top / f"{c} sibling" / "f" for c in "abcdwxyz"]
    for path in siblings:
        path.parent.mkdir()
        path.write_text("x", encoding="utf-8")
    locked.chmod(0o555)
    try:
        throwaway._rmtree(top, ignore_errors=True)
        assert not [p for p in siblings if p.exists()]
        assert (locked / "f").exists()
    finally:
        locked.chmod(0o755)


@posix
def test_without_ignoring_the_first_error_raises(tmp_path):
    top = tmp_path / "copy"
    locked = top / "locked"
    locked.mkdir(parents=True)
    (locked / "f").write_text("x", encoding="utf-8")
    locked.chmod(0o555)
    try:
        with pytest.raises(PermissionError):
            throwaway._rmtree(top)
    finally:
        locked.chmod(0o755)


def test_a_link_at_the_top_is_refused_not_followed(tmp_path):
    target = tmp_path / "outside"
    target.mkdir()
    (target / "keep").write_text("x", encoding="utf-8")
    try:
        os.symlink(target, tmp_path / "link", target_is_directory=True)
    except OSError:
        pytest.skip("can't create symlinks here: Windows needs Developer Mode or admin")
    with pytest.raises(OSError):
        throwaway._rmtree(tmp_path / "link")
    throwaway._rmtree(tmp_path / "link", ignore_errors=True)
    assert (target / "keep").exists()


def test_windows_retry_clears_read_only_and_removes(tmp_path, monkeypatch):
    path = tmp_path / "pack.idx"
    path.write_text("x", encoding="utf-8")
    path.chmod(0o444)
    monkeypatch.setattr(throwaway, "WINDOWS", True)
    throwaway._clear_read_only(os.unlink, str(path), PermissionError(5, "Access is denied"))
    assert not path.exists()


def test_windows_retry_never_acts_through_a_link(tmp_path, monkeypatch):
    target = tmp_path / "outside.txt"
    target.write_text("x", encoding="utf-8")
    target.chmod(0o444)
    link = tmp_path / "link"
    try:
        os.symlink(target, link)
    except OSError:
        pytest.skip("can't create symlinks here: Windows needs Developer Mode or admin")
    monkeypatch.setattr(throwaway, "WINDOWS", True)
    refused = PermissionError(5, "Access is denied")
    with pytest.raises(PermissionError) as raised:
        throwaway._clear_read_only(os.unlink, str(link), refused)
    assert raised.value is refused
    assert link.is_symlink() and stat.S_IMODE(target.stat().st_mode) == 0o444
    target.chmod(0o644)


@posix
def test_windows_retry_that_fails_again_raises_its_own_error(tmp_path, monkeypatch):
    folder = tmp_path / "locked"
    folder.mkdir()
    path = folder / "f"
    path.write_text("x", encoding="utf-8")
    folder.chmod(0o555)
    first = PermissionError(5, "Access is denied")
    monkeypatch.setattr(throwaway, "WINDOWS", True)
    try:
        with pytest.raises(PermissionError) as raised:
            throwaway._clear_read_only(os.unlink, str(path), first)
    finally:
        folder.chmod(0o755)
    assert raised.value is not first and path.exists()
