import json
import os
import re
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest
from conftest import SCRIPTS, run_script

SIZE = r"\d+(\.\d)? (B|KB|MB|GB)"


@pytest.fixture
def temp_env(tmp_path):
    temp = tmp_path / "temp"
    temp.mkdir()
    return temp, {**os.environ, "TMPDIR": str(temp), "TEMP": str(temp), "TMP": str(temp)}


def new_run(env) -> str:
    result = run_script("scratch", "new", env=env)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def age(run: str, hours: float) -> None:
    marker = os.path.join(run, ".bug-hunter-run")
    data = json.loads(open(marker, encoding="utf-8").read())
    data["created"] = time.time() - hours * 3600
    with open(marker, "w", encoding="utf-8") as out:
        json.dump(data, out)


def test_new_makes_a_private_marked_run_folder(temp_env):
    temp, env = temp_env
    run = new_run(env)
    assert os.path.dirname(run) == str(temp)
    assert os.path.basename(run).startswith("bug-hunter-")
    assert not any(ch.isspace() for ch in run)
    assert os.path.isfile(os.path.join(run, ".bug-hunter-run"))
    assert os.path.isdir(os.path.join(run, "cache"))
    if os.name != "nt":
        assert stat.S_IMODE(os.stat(run).st_mode) == 0o700
    assert new_run(env) != run


def test_clean_reports_size_and_removes_read_only_trees(temp_env, tmp_path):
    _, env = temp_env
    run = new_run(env)
    mod = os.path.join(run, "hunter-1", "home", "go", "pkg", "mod", "example.com@v1")
    os.makedirs(mod)
    with open(os.path.join(mod, "go.mod"), "w", encoding="utf-8") as out:
        out.write("module example.com\n" * 200)
    os.chmod(os.path.join(mod, "go.mod"), 0o444)
    os.chmod(mod, 0o555)
    outside = tmp_path / "outside ü"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep", encoding="utf-8")
    os.symlink(outside, os.path.join(run, "hunter-1", "link-out"))
    kept = os.path.join(run, "kept")
    os.makedirs(kept)
    with open(os.path.join(kept, "1.md"), "w", encoding="utf-8") as out:
        out.write("# a draft\n")

    result = run_script("scratch", "clean", run, "--keep", "kept", env=env)
    assert result.returncode == 0, result.stderr
    assert re.search(SIZE, result.stdout) and "freed" in result.stdout
    assert sorted(os.listdir(run)) == [".bug-hunter-run", "kept"]
    assert open(os.path.join(kept, "1.md"), encoding="utf-8").read() == "# a draft\n"
    assert (outside / "keep.txt").read_text(encoding="utf-8") == "keep"

    result = run_script("scratch", "clean", run, env=env)
    assert result.returncode == 0, result.stderr
    assert "freed" in result.stdout and not os.path.exists(run)
    assert (outside / "keep.txt").read_text(encoding="utf-8") == "keep"


def test_clean_refuses_folders_it_did_not_make(temp_env, tmp_path):
    temp, env = temp_env
    unmarked = temp / "bug-hunter-unmarked"
    unmarked.mkdir()
    (unmarked / "x").write_text("keep", encoding="utf-8")
    misnamed = temp / "my work"
    misnamed.mkdir()
    (misnamed / ".bug-hunter-run").write_text("{}", encoding="utf-8")
    a_file = temp / "bug-hunter-file"
    a_file.write_text("keep", encoding="utf-8")
    run = new_run(env)
    link = temp / "bug-hunter-link"
    os.symlink(run, link)

    for bad in (unmarked, misnamed, a_file, link, temp / "bug-hunter-missing"):
        result = run_script("scratch", "clean", bad, env=env)
        assert result.returncode == 1, bad
        assert result.stderr.startswith("error:") and "Traceback" not in result.stderr, bad
    assert (unmarked / "x").exists() and (misnamed / ".bug-hunter-run").exists()
    assert a_file.exists() and os.path.isdir(run)

    for keep in ("../x", "a/b", ".bug-hunter-run", ""):
        result = run_script("scratch", "clean", run, "--keep", keep, env=env)
        assert result.returncode == 1 and "Traceback" not in result.stderr, keep
    assert os.path.isdir(os.path.join(run, "cache"))


