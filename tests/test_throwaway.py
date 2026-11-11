import os
import shlex
import subprocess
import sys

import pytest
from conftest import SCRIPTS, commit, git, run_script


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


def new_base(repo, tmp_path, name):
    base = tmp_path / f"run {name}" / "base"
    result = run_script("throwaway", repo, base)
    assert result.returncode == 0, result.stderr
    return base


def copy_from(repo, base, tmp_path, name):
    dest = tmp_path / f"run {name}" / "copy"
    return run_script("throwaway", repo, dest, "--base", base), dest


def assert_refused(result, dest, why):
    assert result.returncode == 1 and result.stderr.startswith("error:"), result.stderr
    assert "Traceback" not in result.stderr and why in result.stderr, result.stderr
    assert not dest.exists()


def test_base_refuses_a_change_made_after_it_was_made(make_repo, tmp_path):
    repo = make_repo({"src/a.py": "x = 1\n", ".gitignore": "*.log\n"})
    commit(repo)
    result, dest = copy_from(repo, new_base(repo, tmp_path, "untouched"), tmp_path, "untouched")
    assert result.returncode == 0, result.stderr

    changes = {
        "edit": lambda b: (b / "src" / "a.py").write_text("changed\n", encoding="utf-8"),
        "delete": lambda b: (b / "src" / "a.py").unlink(),
        "untracked": lambda b: (b / "new.txt").write_text("x\n", encoding="utf-8"),
        "ignored": lambda b: (b / "build.log").write_text("x\n", encoding="utf-8"),
        "head": lambda b: commit(b, "moved"),
    }
    for label, change in changes.items():
        base = new_base(repo, tmp_path, label)
        change(base)
        result, dest = copy_from(repo, base, tmp_path, label)
        assert_refused(result, dest, "changed after it was made")


def test_a_base_that_was_dirty_when_made_still_copies(make_repo, tmp_path):
    repo = make_repo({"src/a.py": "x = 1\n"})
    commit(repo)
    (repo / "src" / "a.py").write_text("x = 2\n", encoding="utf-8")
    base = new_base(repo, tmp_path, "dirty")
    result, dest = copy_from(repo, base, tmp_path, "dirty")
    assert result.returncode == 0, result.stderr
    assert (dest / "src" / "a.py").read_text(encoding="utf-8") == "x = 2\n"


def test_a_file_that_was_changed_in_the_base_at_birth_is_sealed_by_content(make_repo, tmp_path):
    repo = make_repo({"src/a.py": "x = 1\n", "src/b.py": "y = 1\n", ".gitignore": "*.log\n"})
    commit(repo)
    (repo / "src" / "a.py").write_text("x = 2\n", encoding="utf-8")
    (repo / "src" / "b.py").unlink()
    (repo / "forced.log").write_text("kept\n", encoding="utf-8")
    git(repo, "add", "-f", "forced.log")
    changes = {
        "edit": lambda b: (b / "src" / "a.py").write_text("x = 3\n", encoding="utf-8"),
        "recreate": lambda b: (b / "src" / "b.py").write_text("y = 2\n", encoding="utf-8"),
        "ignored": lambda b: (b / "forced.log").write_text("changed\n", encoding="utf-8"),
    }
    for label, change in changes.items():
        base = new_base(repo, tmp_path, f"born dirty {label}")
        change(base)
        result, dest = copy_from(repo, base, tmp_path, f"born dirty {label}")
        assert_refused(result, dest, "changed after it was made")


def test_base_refuses_git_text_changed_after_it_was_made(make_repo, tmp_path):
    repo = make_repo({"src/a.py": "x = 1\n"})
    commit(repo)
    ran = tmp_path / "ran by the base"

    def set_config(base, key, value):
        subprocess.run(["git", "config", "-f", str(base / ".git" / "config"), key, value],
                       check=True)

    changes = {
        "hooksPath": lambda b: set_config(b, "core.hooksPath", str(tmp_path / "hooks")),
        "fsmonitor": lambda b: set_config(b, "core.fsmonitor", f"touch {shlex.quote(str(ran))}"),
        "insteadOf": lambda b: set_config(b, "url.https://evil/.insteadOf", "https://github.com/"),
        "hook": lambda b: (b / ".git" / "hooks" / "pre-commit").write_text(
            "#!/bin/sh\n", encoding="utf-8"),
        "exclude": lambda b: (b / ".git" / "info" / "exclude").write_text(
            "secret\n", encoding="utf-8"),
        # A base made before seals existed (v0.5.0) is not trusted either.
        "no seal": lambda b: (b / ".git" / "bug-hunter-seal").unlink(),
    }
    why = {"no seal": "seal", "hooksPath": "core.hookspath", "fsmonitor": "core.fsmonitor"}
    for label, change in changes.items():
        base = new_base(repo, tmp_path, label)
        change(base)
        result, dest = copy_from(repo, base, tmp_path, label)
        assert_refused(result, dest, why.get(label, "changed after it was made"))
    # Refusing must not run the base's own commands: git status would run a planted fsmonitor.
    assert not ran.exists()


