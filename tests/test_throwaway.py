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


def test_copy_ignores_the_owners_diff_config(make_repo, tmp_path):
    repo = make_repo({"src/a.py": "x = 1\n"})
    commit(repo)
    (repo / "src" / "a.py").write_text("x = 2\n", encoding="utf-8")
    config = tmp_path / "owner gitconfig"
    config.write_text(
        "[diff]\n\tnoprefix = true\n\tmnemonicPrefix = true\n[color]\n\tdiff = always\n"
        "\tui = always\n",
        encoding="utf-8",
    )
    env = {**os.environ, "GIT_CONFIG_GLOBAL": str(config)}
    dest = tmp_path / "copy"
    result = run_script("throwaway", repo, dest, env=env)
    assert result.returncode == 0, result.stderr
    assert (dest / "src" / "a.py").read_text(encoding="utf-8") == "x = 2\n"


def test_refuses_a_dest_inside_the_repo(make_repo):
    repo = make_repo({"a.py": ""})
    commit(repo)
    result = run_script("throwaway", repo, repo / "scratch" / "copy")
    assert result.returncode == 1 and "inside" in result.stderr
    assert not (repo / "scratch").exists()


def test_copy_is_shallow_and_keeps_uncommitted_changes(make_repo, tmp_path):
    repo = make_repo({"a.py": "x = 1\n"})
    commit(repo)
    (repo / "a.py").write_text("x = 2\n", encoding="utf-8")
    git(repo, "add", "-A")
    commit(repo, "second")
    (repo / "a.py").write_text("x = 3\n", encoding="utf-8")

    dest = tmp_path / "run ü" / "copy"
    result = run_script("throwaway", repo, dest)
    assert result.returncode == 0, result.stderr
    count = subprocess.run(["git", "-C", dest, "rev-list", "--count", "HEAD"],
                           capture_output=True, text=True, check=True).stdout.strip()
    assert count == "1"
    assert (dest / "a.py").read_text(encoding="utf-8") == "x = 3\n"


def make_base(make_repo, tmp_path):
    repo = make_repo({"src/a.py": "x = 1\n"})
    os.symlink("a.py", repo / "src" / "inside.py")
    git(repo, "add", "-A")
    commit(repo)
    base = tmp_path / "run ü" / "base"
    result = run_script("throwaway", repo, base)
    assert result.returncode == 0, result.stderr
    return repo, base


def test_copy_from_a_base_is_independent_and_checked(make_repo, tmp_path):
    repo, base = make_base(make_repo, tmp_path)
    dest = tmp_path / "run ü" / "hunter-1" / "copy"
    result = run_script("throwaway", repo, dest, "--base", base)
    assert result.returncode == 0, result.stderr
    assert (dest / "src" / "a.py").read_text(encoding="utf-8") == "x = 1\n"
    assert (dest / "src" / "inside.py").is_symlink()
    (dest / "src" / "a.py").write_text("changed\n", encoding="utf-8")
    commit(dest, "inside the copy")
    assert (base / "src" / "a.py").read_text(encoding="utf-8") == "x = 1\n"
    remotes = subprocess.run(["git", "-C", dest, "remote"], capture_output=True, text=True)
    assert remotes.returncode == 0 and remotes.stdout.strip() == ""

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    git(elsewhere, "init", "-q")
    commit(elsewhere)
    plain = tmp_path / "plain clone"
    git(tmp_path, "clone", "-q", str(repo), str(plain))
    foreign = tmp_path / "foreign base"
    assert run_script("throwaway", elsewhere, foreign).returncode == 0

    for bad in (tmp_path / "missing", plain, foreign):
        target = tmp_path / f"copy of {bad.name}"
        result = run_script("throwaway", repo, target, "--base", bad)
        assert result.returncode == 1, bad
        assert result.stderr.startswith("error:") and "Traceback" not in result.stderr, bad
        assert not target.exists(), bad

    os.symlink(str(tmp_path), base / "escape")
    target = tmp_path / "copy after escape"
    result = run_script("throwaway", repo, target, "--base", base)
    assert result.returncode == 1 and "escape" in result.stderr
    assert not target.exists()


def test_copy_from_a_base_falls_back_when_cp_fails(make_repo, tmp_path):
    repo, base = make_base(make_repo, tmp_path)
    bin_dir = tmp_path / "fake bin"
    bin_dir.mkdir()
    fake = bin_dir / "cp"
    fake.write_text("#!/bin/sh\necho 'cp: clone not supported' >&2\nexit 1\n", encoding="utf-8")
    fake.chmod(0o755)
    env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}
    dest = tmp_path / "run ü" / "hunter-2" / "copy"
    result = run_script("throwaway", repo, dest, "--base", base, env=env)
    assert result.returncode == 0, result.stderr
    assert (dest / "src" / "a.py").read_text(encoding="utf-8") == "x = 1\n"
    assert (dest / "src" / "inside.py").is_symlink()
    assert subprocess.run(["git", "-C", dest, "status", "--porcelain"], capture_output=True,
                          text=True, check=True).stdout == ""


def test_a_base_with_links_or_alternates_in_git_is_refused(make_repo, tmp_path):
    repo, base = make_base(make_repo, tmp_path)
    config = base / ".git" / "config"
    saved = config.read_text(encoding="utf-8")
    config.unlink()
    os.symlink(str(tmp_path / "owner gitconfig"), config)
    dest = tmp_path / "copy 1"
    result = run_script("throwaway", repo, dest, "--base", base)
    assert result.returncode == 1 and "config" in result.stderr and not dest.exists()

    config.unlink()
    config.write_text(saved, encoding="utf-8")
    alternates = base / ".git" / "objects" / "info" / "alternates"
    alternates.parent.mkdir(parents=True, exist_ok=True)
    alternates.write_text(str(repo / ".git" / "objects") + "\n", encoding="utf-8")
    dest = tmp_path / "copy 2"
    result = run_script("throwaway", repo, dest, "--base", base)
    assert result.returncode == 1 and "alternates" in result.stderr and not dest.exists()

    alternates.unlink()
    for name, setup in (
            ("commondir", lambda git: (git / "commondir").write_text(str(repo / ".git"))),
            ("worktree", lambda git: subprocess.run(
                ["git", "config", "-f", str(git / "config"), "core.worktree", str(repo)],
                check=True)),
            ("include", lambda git: subprocess.run(
                ["git", "config", "-f", str(git / "config"), "include.path",
                 str(tmp_path / "owner gitconfig")], check=True))):
        config.write_text(saved, encoding="utf-8")
        (base / ".git" / "commondir").unlink(missing_ok=True)
        setup(base / ".git")
        dest = tmp_path / f"copy {name}"
        result = run_script("throwaway", repo, dest, "--base", base)
        assert result.returncode == 1 and name in result.stderr, (name, result.stderr)
        assert not dest.exists(), name
