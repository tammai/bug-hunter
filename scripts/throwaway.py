"""Make a throwaway copy of a repo that nothing run inside it can reach back out of."""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def _git(*args: str, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "--no-optional-locks", *args], capture_output=True, **kwargs)


def _escaping_links(root: Path) -> list[str]:
    """Symlinks under root, outside .git, that point outside it."""
    found = []
    for folder, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if not (folder == str(root) and d == ".git")]
        for name in dirs + files:
            link = Path(folder) / name
            if link.is_symlink() and not link.resolve().is_relative_to(root.resolve()):
                found.append(link.relative_to(root).as_posix())
    return sorted(found)


def _make(repo: Path, dest: Path) -> str | None:
    """Copy repo to dest; returns the reason when it can't be done safely."""
    if dest.exists() and (not dest.is_dir() or any(dest.iterdir())):
        return f"{dest} already exists and isn't empty"
    top = _git("-C", str(repo), "rev-parse", "--show-toplevel", text=True, encoding="utf-8")
    if top.returncode != 0:
        return f"not a git repo: {repo}"
    repo = Path(top.stdout.strip()).resolve()
    if dest.resolve().is_relative_to(repo):
        return f"{dest} is inside the repo; the copy must go outside it"

    # A clone, not cp -R: a worktree's .git file, a .venv's absolute paths and other untracked
    # environments would all point back into the real repo.
    dest.parent.mkdir(parents=True, exist_ok=True)
    clone = _git("clone", "--quiet", "--no-local", "--no-hardlinks", "--", str(repo), str(dest))
    if clone.returncode != 0:
        return f"git clone failed: {clone.stderr.decode(errors='replace').strip()}"
    # Without this, a repro's `git push` would write into the real repo.
    if _git("-C", str(dest), "remote", "remove", "origin").returncode != 0:
        shutil.rmtree(dest)
        return "couldn't remove the copy's origin remote, which points at the real repo"

    # Pinned options, since the owner's diff config (noprefix, color, external tools) would
    # otherwise give a patch that git apply can't read.
    diff = _git(
        "-C", str(repo), "diff", "HEAD", "--binary", "--no-ext-diff", "--no-textconv",
        "--no-color", "--src-prefix=a/", "--dst-prefix=b/",
    )
    if diff.returncode != 0:
        shutil.rmtree(dest)
        return "couldn't read the repo's uncommitted changes"
    if diff.stdout:
        applied = _git("-C", str(dest), "apply", "--whitespace=nowarn", input=diff.stdout)
        if applied.returncode != 0:
            shutil.rmtree(dest)
            return "couldn't apply the repo's uncommitted changes to the copy"

    if links := _escaping_links(dest):
        shutil.rmtree(dest)
        return "symlinks point outside the copy, so code run in it could change files there: " + (
            ", ".join(links)
        )
    return None


def _main(argv: list[str] | None = None) -> int:
    # Windows Python before 3.15 writes in the ANSI code page; the commands read UTF-8.
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors=stream.errors)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo")
    parser.add_argument("dest")
    args = parser.parse_args(argv)
    try:
        why = _make(Path(args.repo), Path(args.dest))
    except FileNotFoundError:
        why = "git is not installed"
    if why:
        print(f"error: {why}", file=sys.stderr)
        return 1
    print(Path(args.dest).resolve())
    return 0


if __name__ == "__main__":
    sys.exit(_main())