def test_sweep_removes_only_stale_marked_folders(temp_env):
    temp, env = temp_env
    old, young = new_run(env), new_run(env)
    age(old, 13)
    age(young, 1)
    unmarked = temp / "bug-hunter-unmarked"
    unmarked.mkdir()
    os.utime(unmarked, (time.time() - 99 * 3600,) * 2)
    other = temp / "someone else"
    other.mkdir()
    os.symlink(old, temp / "bug-hunter-link")

    result = run_script("scratch", "sweep", "--older-than", "12", env=env)
    assert result.returncode == 0, result.stderr
    assert not os.path.exists(old) and os.path.isdir(young)
    assert unmarked.is_dir() and other.is_dir()
    assert re.search(rf"removed .*{re.escape(os.path.basename(old))}.*{SIZE}", result.stdout)
    assert re.search(rf"kept .*{re.escape(os.path.basename(young))}.*{SIZE}.*in use",
                     result.stdout)

    result = run_script("scratch", "sweep", "--older-than", "0", env=env)
    assert result.returncode == 0 and not os.path.exists(young)
    result = run_script("scratch", "sweep", "--older-than", "-1", env=env)
    assert result.returncode != 0 and "Traceback" not in result.stderr


root = pytest.mark.skipif(os.name == "nt" or os.geteuid() == 0,
                          reason="POSIX permissions, which root ignores")


@root
def test_sweep_and_clean_skip_folders_they_cannot_read(temp_env):
    temp, env = temp_env
    locked = temp / "bug-hunter-locked"
    locked.mkdir()
    (locked / ".bug-hunter-run").write_text('{"created": 0}', encoding="utf-8")
    locked.chmod(0)
    try:
        old = new_run(env)
        age(old, 13)
        result = run_script("scratch", "sweep", env=env)
        assert result.returncode == 0 and "Traceback" not in result.stderr, result.stderr
        assert not os.path.exists(old)
        result = run_script("scratch", "clean", locked, env=env)
        assert result.returncode == 1 and result.stderr.startswith("error:")
        assert "Traceback" not in result.stderr
    finally:
        locked.chmod(0o700)
    assert (locked / ".bug-hunter-run").exists()


@root
def test_clean_removes_unreadable_and_unwritable_folders(temp_env):
    _, env = temp_env
    run = new_run(env)
    modes = (("no-access", 0), ("write-only", 0o200), ("read-only", 0o500),
             ("no-search", 0o400), ("no-search-write", 0o600))
    for name, mode in modes:
        folder = os.path.join(run, "hunter-1", name)
        os.makedirs(os.path.join(folder, "inner"))
        with open(os.path.join(folder, "inner", "f"), "w", encoding="utf-8") as out:
            out.write("x")
        os.chmod(folder, mode)
    result = run_script("scratch", "clean", run, env=env)
    assert result.returncode == 0, result.stderr
    assert "Traceback" not in result.stderr and not os.path.exists(run)


def _swap_for_link(folder, decoy):
    os.rename(folder, folder + ".real")
    os.symlink(decoy, folder)


@root
def test_clean_never_follows_a_parent_swapped_for_a_link_after_it_is_opened(temp_env, tmp_path,
                                                                            monkeypatch):
    import scratch

    _, env = temp_env
    monkeypatch.setenv("TMPDIR", env["TMPDIR"])
    run = new_run(env)
    parent = os.path.join(run, "hunter-1", "p")
    os.makedirs(os.path.join(parent, "x", "inner"))
    with open(os.path.join(parent, "f1"), "w", encoding="utf-8"):
        pass
    os.chmod(os.path.join(parent, "x"), 0)
    decoy = tmp_path / "decoy"
    (decoy / "x").mkdir(parents=True)
    (decoy / "x" / "secret").write_text("keep", encoding="utf-8")
    (decoy / "f1").write_text("keep", encoding="utf-8")
    os.chmod(decoy / "x", 0o755)
    decoy_mode = 0o755
    real_unlink, swapped = os.unlink, []

    def unlink(path, *args, **kwargs):
        if not swapped and os.path.basename(os.fspath(path)) == "f1":
            swapped.append(1)
            _swap_for_link(parent, decoy)
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(os, "unlink", unlink)
    scratch._clean(Path(run), None)
    monkeypatch.undo()
    assert swapped
    assert sorted(str(p.relative_to(decoy)) for p in decoy.rglob("*")) == [
        "f1", "x", os.path.join("x", "secret")]
    assert stat.S_IMODE(os.stat(decoy / "x").st_mode) == decoy_mode


