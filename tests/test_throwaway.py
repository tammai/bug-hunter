import os
import subprocess

from conftest import commit, git, run_script


def head(repo) -> str:
    return subprocess.run(
        ["git", "-C", repo, "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()


def test_copy_is_standalone_and_has_uncommitted_tracked_changes(make_repo, tmp_path):
    repo = make_repo({"cli.py": "print(1)\n"})
    commit(repo)
    wt = tmp_path / "work tree"
    git(repo, "worktree", "add", "-q", str(wt), "-b", "wt")
    (wt / "cli.py").write_text("print(2)\n", encoding="utf-8")
    (wt / ".venv").mkdir()
    (wt / ".venv" / "pyvenv.cfg").write_text(f"home = {wt}\n", encoding="utf-8")
    before = (head(repo), head(wt))

    dest = tmp_path / "scratch ü" / "hunter-1" / "copy"
    result = run_script("throwaway", wt, dest)
    assert result.returncode == 0, result.stderr
    assert (dest / ".git").is_dir()
    assert (dest / "cli.py").read_text(encoding="utf-8") == "print(2)\n"
    assert not (dest / ".venv").exists()
    remotes = subprocess.run(["git", "-C", dest, "remote"], capture_output=True, text=True)
    assert remotes.stdout.strip() == ""

    commit(dest, "inside the copy")
    git(dest, "checkout", "-q", "-b", "other")
    assert (head(repo), head(wt)) == before
    assert (wt / "cli.py").read_text(encoding="utf-8") == "print(2)\n"


def test_refuses_symlinks_out_of_the_copy_and_a_used_dest(make_repo, tmp_path):
    repo = make_repo({"a.py": ""})
    os.symlink("a.py", repo / "inside.py")
    os.symlink(str(tmp_path), repo / "escape")
    git(repo, "add", "-A")
    commit(repo)

    dest = tmp_path / "copy"
    result = run_script("throwaway", repo, dest)
    assert result.returncode == 1
    assert "escape" in result.stderr and "inside.py" not in result.stderr
    assert "Traceback" not in result.stderr
    assert not dest.exists()

    used = tmp_path / "used"
    used.mkdir()
    (used / "x").write_text("keep", encoding="utf-8")
    result = run_script("throwaway", repo, used)
    assert result.returncode == 1 and (used / "x").read_text(encoding="utf-8") == "keep"

    plain = tmp_path / "plain"
    plain.mkdir()
    result = run_script("throwaway", plain, tmp_path / "c2")
    assert result.returncode == 1 and "Traceback" not in result.stderr
