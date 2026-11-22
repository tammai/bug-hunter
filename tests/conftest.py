import json
import os
import shutil
import stat
import subprocess
import sys
import sysconfig
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
WINDOWS = os.name == "nt"
# Add file and add subfolder only: denying all of (W) also denies SYNCHRONIZE, which breaks
# listing the folder.
EVERYONE_NO_NEW_ENTRIES = "*S-1-1-0:(WD,AD)"


@pytest.fixture(autouse=True, scope="session")
def no_real_gh(tmp_path_factory):
    """Keep the owner's real, logged-in gh out of every test's reach.

    Where the fake gh can't run (Windows can't exec a shebang script), the scripts under test
    would find the real gh on PATH and file real issues. Every test builds its environment
    from os.environ, so cleaning it here covers them all.
    """
    with pytest.MonkeyPatch.context() as mp:
        # Set, not unset: with no token in the environment gh falls back to a login stored in
        # Windows Credential Manager or the macOS Keychain.
        for name in ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN",
                     "GITHUB_ENTERPRISE_TOKEN"):
            mp.setenv(name, "test-no-token")
        mp.setenv("GH_CONFIG_DIR", str(tmp_path_factory.mktemp("no-gh-config")))
        mp.setenv("GH_PROMPT_DISABLED", "1")
        mp.setenv("PATH", gh_free_path(os.environ.get("PATH", ""),
                                       tmp_path_factory.mktemp("gh-free-path")))
        yield


def gh_free_path(path: str, shims: Path) -> str:
    """PATH with no real gh on it, keeping the other tools that share a folder with one."""
    kept = []
    for n, folder in enumerate(path.split(os.pathsep)):
        if not (folder and shutil.which("gh", path=folder)):
            kept.append(folder)
        elif os.name == "nt":
            # Symlinks need privilege there, so the folder goes, unless it also holds git;
            # the placeholder tokens then make any reached gh fail its login.
            if shutil.which("git", path=folder):
                kept.append(folder)
        else:
            # A folder of links to everything but gh, in the folder's place, so Homebrew's
            # other tools stay on PATH in the same order.
            shim = shims / str(n)
            shim.mkdir(parents=True)
            # Absolute, or links from a relative entry (node_modules/.bin) would dangle.
            for entry in os.scandir(os.path.abspath(folder)):
                if entry.name != "gh":
                    os.symlink(entry.path, shim / entry.name)
            # Another spelling (GH on a case-insensitive volume) would still be found.
            assert not shutil.which("gh", path=str(shim)), f"gh still reachable via {folder}"
            kept.append(str(shim))
    return os.pathsep.join(kept)


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def make_repo(tmp_path):
    """A real git repo with the given files staged, at a path with a space and non-ASCII."""

    def make(files: dict[str, str], origin: str | None = None) -> Path:
        repo = tmp_path / "my repö"
        repo.mkdir()
        git(repo, "init", "-q")
        for name, text in files.items():
            path = repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            # Bytes: text mode on Windows turns each \n into \r\n, and \r\n into \r\r\n.
            path.write_bytes(text.encode("utf-8"))
        if files:
            git(repo, "add", "-A")
        if origin:
            git(repo, "remote", "add", "origin", origin)
        return repo

    return make


FAKE_GH = """import json, os, subprocess, sys


def main(args):
    with open(os.environ["FAKE_GH_LOG"], "a", encoding="utf-8") as log:
        log.write(json.dumps(args) + "\\n")
    if args[:2] == ["auth", "status"]:
        return int(os.environ.get("FAKE_GH_AUTH_EXIT", "0"))
    if args[:2] == ["issue", "list"]:
        if os.environ.get("FAKE_GH_LIST_EXIT", "0") != "0":
            print("HTTP 401: Bad credentials", file=sys.stderr)
            return 1
        print(os.environ.get("FAKE_GH_LIST", "[]"))
        return 0
    if args[:2] == ["issue", "create"]:
        counter = os.environ["FAKE_GH_LOG"] + ".n"
        n = int(open(counter).read()) + 1 if os.path.exists(counter) else 1
        if str(n) == os.environ.get("FAKE_GH_FAIL_AT"):
            print("GraphQL: could not create issue", file=sys.stderr)
            return 1
        open(counter, "w").write(str(n))
        if folder := os.environ.get("FAKE_GH_CHMOD_DIR"):
            if os.name == "nt":
                subprocess.run(["icacls", folder, "/deny", "@DENY@"], check=True,
                               capture_output=True)
            else:
                os.chmod(folder, 0o555)
        print(f"https://github.com/o/r/issues/{n}")
        return 0
    return 3


# site imports this before Python looks for a script: only the interpreter run under the
# name gh is the fake, and it must exit before Python tries to open "issue" as one.
if os.path.splitext(os.path.basename(sys.orig_argv[0]))[0].lower() == "gh":
    code = main(sys.orig_argv[1:])
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)
""".replace("@DENY@", EVERYONE_NO_NEW_ENTRIES)


