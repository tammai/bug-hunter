import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


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


def run_script(name: str, *args, cwd=None, env=None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / f"{name}.py"), *map(str, args)],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
