"""Make a throwaway copy of a repo that nothing run inside it can reach back out of."""

import argparse
import hashlib
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

# What `git rev-parse --local-env-vars` lists: set inside a hook or alias of another repo, these
# would send every command (the clone, the origin removal, the patch) to that repo instead.
_REPO_VARS = {
    "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_CONFIG", "GIT_CONFIG_PARAMETERS", "GIT_CONFIG_COUNT",
    "GIT_OBJECT_DIRECTORY", "GIT_DIR", "GIT_WORK_TREE", "GIT_IMPLICIT_WORK_TREE",
    "GIT_GRAFT_FILE", "GIT_INDEX_FILE", "GIT_NO_REPLACE_OBJECTS", "GIT_REPLACE_REF_BASE",
    "GIT_PREFIX", "GIT_SHALLOW_FILE", "GIT_COMMON_DIR",
}


def _git(*args: str, **kwargs) -> subprocess.CompletedProcess:
    # A hunter replacing its copy calls this from inside the folder it just deleted; git and
    # the shell it starts fail without a current folder, and every call names its repo anyway.
    kwargs.setdefault("cwd", tempfile.gettempdir())
    kwargs.setdefault("env", {k: v for k, v in os.environ.items()
                              if k.upper() not in _REPO_VARS})
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
SEAL = "bug-hunter-seal"
# Git's own bookkeeping, at the top of .git, that changes without anyone changing the code,
# and the two files that hold what is being compared.
_UNSEALED = {"index", MARKER, SEAL}
_BIG = {"objects", "logs"}


_READ_ONLY = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0) | \
    getattr(os, "O_BINARY", 0)


def _hash_entry(digest, name: bytes, path: Path) -> bool:
    """Add a path's name, type, mode and contents to digest; False for a pipe or device."""
    # Every field is fixed-size or length-prefixed, so no bytes can move from one entry into
    # the next, and a file and a link holding the same bytes hash apart.
    info = os.lstat(path)
    if stat.S_ISLNK(info.st_mode):
        kind, body = b"L", hashlib.sha256(os.fsencode(os.readlink(path))).digest()
    elif stat.S_ISREG(info.st_mode):
        # No-follow and non-blocking: a pipe or link swapped in after the lstat is not read.
        with os.fdopen(os.open(path, _READ_ONLY), "rb") as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                return False
            body = hashlib.file_digest(handle, "sha256").digest()
        kind = b"F"
    elif stat.S_ISDIR(info.st_mode):
        # A folder's contents are the tree walk's; here it only has to differ from a file.
        kind, body = b"T", b""
    else:
        return False
    digest.update(len(name).to_bytes(4, "big") + name + kind
                  + stat.S_IMODE(info.st_mode).to_bytes(2, "big") + body)
    return True


def _seal_files(root: Path) -> str | None:
    """A hash of every small file under root/.git: config, HEAD, hooks, refs, info."""
    # Not the objects: reading the whole repo for every copy would cost what copy-on-write
    # saves. Pure Python on purpose: this runs before any git command, so a base whose config
    # was changed is refused without running what it names (fsmonitor, a filter).
    digest = hashlib.sha256()
    git_dir = root / ".git"
    try:
        for folder, dirs, files in os.walk(git_dir):
            top = Path(folder) == git_dir
            dirs[:] = sorted(d for d in dirs if not (top and d in _BIG))
            for name in sorted(files):
                path = Path(folder) / name
                if name.endswith(".lock") or (top and name in _UNSEALED):
                    continue
                # git never makes a link, pipe or device here, and a pipe would block the read.
                if not stat.S_ISREG(os.lstat(path).st_mode) or not _hash_entry(
                        digest, os.fsencode(path.relative_to(git_dir).as_posix()), path):
                    return None
    # ValueError: a name the filesystem encoding can't hold.
    except (OSError, ValueError):
        return None
    return digest.hexdigest()