def build_fake_gh(root: Path) -> Path:
    """Python itself as gh (a link, or on Windows a copy), in a venv that runs FAKE_GH at startup.

    Windows finds only gh.exe, and a gh.cmd would pass titles through cmd.exe. The returned
    PATH folder holds no python, so a script's own `python3` never reaches the fake.
    """
    paths = {"base": str(root), "platbase": str(root)}
    scripts = Path(sysconfig.get_path("scripts", "venv", paths))
    site = Path(sysconfig.get_path("purelib", "venv", paths))
    scripts.mkdir(parents=True)
    site.mkdir(parents=True)
    base = Path(sys._base_executable)
    (root / "pyvenv.cfg").write_text(
        f"home = {base.parent}\ninclude-system-site-packages = false\n", encoding="utf-8")
    if WINDOWS:
        shutil.copy2(base, scripts / "gh.exe")
        for dll in base.parent.glob("*.dll"):
            shutil.copy2(dll, scripts)
    else:
        os.symlink(base, scripts / "gh")
    (site / "fake_gh.py").write_text(FAKE_GH, encoding="utf-8")
    (site / "fake_gh.pth").write_text("import fake_gh\n", encoding="utf-8")
    return scripts


@pytest.fixture
def fake_gh(tmp_path):
    """An env whose PATH has a fake `gh` that logs each call; returns (env, calls())."""
    bin_dir = build_fake_gh(tmp_path / "fake gh")
    log = tmp_path / "gh-calls.log"
    env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}
    env["FAKE_GH_LOG"] = str(log)
    # Path.home() reads USERPROFILE on Windows.
    env["HOME"] = env["USERPROFILE"] = str(tmp_path / "home")

    def calls() -> list[list[str]]:
        if not log.exists():
            return []
        return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]

    return env, calls


def lock_dir(path: Path) -> None:
    """Make a folder refuse new entries; Windows ignores chmod on folders, so a deny ACL."""
    if WINDOWS:
        subprocess.run(["icacls", str(path), "/deny", EVERYONE_NO_NEW_ENTRIES], check=True,
                       capture_output=True)
    else:
        path.chmod(0o555)


def unlock_dir(path: Path) -> None:
    if WINDOWS:
        subprocess.run(["icacls", str(path), "/remove:d", "*S-1-1-0"], check=True,
                       capture_output=True)
    else:
        path.chmod(0o755)


def mode_is(path: Path, mode: int) -> bool:
    """POSIX permission bits equal mode; Windows has none (os.chmod only sets read-only)."""
    return WINDOWS or stat.S_IMODE(path.stat().st_mode) == mode


def rmtree(path: Path) -> None:
    """shutil.rmtree that also removes read-only entries, such as git's objects on Windows."""

    def make_writable(func, failed, _exc):
        os.chmod(os.path.dirname(failed), stat.S_IRWXU)
        os.chmod(failed, stat.S_IRWXU)
        func(failed)

    shutil.rmtree(path, onexc=make_writable)


def skip_unless_git_keeps_symlinks(probe: Path) -> None:
    """Skip unless a symlink can be made, committed and cloned back as a link."""
    repo = probe / "repo"
    repo.mkdir(parents=True)
    git(repo, "init", "-q")
    try:
        os.symlink("target", repo / "link")
    except OSError:
        pytest.skip("can't create symlinks here: Windows needs Developer Mode or admin")
    git(repo, "add", "-A")
    commit(repo)
    git(probe, "clone", "-q", "--no-local", str(repo), "clone")
    if not (probe / "clone" / "link").is_symlink():
        pytest.skip("git checks committed symlinks out as plain files here (core.symlinks=false)")


def commit(repo: Path, message: str = "init") -> None:
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty",
        "-m", message)


def run_script(name: str, *args, cwd=None, env=None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / f"{name}.py"), *map(str, args)],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