def test_clean_keeps_going_and_removes_fingerprints_first(temp_env, monkeypatch, capsys):
    import scratch

    temp, env = temp_env
    monkeypatch.setenv("TMPDIR", str(temp))
    run = new_run(env)
    stuck = os.path.join(run, "base", "stuck.txt")
    os.makedirs(os.path.dirname(stuck))
    for path in (stuck, os.path.join(run, "fingerprints.json"),
                 os.path.join(run, "zz-copy", "f")):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as out:
            out.write("x")
    real_unlink = os.unlink

    def unlink(path, *args, **kwargs):
        if os.path.basename(os.fspath(path)) == "stuck.txt":
            raise PermissionError(1, "Operation not permitted", stuck)
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(os, "unlink", unlink)
    code = scratch._main(["clean", run])
    err = capsys.readouterr().err
    assert code == 1 and "stuck.txt" in err
    assert not os.path.exists(os.path.join(run, "fingerprints.json"))
    assert not os.path.exists(os.path.join(run, "zz-copy"))
    assert os.path.exists(os.path.join(run, ".bug-hunter-run"))


def test_clean_never_follows_a_folder_swapped_for_a_link_mid_clean(temp_env, tmp_path,
                                                                   monkeypatch):
    import scratch

    _, env = temp_env
    monkeypatch.setenv("TMPDIR", env["TMPDIR"])
    run = new_run(env)
    victim = os.path.join(run, "hunter-1", "victim")
    os.makedirs(victim)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep", encoding="utf-8")
    real_is_folder = scratch._is_folder

    # Code still running in the run swaps a folder for a link after it was seen as a folder.
    def is_folder(name, fd):
        seen = real_is_folder(name, fd)
        if name == "victim" and seen:
            os.rmdir(victim)
            os.symlink(outside, victim)
        return seen

    monkeypatch.setattr(scratch, "_is_folder", is_folder)
    scratch._clean(Path(run), None)
    monkeypatch.undo()
    assert (outside / "keep.txt").read_text(encoding="utf-8") == "keep"
    assert not os.path.lexists(victim)


@root
def test_clean_removes_the_marker_through_the_run_not_a_swapped_path(temp_env, tmp_path,
                                                                     monkeypatch):
    import scratch

    _, env = temp_env
    monkeypatch.setenv("TMPDIR", env["TMPDIR"])
    run = new_run(env)
    decoy = tmp_path / "decoy"
    decoy.mkdir()
    (decoy / ".bug-hunter-run").write_text("keep", encoding="utf-8")
    real_empty = scratch._empty_dir

    # The run folder itself is swapped for a link once its contents are gone. Only the call
    # for the run (it skips the marker); the same function also empties nested folders.
    def empty(*args, **kwargs):
        real_empty(*args, **kwargs)
        if kwargs.get("skip"):
            os.rename(run, run + ".real")
            os.symlink(decoy, run)

    monkeypatch.setattr(scratch, "_empty_dir", empty)
    errors = scratch._clean(Path(run), None)
    monkeypatch.undo()
    assert os.path.islink(run) and not os.path.exists(run + ".real/.bug-hunter-run")
    assert (decoy / ".bug-hunter-run").read_text(encoding="utf-8") == "keep"
    assert len(errors) == 1 and "Not a directory" in errors[0]