def _seal_tree(root: Path) -> str | None:
    """A hash of every entry in root's working tree: name, type, mode, and a file's size and
    modification time."""
    # Status hides what git doesn't track (a .git below the top, a pipe, an empty folder, a
    # submodule's files), so the tree is walked here. Contents are left to status, which
    # names the paths worth reading. Pure Python, like _seal_files, so it runs before git.
    digest = hashlib.sha256()
    try:
        for folder, dirs, files in os.walk(root):
            if folder == str(root):
                dirs[:] = [d for d in dirs if d != ".git"]
            dirs.sort()
            for name in sorted(dirs + files):
                # Any spelling a case-insensitive filesystem treats as .git is a repo git would
                # enter from there, with its own config and hooks.
                if name.lower() == ".git":
                    return None
                path = Path(folder) / name
                info = os.lstat(path)
                mode = stat.S_IMODE(info.st_mode).to_bytes(2, "big")
                if stat.S_ISDIR(info.st_mode):
                    record = b"T" + mode
                elif stat.S_ISLNK(info.st_mode):
                    record = b"L" + mode + hashlib.sha256(os.fsencode(os.readlink(path))).digest()
                elif stat.S_ISREG(info.st_mode):
                    record = b"F" + mode + info.st_size.to_bytes(8, "big") \
                        + info.st_mtime_ns.to_bytes(9, "big", signed=True)
                else:
                    return None
                rel = os.fsencode(path.relative_to(root).as_posix())
                digest.update(len(rel).to_bytes(4, "big") + rel + record)
    except (OSError, ValueError):
        return None
    return digest.hexdigest()


