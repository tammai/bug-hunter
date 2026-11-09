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


MARKER = "bug-hunter-base"


def _git_links(root: Path) -> list[str]:
    found = []
    for folder, dirs, files in os.walk(root / ".git"):
        for name in dirs + files:
            if (Path(folder) / name).is_symlink():
                found.append((Path(folder) / name).relative_to(root).as_posix())
    return sorted(found)


def _make(repo: Path, dest: Path, base: Path | None = None) -> str | None:
    """Copy repo to dest; returns the reason when it can't be done safely."""
    if dest.exists() and (not dest.is_dir() or any(dest.iterdir())):
        return f"{dest} already exists and isn't empty"
    top = _git("-C", str(repo), "rev-parse", "--show-toplevel", text=True, encoding="utf-8")
    if top.returncode != 0:
        return f"not a git repo: {repo}"
    repo = Path(top.stdout.strip()).resolve()
    if dest.resolve().is_relative_to(repo):
        return f"{dest} is inside the repo; the copy must go outside it"
    if base is not None:
        return _copy_base(repo, base, dest)

    # A clone, not cp -R: a worktree's .git file, a .venv's absolute paths and other untracked
    # environments would all point back into the real repo. One commit is enough to run the
    # code, and history is most of a large repo's size.
    dest.parent.mkdir(parents=True, exist_ok=True)
    clone = _git("clone", "--quiet", "--no-local", "--no-hardlinks", "--depth", "1", "--",
                 str(repo), str(dest))
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

    if why := _refuse_escaping_links(dest):
        return why
    (dest / ".git" / MARKER).write_text(str(repo), encoding="utf-8")
    return None


def _refuse_escaping_links(dest: Path) -> str | None:
    if links := _escaping_links(dest):
        shutil.rmtree(dest)
        return "symlinks point outside the copy, so code run in it could change files there: " + (
            ", ".join(links)
        )
    return None


def _git_points_out(git_dir: Path) -> str | None:
    """Why git run in a copy of this .git would read or write another repo, or None."""
    # A clone writes none of these; each sends git, and a repro's commits, outside the copy.
    if (git_dir / "objects" / "info" / "alternates").exists():
        return ".git/objects/info/alternates borrows objects from another repo"
    if (git_dir / "commondir").exists():
        return ".git/commondir shares another repo's .git"
    try:
        found = subprocess.run(
            ["git", "config", "--file", str(git_dir / "config"), "--name-only", "--get-regexp",
             r"^(core\.worktree|include\.path|includeif\..*\.path)$"],
            capture_output=True, text=True)
    except OSError:
        return ".git/config can't be read"
    if found.returncode not in (0, 1):
        return ".git/config can't be read"
    if names := found.stdout.split():
        return ".git/config sets " + ", ".join(names) + ", which point outside the copy"
    return None


def _copy_base(repo: Path, base: Path, dest: Path) -> str | None:
    """Copy a base this script made from repo, sharing disk blocks where the filesystem can."""
    marker = base / ".git" / MARKER
    if base.is_symlink() or (base / ".git").is_symlink() or marker.is_symlink():
        return f"{base} is a symlink or holds one at .git; not a base this script made"
    try:
        made_for = marker.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return f"{base} is not a base made by throwaway.py"
    if made_for != str(repo):
        return f"{base} was made for another repo, not {repo}"
    if links := _escaping_links(base):
        return "symlinks point outside the base, so code run in a copy could change files " \
            "there: " + ", ".join(links)
    # git never makes links in .git, and the clone made none, so any there was planted later:
    # .git/config or a hook linked to the owner's files would be written or run by a repro.
    if git_links := _git_links(base):
        return "symlinks in the base's .git, which git never makes: " + ", ".join(git_links)
    if why := _git_points_out(base / ".git"):
        return f"the base's {why}"

    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.rmdir()
    # Copy-on-write: APFS clonefile on macOS, reflinks on btrfs and XFS. Never hardlinks, which
    # would let a write in one copy change the others.
    if sys.platform == "darwin":
        clone = ["cp", "-c", "-R", str(base), str(dest)]
    elif sys.platform.startswith("linux"):
        clone = ["cp", "-R", "--reflink=auto", "--no-dereference", str(base), str(dest)]
    else:
        clone = None
    try:
        copied = bool(clone) and subprocess.run(clone, capture_output=True).returncode == 0
    except OSError:
        copied = False
    if not copied:
        shutil.rmtree(dest, ignore_errors=True)
        shutil.copytree(base, dest, symlinks=True)
    if _git_links(dest) or _git_points_out(dest / ".git"):
        shutil.rmtree(dest)
        return "the copy's .git changed while copying to reach outside the copy"
    return _refuse_escaping_links(dest)


def _main(argv: list[str] | None = None) -> int:
    # Windows Python before 3.15 writes in the ANSI code page; the commands read UTF-8.
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors=stream.errors)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo")
    parser.add_argument("dest")
    parser.add_argument("--base", type=Path,
                        help="copy this run's base clone of repo instead of cloning again")
    args = parser.parse_args(argv)
    try:
        why = _make(Path(args.repo), Path(args.dest), args.base)
    except FileNotFoundError:
        why = "git is not installed"
    except OSError as exc:
        shutil.rmtree(args.dest, ignore_errors=True)
        why = f"couldn't copy: {exc}"
    if why:
        print(f"error: {why}", file=sys.stderr)
        return 1
    print(Path(args.dest).resolve())
    return 0


if __name__ == "__main__":
    sys.exit(_main())
