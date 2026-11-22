import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


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
            path.write_text(text, encoding="utf-8")
        if files:
            git(repo, "add", "-A")
        if origin:
            git(repo, "remote", "add", "origin", origin)
        return repo

    return make


FAKE_GH = """#!{python}
import json, os, sys
args = sys.argv[1:]
with open(os.environ["FAKE_GH_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps(args) + "\\n")
if args[:2] == ["auth", "status"]:
    sys.exit(int(os.environ.get("FAKE_GH_AUTH_EXIT", "0")))
if args[:2] == ["issue", "list"]:
    if os.environ.get("FAKE_GH_LIST_EXIT", "0") != "0":
        print("HTTP 401: Bad credentials", file=sys.stderr)
        sys.exit(1)
    print(os.environ.get("FAKE_GH_LIST", "[]"))
    sys.exit(0)
if args[:2] == ["issue", "create"]:
    counter = os.environ["FAKE_GH_LOG"] + ".n"
    n = int(open(counter).read()) + 1 if os.path.exists(counter) else 1
    if str(n) == os.environ.get("FAKE_GH_FAIL_AT"):
        print("GraphQL: could not create issue", file=sys.stderr)
        sys.exit(1)
    open(counter, "w").write(str(n))
    if os.environ.get("FAKE_GH_CHMOD_DIR"):
        os.chmod(os.environ["FAKE_GH_CHMOD_DIR"], 0o555)
    print(f"https://github.com/o/r/issues/{{n}}")
    sys.exit(0)
sys.exit(3)
"""


@pytest.fixture
def fake_gh(tmp_path):
    """An env whose PATH has a fake `gh` that logs each call; returns (env, calls())."""
    bin_dir = tmp_path / "fake bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(FAKE_GH.format(python=sys.executable), encoding="utf-8")
    gh.chmod(0o755)
    log = tmp_path / "gh-calls.log"
    env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}
    env["FAKE_GH_LOG"] = str(log)
    env["HOME"] = str(tmp_path / "home")

    def calls() -> list[list[str]]:
        if not log.exists():
            return []
        return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]

    return env, calls


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
