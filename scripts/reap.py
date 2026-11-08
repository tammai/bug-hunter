"""Stop the background processes agents listed in their scratch folders' bg.pids files."""

import argparse
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path


def _listed(scratch: Path) -> list[int]:
    """PIDs listed in <scratch>/bg.pids and <scratch>/*/bg.pids; other lines are skipped."""
    files = [scratch / "bg.pids", *scratch.glob("*/bg.pids")]
    pids = []
    for path in files:
        if path.is_file():
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.strip().isascii() and line.strip().isdigit() and int(line) > 1:
                    pids.append(int(line))
    return sorted(set(pids))


def _tree(roots: list[int]) -> list[int]:
    """The roots and every process under them, deepest first, read before anything is stopped."""
    # `cmd && prog &` backgrounds a subshell: `$!` is the subshell, and prog outlives its kill.
    ps = shutil.which("ps")
    if ps is None:
        raise FileNotFoundError("ps")
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
        except (ProcessLookupError, PermissionError):
            return False
        return True
    # Agents run in Git Bash, so `$!` is an MSYS PID, which only MSYS's own kill can reach.
    kill = shutil.which("kill")
    if kill is None:
        raise FileNotFoundError("kill")
    return subprocess.run([kill, str(pid)], capture_output=True).returncode == 0


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scratch")
    args = parser.parse_args(argv)
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