def test_a_planted_filter_is_refused_without_running(make_repo, tmp_path):
    repo = make_repo({"src/a.py": "x = 1\n"})
    commit(repo)
    base = new_base(repo, tmp_path, "filter")
    ran = tmp_path / "filter ran"
    subprocess.run(["git", "config", "-f", str(base / ".git" / "config"),
                    "filter.x.clean", f"touch {shlex.quote(str(ran))}; cat"], check=True)
    (base / ".git" / "info" / "attributes").write_text("* filter=x\n", encoding="utf-8")
    (base / "src" / "a.py").touch()
    result, dest = copy_from(repo, base, tmp_path, "filter")
    assert_refused(result, dest, "filter.x.clean")
    assert not ran.exists()


def test_the_files_digest_is_checked_before_git_runs_on_the_base(make_repo, tmp_path,
                                                                  monkeypatch):
    import throwaway

    repo = make_repo({"src/a.py": "x = 1\n"})
    commit(repo)
    base = new_base(repo, tmp_path, "order")
    sealed = (base / ".git" / "bug-hunter-seal").read_text(encoding="utf-8")
    assert throwaway._unchanged(base, sealed)
    (base / ".git" / "info" / "exclude").write_text("changed\n", encoding="utf-8")

    def no_git(*args, **kwargs):
        raise AssertionError("git ran on a base whose .git text had changed")

    monkeypatch.setattr(throwaway, "_git", no_git)
    assert not throwaway._unchanged(base, sealed)


def test_index_flags_that_hide_edits_are_part_of_the_seal(make_repo, tmp_path):
    repo = make_repo({"src/a.py": "x = 1\n"})
    commit(repo)
    for flag in ("--skip-worktree", "--assume-unchanged"):
        base = new_base(repo, tmp_path, flag.strip("-"))
        git(base, "update-index", flag, "src/a.py")
        (base / "src" / "a.py").write_text("hidden edit\n", encoding="utf-8")
        result, dest = copy_from(repo, base, tmp_path, flag.strip("-"))
        assert_refused(result, dest, "changed after it was made")


def test_the_seal_does_not_depend_on_the_callers_git_ignore_files(make_repo, tmp_path):
    repo = make_repo({"src/a.py": "x = 1\n"})
    commit(repo)
    (repo / "x.log").write_text("staged\n", encoding="utf-8")
    git(repo, "add", "x.log")
    ignoring, plain = tmp_path / "cfg a", tmp_path / "cfg b"
    (ignoring / "git").mkdir(parents=True)
    (ignoring / "git" / "ignore").write_text("*.log\n", encoding="utf-8")
    plain.mkdir()
    base = tmp_path / "run home" / "base"
    made = run_script("throwaway", repo, base,
                      env={**os.environ, "XDG_CONFIG_HOME": str(ignoring)})
    assert made.returncode == 0, made.stderr
    dest = tmp_path / "run home" / "copy"
    result = run_script("throwaway", repo, dest, "--base", base,
                        env={**os.environ, "XDG_CONFIG_HOME": str(plain)})
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(os.name == "nt", reason="named pipes are POSIX only")
def test_a_pipe_under_the_base_git_is_refused_not_waited_for(make_repo, tmp_path):
    repo = make_repo({"src/a.py": "x = 1\n"})
    commit(repo)
    base = new_base(repo, tmp_path, "pipe")
    os.mkfifo(base / ".git" / "hooks" / "pipe")
    dest = tmp_path / "run pipe" / "copy"
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "throwaway.py"), str(repo), str(dest), "--base", str(base)],
        capture_output=True, text=True, timeout=60)
    assert_refused(result, dest, "changed after it was made")


def test_refs_named_like_skipped_folders_are_still_sealed(make_repo, tmp_path):
    repo = make_repo({"src/a.py": "x = 1\n"})
    commit(repo)
    git(repo, "checkout", "-q", "-b", "logs/main")
    base = new_base(repo, tmp_path, "logs")
    # Not `git commit`, which also writes COMMIT_EDITMSG and would be caught by that alone.
    other = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-C", str(base), "commit-tree",
         "HEAD^{tree}", "-p", "HEAD", "-m", "x"], capture_output=True, text=True, check=True,
    ).stdout.strip()
    git(base, "update-ref", "refs/heads/logs/main", other)
    result, dest = copy_from(repo, base, tmp_path, "logs")
    assert_refused(result, dest, "changed after it was made")


def test_a_file_that_was_untracked_in_the_base_at_birth_is_sealed_by_content(make_repo,
                                                                             tmp_path):
    repo = make_repo({"src/a.py": "x = 1\n"})
    commit(repo)
    (repo / "n.py").write_text("new = 1\n", encoding="utf-8")
    git(repo, "add", "n.py")
    base = new_base(repo, tmp_path, "untracked")
    result, dest = copy_from(repo, base, tmp_path, "before")
    assert result.returncode == 0, result.stderr
    (base / "n.py").write_text("new = 2\n", encoding="utf-8")
    result, dest = copy_from(repo, base, tmp_path, "after")
    assert_refused(result, dest, "changed after it was made")
