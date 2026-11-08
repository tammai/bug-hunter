"""Stop the background processes agents listed in their scratch folders' bg.pids files."""

import argparse
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path

# Above any real PID (Linux tops out at 2**22, Windows below 2**32); longer lines are not PIDs.
MAX_PID = 2**31 - 1


def _pid(text: str) -> int | None:
    text = text.strip()
    if text.isascii() and text.isdigit() and len(text) <= 10 and 1 < int(text) <= MAX_PID:
        return int(text)
    return None


def _listed(scratch: Path) -> list[int]:
    """PIDs listed in <scratch>/bg.pids and <scratch>/*/bg.pids; other lines are skipped."""
    files = [scratch / "bg.pids", *scratch.glob("*/bg.pids")]
    pids = []
    for path in files:
        if path.is_file():
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                if (pid := _pid(line)) is not None:
                    pids.append(pid)
    return sorted(set(pids))


def _tool(name: str) -> str:
    """The path of ps or kill, never one from the current folder (the target repo's root)."""
    # Windows' lookup tries the current folder first unless this is set, so a ps.bat a
    # target commits would run here with the owner's full environment.
    os.environ["NoDefaultCurrentDirectoryInExePath"] = "1"
    found = shutil.which(name)
    if found is None or Path(found).resolve().parent == Path.cwd().resolve():
        raise FileNotFoundError(name)
    return found


def _tree(roots: list[int]) -> list[int]:
    """The roots and every process under them, deepest first, read before anything is stopped."""
    # `cmd && prog &` backgrounds a subshell: `$!` is the subshell, and prog outlives its kill.
    ps = _tool("ps")
    rows = subprocess.run([ps, "-ef"], capture_output=True, text=True, errors="replace").stdout
    children: dict[int, list[int]] = {}
    for cols in (row.split() for row in rows.splitlines()[1:]):
        if len(cols) > 2 and cols[1].isdigit() and cols[2].isdigit():
            children.setdefault(int(cols[2]), []).append(int(cols[1]))
    order, todo = [], list(roots)
    while todo:
        pid = todo.pop()
        if pid not in order:
            order.append(pid)
            todo += children.get(pid, [])
    return order[::-1]


def _stop(pid: int) -> bool:
    if os.name != "nt":
        try:
            os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError, OverflowError):
            return False
        return True
    # Agents run in Git Bash, so `$!` is an MSYS PID, which only MSYS's own kill can reach.
    kill = _tool("kill")
    return subprocess.run([kill, str(pid)], capture_output=True).returncode == 0


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scratch")
    parser.add_argument("--record", nargs="*", metavar="PID",
                        help="append these PIDs and the processes under them to bg.pids")
    args = parser.parse_args(argv)
    if args.record is not None:
        # Run by the isolation prefix's EXIT trap: the tree is read while a backgrounded
        # subshell still lives, so its child is listed even if the agent kills the subshell.
        roots = [pid for pid in map(_pid, args.record) if pid is not None]
        try:
            tree = _tree(roots)
        except FileNotFoundError:
            tree = roots
        with (Path(args.scratch) / "bg.pids").open("a", encoding="utf-8") as out:
            out.writelines(f"{pid}\n" for pid in tree)
        return 0
    try:
        listed = _listed(Path(args.scratch))
        stopped = sum(_stop(pid) for pid in (_tree(listed) if listed else []))
    except FileNotFoundError as exc:
        print(f"error: no {exc.args[0]} command on PATH (run from Git Bash)", file=sys.stderr)
        return 1
    print(f"stopped {stopped} process(es)")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
