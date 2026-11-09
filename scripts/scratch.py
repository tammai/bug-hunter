"""Make, clean up and sweep the temp folders /hunt and /audit run in."""

import argparse
import json
import os
import shutil
import stat
import sys
import tempfile
import time
from pathlib import Path

PREFIX = "bug-hunter-"
MARKER = ".bug-hunter-run"
WINDOWS = os.name == "nt"


def _size(path: Path) -> int:
    """Bytes on disk under path, each hard-linked file once, never following a link."""
    total, seen = 0, set()
    for folder, dirs, files in os.walk(path):
        for name in dirs + files:
            try:
                st = os.lstat(os.path.join(folder, name))
            except OSError:
                continue
            if (st.st_dev, st.st_ino) in seen:
                continue
            seen.add((st.st_dev, st.st_ino))
            total += getattr(st, "st_blocks", 0) * 512 or st.st_size
    return total


def _human(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    value, unit = size / 1024, "KB"
    for bigger in ("MB", "GB"):
        if value < 1024:
            break
        value, unit = value / 1024, bigger
    return f"{value:.1f} {unit}"


def _ago(seconds: float) -> str:
    minutes = int(seconds // 60)
    return f"{minutes} min" if minutes < 120 else f"{minutes // 60} h"


def _run_folder(path: Path) -> str | None:
    """Why path isn't a run folder this script made, or None when it is."""
    # The folder itself first, by lstat: looking inside another user's 0700 run raises.
    try:
        st = path.lstat()
    except OSError:
        return f"{path} doesn't exist or can't be read"
    if stat.S_ISLNK(st.st_mode):
        return f"{path} is a symlink"
    if not stat.S_ISDIR(st.st_mode):
        return f"{path} is not a folder"
    if not path.name.startswith(PREFIX):
        return f"{path} isn't named {PREFIX}*"
    if not WINDOWS and st.st_uid != os.getuid():
        return f"{path} belongs to another user"
    try:
        marker = os.lstat(path / MARKER)
    except OSError:
        return f"{path} has no readable {MARKER} marker, so it wasn't made by scratch.py"
    if not stat.S_ISREG(marker.st_mode):
        return f"{path} has no {MARKER} marker, so it wasn't made by scratch.py"
    return None


def _created(path: Path) -> float | None:
    try:
        created = json.loads((path / MARKER).read_text(encoding="utf-8"))["created"]
    except (OSError, UnicodeDecodeError, ValueError, KeyError, TypeError):
        return None
    return float(created) if isinstance(created, (int, float)) else None


def _clear_read_only(path: str) -> None:
    """Windows refuses to delete a read-only file, such as Go's 0444 module files."""
    try:
        if stat.S_ISREG(os.lstat(path).st_mode):
            os.chmod(path, stat.S_IWRITE)
    except OSError:
        pass


def _unlink(path: str) -> None:
    try:
        os.unlink(path)
    except PermissionError:
        if not WINDOWS:
            raise
        _clear_read_only(path)
        os.unlink(path)


DIR_FLAGS = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)


def _open_dir(name: str, parent: int) -> int:
    """Open a folder inside an open one, refusing a link, and give the owner full access."""
    try:
        fd = os.open(name, DIR_FLAGS, dir_fd=parent)
    except PermissionError:
        # No read permission, such as a hunter's 0o000 input. Through the parent, and a fixed
        # mode, so a link swapped in meanwhile can at worst narrow a folder the owner owns.
        os.chmod(name, stat.S_IRWXU, dir_fd=parent)
        fd = os.open(name, DIR_FLAGS, dir_fd=parent)
    try:
        os.fchmod(fd, stat.S_IRWXU)
    except OSError:
        pass
    return fd


def _is_folder(name: str, fd: int) -> bool:
    try:
        return stat.S_ISDIR(os.stat(name, dir_fd=fd, follow_symlinks=False).st_mode)
    except OSError:
        return False


def _empty_dir(fd: int, shown: str, errors: list[str], skip: tuple = ()) -> None:
    """Remove everything in an open folder, each entry through that folder's handle."""
    # Files go before folders, so a run's top-level files (an audit's fingerprints) are
    # removed whatever fails below them.
    try:
        names = [n for n in os.listdir(fd) if n not in skip]
    except OSError as exc:
        errors.append(f"{shown}: {exc.strerror}")
        return
    folder = {n: _is_folder(n, fd) for n in names}
    for name in sorted(names, key=lambda n: (folder[n], n)):
        full = os.path.join(shown, name)
        try:
            if folder[name]:
                _remove_dir(name, fd, full, errors)
            else:
                os.unlink(name, dir_fd=fd)
        except FileNotFoundError:
            pass
        except OSError as exc:
            errors.append(f"{full}: {exc.strerror}")


def _remove_dir(name: str, parent: int, shown: str, errors: list[str]) -> None:
    try:
        fd = _open_dir(name, parent)
    except OSError:
        # Swapped for a link or a file after it was listed: remove that entry, never what a
        # link names.
        os.unlink(name, dir_fd=parent)
        return
    try:
        _empty_dir(fd, shown, errors)
    finally:
        os.close(fd)
    os.rmdir(name, dir_fd=parent)


def _remove_tree_windows(top: str, errors: list[str]) -> None:
    # shutil.rmtree takes junctions for links and removes them without entering. It works by
    # path, so a folder swapped for a junction while it runs isn't caught (AC-006).
    def retry(func, path, exc) -> None:
        if isinstance(exc, FileNotFoundError):
            return
        if func in (os.unlink, os.rmdir) and isinstance(exc, PermissionError):
            _clear_read_only(path)
            try:
                func(path)
                return
            except OSError as again:
                exc = again
        elif func is os.path.islink and os.path.islink(path):
            try:
                os.unlink(path)
                return
            except OSError as again:
                exc = again
        errors.append(f"{path}: {getattr(exc, 'strerror', None) or exc}")

    shutil.rmtree(top, onexc=retry)


def _is_dir(entry: os.DirEntry) -> bool:
    # A Windows junction looks like a folder but leads out: removed as a link, never entered.
    try:
        return entry.is_dir(follow_symlinks=False) and not entry.is_junction()
    except OSError:
        return False


def _clean_windows(run: Path, keep: str | None, errors: list[str]) -> None:
    try:
        with os.scandir(run) as listing:
            entries = [e for e in listing if e.name not in (MARKER, keep)]
    except OSError as exc:
        errors.append(f"{run}: {exc.strerror}")
        return
    for entry in sorted(entries, key=lambda e: (_is_dir(e), e.name)):
        try:
            if _is_dir(entry):
                _remove_tree_windows(entry.path, errors)
            else:
                _unlink(entry.path)
        except OSError as exc:
            errors.append(f"{entry.path}: {exc.strerror}")


def _clean(run: Path, keep: str | None) -> list[str]:
    """Remove the run; return what couldn't be removed."""
    # Top-level files (an audit's fingerprints) go first, and every entry is tried whatever
    # failed before it. The marker goes last, and only once the rest is gone, so a run left
    # part way by a kill or an error is still found by a later sweep.
    errors: list[str] = []
    if WINDOWS:
        _clean_windows(run, keep, errors)
    else:
        try:
            fd = os.open(run, DIR_FLAGS)
        except OSError as exc:
            return [f"{run}: {exc.strerror}"]
        try:
            _empty_dir(fd, str(run), errors, skip=(MARKER, keep))
            if keep is None and not errors:
                os.unlink(MARKER, dir_fd=fd)
        except OSError as exc:
            errors.append(f"{run / MARKER}: {exc.strerror}")
        finally:
            os.close(fd)
    if keep is None and not errors:
        try:
            if WINDOWS:
                _unlink(str(run / MARKER))
            os.rmdir(run)
        except OSError as exc:
            errors.append(f"{run}: {exc.strerror}")
    return errors


def _new() -> int:
    run = Path(tempfile.mkdtemp(prefix=PREFIX))
    if any(ch.isspace() for ch in str(run)):
        shutil.rmtree(run)
        print(f"error: the temp folder {run.parent} has whitespace, which the agents' "
              "isolation can't carry; set TMPDIR to a folder without spaces", file=sys.stderr)
        return 1
    (run / MARKER).write_text(json.dumps({"created": time.time()}), encoding="utf-8")
    (run / "cache").mkdir()
    print(run)
    return 0


def _clean_run(run: Path, keep: str | None) -> int:
    if keep is not None and (keep in ("", ".", "..", MARKER) or "/" in keep or "\\" in keep):
        print(f"error: --keep takes the name of one entry in the run folder, not {keep!r}",
              file=sys.stderr)
        return 1
    if why := _run_folder(run):
        print(f"error: refusing to clean {run}: {why}", file=sys.stderr)
        return 1
    before = _size(run)
    print(f"cleaning up {run} ({_human(before)})")
    errors = _clean(run, keep)
    after = _size(run) if run.exists() else 0
    # Copy-on-write copies count in full here but share blocks on disk.
    freed = f"up to {_human(before - after)} freed"
    if errors:
        print(f"removed part of {run}: {freed}")
        print(f"error: couldn't remove {len(errors)} entries in {run}, first: {errors[0]}",
              file=sys.stderr)
        return 1
    kept = f", kept {keep}" if keep and (run / keep).exists() else ""
    print(f"removed {run}: {freed}{kept}")
    return 0


def _sweep(hours: float) -> int:
    temp = Path(tempfile.gettempdir())
    now, found = time.time(), False
    for path in sorted(temp.glob(PREFIX + "*")):
        if _run_folder(path):
            continue
        found = True
        created = _created(path)
        try:
            age = now - (created if created is not None else (path / MARKER).lstat().st_mtime)
        except OSError:
            continue
        size = _human(_size(path))
        if age >= hours * 3600:
            if errors := _clean(path, None):
                print(f"couldn't remove all of {path} ({size}): {errors[0]}")
                continue
            print(f"removed {path} ({size}, started {_ago(age)} ago)")
        else:
            print(f"kept {path} ({size}, started {_ago(age)} ago): may be in use by another run")
    if not found:
        print("no leftover runs")
    return 0


def _hours(value: str) -> float:
    try:
        hours = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a number of hours: {value!r}") from None
    if not hours >= 0:
        raise argparse.ArgumentTypeError(f"hours can't be negative: {value!r}")
    return hours


def _main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors=stream.errors)
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("new", help="make a run folder and print its path")
    clean = sub.add_parser("clean", help="remove a run folder and say how much was freed")
    clean.add_argument("run", type=Path)
    clean.add_argument("--keep", help="one entry of the run to keep, such as kept")
    sweep = sub.add_parser("sweep", help="remove run folders left by earlier runs")
    sweep.add_argument("--older-than", type=_hours, default=12.0, metavar="HOURS")
    args = parser.parse_args(argv)
    if args.cmd == "new":
        return _new()
    if args.cmd == "clean":
        return _clean_run(args.run, args.keep)
    return _sweep(args.older_than)


if __name__ == "__main__":
    sys.exit(_main())