def _pinned(root: Path) -> tuple[list[str], dict[str, str]]:
    """Git options and environment for reading a base's state, whatever the caller's config."""
    # The caller differs between the orchestrator and an agent (HOME is moved): its global
    # ignore and attributes files, and the commands config can name, must not change the answer.
    # Its GIT_* variables too: set inside a hook or alias, they move the index, the repo or
    # the config git reads.
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    env |= {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    options = ["-c", "core.fsmonitor=false", "-c", "core.untrackedCache=false",
               "-c", f"core.excludesFile={os.devnull}", "-c", f"core.attributesFile={os.devnull}",
               "-c", "status.showUntrackedFiles=all", "-C", str(root)]
    return options, env


def _status_paths(status: bytes) -> list[bytes]:
    """Every path in `git status --porcelain=v1 -z` output, ignored ones included."""
    # Ignored too: a file the owner force-added but didn't commit lands in the base ignored.
    paths, entries = [], iter(status.split(b"\0"))
    for entry in entries:
        if len(entry) < 4:
            continue
        code = entry[:2]
        paths.append(entry[3:])
        # A rename or copy is followed by its source path, which is not a separate entry.
        if b"R" in code or b"C" in code:
            next(entries, None)
    return paths


def _seal_git(root: Path) -> tuple[str, str] | None:
    """Hashes of git's view of the tree (status and index flags) and of each listed path."""
    # Only run once _seal_files matched, so .git/config is still the clone's own.
    options, env = _pinned(root)
    status = _git(*options, "status", "--porcelain=v1", "-z", "--ignored",
                  "--ignore-submodules=all", env=env)
    # skip-worktree and assume-unchanged hide edits from status, so their flags are sealed.
    flags = _git(*options, "ls-files", "-v", "-z", env=env)
    if status.returncode != 0 or flags.returncode != 0:
        return None
    # Status names a path, not what it holds: a file already changed or untracked when the base
    # was made (the owner's uncommitted changes) could be edited again and still give the same
    # status. So each path it lists is sealed by content.
    contents = hashlib.sha256()
    try:
        for name in sorted(_status_paths(status.stdout)):
            path = root / os.fsdecode(name)
            try:
                if not _hash_entry(contents, name, path):
                    return None
            except (FileNotFoundError, NotADirectoryError):
                # Deleted, or a folder on its way was replaced by a file.
                contents.update(len(name).to_bytes(4, "big") + name + b"D")
    # ValueError: a name Windows can't decode.
    except (OSError, ValueError):
        return None
    return (hashlib.sha256(status.stdout + b"\0" + flags.stdout).hexdigest(),
            contents.hexdigest())


def _seal(root: Path) -> str | None:
    files = _seal_files(root)
    tree = _seal_tree(root) if files is not None else None
    view = _seal_git(root) if tree is not None else None
    return None if view is None else "\n".join((files, tree, *view))


def _unchanged(base: Path, sealed: str) -> bool:
    """Whether base still matches its seal, looking at its files first and git only after."""
    parts = (sealed.strip().split("\n") + ["", "", ""])[:4]
    if _seal_files(base) != parts[0] or _seal_tree(base) != parts[1]:
        return False
    view = _seal_git(base)
    return view is not None and list(view) == parts[2:]


def _git_links(root: Path) -> list[str]:
    found = []
    for folder, dirs, files in os.walk(root / ".git"):
        for name in dirs + files:
            if (Path(folder) / name).is_symlink():
                found.append((Path(folder) / name).relative_to(root).as_posix())
    return sorted(found)


def _line_endings() -> list[str]:
    """The caller's core.autocrlf and core.eol as `git clone --config` options."""
    # The clone checks out with them (Git for Windows' system autocrlf), but the seal reads the
    # base with system and global config pinned off: unless the clone's own config holds them,
    # every text file reads as changed. Typed as git reads them (a bare key, 2, input).
    options = []
    raw = _git("config", "--get", "core.autocrlf", text=True, encoding="utf-8")
    if raw.returncode == 0:
        value = raw.stdout.strip().lower()
        if value != "input":
            typed = _git("config", "--type=bool", "--get", "core.autocrlf", text=True,
                         encoding="utf-8")
            value = typed.stdout.strip() if typed.returncode == 0 else ""
        if value in ("true", "false", "input"):
            options += ["--config", f"core.autocrlf={value}"]
    eol = _git("config", "--get", "core.eol", text=True, encoding="utf-8")
    if eol.returncode == 0 and (value := eol.stdout.strip().lower()) in ("lf", "crlf", "native"):
        options += ["--config", f"core.eol={value}"]
    return options


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
    clone = _git("clone", *_line_endings(), "--quiet", "--no-local", "--no-hardlinks",
                 "--depth", "1", "--", str(repo), str(dest))
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
    sealed = _seal(dest)
    if sealed is None:
        shutil.rmtree(dest)
        return "couldn't read the copy's .git and status to seal it"
    (dest / ".git" / SEAL).write_text(sealed, encoding="utf-8")
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
             r"^(core\.worktree|core\.fsmonitor|core\.hookspath|include\.path|includeif\..*\.path"
             r"|filter\..*\.(clean|smudge|process)|diff\..*\.(textconv|command))$"],
            capture_output=True, text=True, cwd=tempfile.gettempdir())
    except OSError:
        return ".git/config can't be read"
    if found.returncode not in (0, 1):
        return ".git/config can't be read"
    if names := found.stdout.split():
        return ".git/config sets " + ", ".join(names) + ", which name a command or a " \
            "path outside the copy"
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
    # Anything else a repro changed since the base was made: a hook, a config value, a file.
    try:
        sealed = (base / ".git" / SEAL).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return f"{base} has no seal, so it wasn't made by this version of throwaway.py; " \
            "make a new base"
    changed = f"{base} changed after it was made, so a copy could run code the hunt didn't " \
        "start with; make a new base"
    if not _unchanged(base, sealed):
        return changed

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
    if not _unchanged(base, sealed):
        shutil.rmtree(dest)
        return changed
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
        # Absolute before git runs elsewhere (_git); an absolute path never reads the cwd.
        base = args.base.absolute() if args.base else None
        repo, dest = Path(args.repo).absolute(), Path(args.dest).absolute()
    except FileNotFoundError:
        print("error: the current folder no longer exists, so relative paths can't be "
              "resolved; give absolute ones", file=sys.stderr)
        return 1
    try:
        why = _make(repo, dest, base)
    except FileNotFoundError:
        why = "git is not installed"
    except OSError as exc:
        shutil.rmtree(dest, ignore_errors=True)
        why = f"couldn't copy: {exc}"
    if why:
        print(f"error: {why}", file=sys.stderr)
        return 1
    print(dest.resolve())
    return 0


if __name__ == "__main__":
    sys.exit(_main())