@pytest.mark.skipif(os.name != "nt", reason="directory junctions are Windows only")
def test_clean_removes_a_junction_without_entering_it(temp_env, tmp_path):
    import _winapi

    _, env = temp_env
    run = new_run(env)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep", encoding="utf-8")
    os.makedirs(os.path.join(run, "hunter-1", "copy"))
    _winapi.CreateJunction(str(outside), os.path.join(run, "hunter-1", "copy", "linked"))
    _winapi.CreateJunction(str(outside), os.path.join(run, "top-junction"))
    result = run_script("scratch", "clean", run, env=env)
    assert result.returncode == 0, result.stderr
    assert (outside / "keep.txt").read_text(encoding="utf-8") == "keep"
    assert not os.path.exists(run)


@root
def test_an_unlistable_run_folder_gives_an_error_not_a_traceback(temp_env):
    _, env = temp_env
    run = new_run(env)
    age(run, 13)
    os.chmod(run, 0o300)
    try:
        result = run_script("scratch", "clean", run, env=env)
        assert result.returncode == 1 and "Traceback" not in result.stderr, result.stderr
        result = run_script("scratch", "sweep", env=env)
        assert result.returncode == 0 and "Traceback" not in result.stderr, result.stderr
    finally:
        os.chmod(run, 0o700)


def make_deep(top: str, depth: int) -> None:
    fd = os.open(top, os.O_RDONLY)
    try:
        for _ in range(depth):
            os.mkdir("d", dir_fd=fd)
            inner = os.open("d", os.O_RDONLY, dir_fd=fd)
            os.close(fd)
            fd = inner
    finally:
        os.close(fd)


@pytest.mark.skipif(os.name == "nt", reason="the descriptor walk is POSIX only")
def test_clean_removes_a_tree_deeper_than_the_default_limits(temp_env):
    import resource

    _, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    if hard != resource.RLIM_INFINITY and hard < 2000:
        pytest.skip("the hard open-file limit is too low for a deep tree")
    _, env = temp_env
    run = new_run(env)
    top = os.path.join(run, "hunter-1")
    os.makedirs(top)
    make_deep(top, 600)

    def small_soft_limit():
        # What a shell gives by default on macOS: fewer handles than the tree has levels.
        resource.setrlimit(resource.RLIMIT_NOFILE, (256, hard))

    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "scratch.py"), "clean", run], env=env,
        capture_output=True, text=True, preexec_fn=small_soft_limit)
    assert result.returncode == 0, result.stderr
    assert "Traceback" not in result.stderr and not os.path.exists(run)


@pytest.mark.skipif(os.name == "nt", reason="the descriptor walk is POSIX only")
def test_clean_names_the_real_reason_when_a_folder_cant_be_opened(temp_env, monkeypatch):
    import errno

    import scratch

    temp, env = temp_env
    monkeypatch.setenv("TMPDIR", str(temp))
    run = new_run(env)
    victim = os.path.join(run, "hunter-1", "victim")
    os.makedirs(victim)
    with open(os.path.join(victim, "f"), "w", encoding="utf-8") as out:
        out.write("x")
    real_open = os.open

    def fake_open(path, *args, **kwargs):
        if kwargs.get("dir_fd") is not None and path == "victim":
            raise OSError(errno.EMFILE, os.strerror(errno.EMFILE))
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(os, "open", fake_open)
    errors = scratch._clean(Path(run), None)
    monkeypatch.undo()
    assert any("victim" in e and "Too many open files" in e for e in errors), errors
    assert os.path.exists(os.path.join(victim, "f"))
    assert os.path.exists(os.path.join(run, ".bug-hunter-run"))


def test_windows_clean_ignores_a_top_level_file_that_vanishes(temp_env, monkeypatch):
    import scratch

    temp, env = temp_env
    monkeypatch.setenv("TMPDIR", str(temp))
    run = new_run(env)
    with open(os.path.join(run, "fingerprints.json"), "w", encoding="utf-8") as out:
        out.write("x")

    def gone(path):
        raise FileNotFoundError(2, "No such file or directory", path)

    monkeypatch.setattr(scratch, "_unlink", gone)
    errors: list[str] = []
    scratch._clean_windows(Path(run), None, errors)
    assert errors == []



