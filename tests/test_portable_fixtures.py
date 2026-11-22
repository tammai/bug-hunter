import os
import re
import shutil
import subprocess
from pathlib import Path

import conftest
import pytest

TRICKY = "Bug $(touch pwned) `touch pwned` \"q\" 'q' & | < > ^ %PATH% ü"


def test_fake_gh_is_an_interpreter_and_keeps_arguments_exact(fake_gh, tmp_path):
    env, calls = fake_gh
    gh = shutil.which("gh", path=env["PATH"])
    assert gh and not Path(gh).read_bytes().startswith(b"#!")
    args = ["issue", "create", "--title", TRICKY, "--body-file", str(tmp_path / "a b ü.md")]
    # By path: on Windows a child's env doesn't change where CreateProcess looks for "gh".
    result = subprocess.run([gh, *args], env=env, cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "https://github.com/o/r/issues/1"
    assert calls() == [args]
    assert not (tmp_path / "pwned").exists()


def test_fake_gh_moves_userprofile_with_home(fake_gh):
    env, _ = fake_gh
    assert env["USERPROFILE"] == env["HOME"]


def test_rmtree_removes_read_only_entries(tmp_path):
    tree = tmp_path / "tree"
    (tree / "locked").mkdir(parents=True)
    (tree / "ro.txt").write_text("x", encoding="utf-8")
    (tree / "ro.txt").chmod(0o444)
    (tree / "locked" / "inside.txt").write_text("x", encoding="utf-8")
    (tree / "locked" / "inside.txt").chmod(0o444)
    (tree / "locked").chmod(0o555)
    conftest.rmtree(tree)
    assert not tree.exists()


def test_mode_is_exact_on_posix_and_true_on_windows(tmp_path, monkeypatch):
    path = tmp_path / "f"
    path.write_text("x", encoding="utf-8")
    path.chmod(0o600)
    if os.name != "nt":
        monkeypatch.setattr(conftest, "WINDOWS", False)
        assert conftest.mode_is(path, 0o600) and not conftest.mode_is(path, 0o644)
    monkeypatch.setattr(conftest, "WINDOWS", True)
    assert conftest.mode_is(path, 0o644)


def test_lock_dir_refuses_new_files_until_unlocked(tmp_path):
    folder = tmp_path / "drafts ü"
    folder.mkdir()
    conftest.lock_dir(folder)
    try:
        with pytest.raises(PermissionError):
            (folder / "new").open("x").close()
        assert [p.name for p in folder.iterdir()] == []
    finally:
        conftest.unlock_dir(folder)
    (folder / "new").open("x").close()
    assert (folder / "new").exists()


def test_symlink_probe_skips_with_its_reason(tmp_path, monkeypatch):
    def refuse(*args, **kwargs):
        raise OSError(1314, "A required privilege is not held by the client")

    with monkeypatch.context() as mp:
        mp.setattr(os, "symlink", refuse)
        with pytest.raises(pytest.skip.Exception, match="Developer Mode"):
            conftest.skip_unless_git_keeps_symlinks(tmp_path / "no rights")

    try:
        os.symlink("x", tmp_path / "can link")
    except OSError:
        return  # An account without link rights takes the branch above for real.
    with monkeypatch.context() as mp:
        for key, value in {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.symlinks",
                           "GIT_CONFIG_VALUE_0": "false"}.items():
            mp.setenv(key, value)
        with pytest.raises(pytest.skip.Exception, match="plain file"):
            conftest.skip_unless_git_keeps_symlinks(tmp_path / "as files")

    if os.name != "nt":
        conftest.skip_unless_git_keeps_symlinks(tmp_path / "plain")


def test_ci_runs_the_suite_on_windows():
    workflow = Path(__file__).resolve().parent.parent / ".github/workflows/sdlc-verify.yml"
    matrix = re.search(r"^\s*os: \[(.*)\]$", workflow.read_text(encoding="utf-8"), re.M)
    assert matrix, "no os matrix in sdlc-verify.yml"
    assert {'"ubuntu-latest"', '"windows-latest"'} <= {o.strip() for o in matrix[1].split(",")}