def _windows_rules(monkeypatch):
    """Make unlink and rmdir refuse an entry without its write bit, as Windows does."""
    real_unlink, real_rmdir = os.unlink, os.rmdir

    def guard(real):
        def call(path, *, dir_fd=None):
            if not os.stat(path, dir_fd=dir_fd, follow_symlinks=False).st_mode & stat.S_IWUSR:
                raise PermissionError(13, "Access is denied", path)
            return real(path, dir_fd=dir_fd)
        return call

    monkeypatch.setattr(os, "unlink", guard(real_unlink))
    monkeypatch.setattr(os, "rmdir", guard(real_rmdir))


def test_windows_tree_removal_clears_read_only_folders(tmp_path, monkeypatch):
    import scratch

    top = tmp_path / "hunter-1"
    mod = top / "home" / "go" / "pkg" / "mod" / "example.com@v1"
    mod.mkdir(parents=True)
    (top / "home" / "go.sum").write_text("x\n", encoding="utf-8")
    os.chmod(top / "home" / "go.sum", 0o444)
    os.chmod(mod, 0o555)
    _windows_rules(monkeypatch)
    errors: list[str] = []
    scratch._remove_tree_windows(str(top), errors)
    monkeypatch.undo()
    assert errors == [] and not top.exists()


@pytest.mark.skipif(os.name == "nt", reason="symlinks need Developer Mode or admin on Windows")
def test_windows_tree_removal_never_changes_modes_through_a_link(tmp_path, monkeypatch):
    import scratch

    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "go.mod").write_text("module x\n", encoding="utf-8")
    os.chmod(outside / "go.mod", 0o444)
    os.chmod(outside, 0o555)
    top = tmp_path / "hunter-1"
    top.mkdir()
    os.symlink(outside, top / "link")
    os.symlink(outside / "go.mod", top / "file-link")
    # One of the run's own, so clean has read-only to clear beside the links.
    (top / "own").mkdir()
    os.chmod(top / "own", 0o555)

    # A link met where a folder or file was seen: swapped in after the check. Only where
    # chmod can refuse to follow a link (macOS, Windows from 3.13); Linux has no lchmod, and
    # clean's chmod runs only on Windows.
    if os.chmod in os.supports_follow_symlinks:
        real_lstat = os.lstat
        (tmp_path / "a file").write_text("x", encoding="utf-8")
        seen = {"link": real_lstat(tmp_path), "file-link": real_lstat(tmp_path / "a file")}
        monkeypatch.setattr(scratch.os, "lstat", lambda p, *a, **k: seen.get(
            os.path.basename(str(p))) or real_lstat(p, *a, **k))
        for name in seen:
            scratch._clear_read_only(str(top / name))
        monkeypatch.undo()
    _windows_rules(monkeypatch)
    errors: list[str] = []
    scratch._remove_tree_windows(str(top), errors)
    monkeypatch.undo()
    assert errors == [] and not top.exists()
    assert stat.S_IMODE(os.lstat(outside).st_mode) == 0o555
    assert stat.S_IMODE(os.lstat(outside / "go.mod").st_mode) == 0o444
    os.chmod(outside, 0o755)


def test_windows_clear_read_only_skips_only_links_among_reparse_points(tmp_path, monkeypatch):
    import scratch

    # A deduplicated or cloud-placeholder file has a reparse point but is a plain file to
    # remove; a symlink or junction (a name surrogate) leads elsewhere.
    files = {"placeholder": 0x80000013, "linked": 0xA000000C}
    real_lstat = os.lstat
    fakes = {}
    for name, tag in files.items():
        path = tmp_path / name
        path.write_text("x", encoding="utf-8")
        os.chmod(path, 0o444)
        info = real_lstat(path)
        fakes[str(path)] = type("Stat", (), {
            "st_mode": info.st_mode, "st_reparse_tag": tag,
            "st_file_attributes": stat.FILE_ATTRIBUTE_REPARSE_POINT})()
    monkeypatch.setattr(scratch.os, "lstat", lambda p, *a, **k: fakes.get(str(p))
                        or real_lstat(p, *a, **k))
    for path in fakes:
        scratch._clear_read_only(path)
    monkeypatch.undo()
    assert os.lstat(tmp_path / "placeholder").st_mode & stat.S_IWUSR
    assert not os.lstat(tmp_path / "linked").st_mode & stat.S_IWUSR
