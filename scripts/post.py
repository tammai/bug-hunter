"""File the drafts the owner names as GitHub issues, with their own gh login, each only once."""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from drafts import numbered, problems, title

UNREADABLE = "{} is unreadable; fix or remove it so nothing is filed twice"


def _fail(message: str) -> int:
    print(f"error: {message}", file=sys.stderr)
    return 1


def _record(posted_file: Path, posted: dict[str, str]) -> None:
    # Atomic and synced, so a crash part way never leaves a half-written record behind.
    fd, tmp = tempfile.mkstemp(dir=posted_file.parent, prefix=".posted-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(posted, out, indent=2, sort_keys=True)
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, posted_file)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _writable(directory: Path) -> bool:
    try:
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=".posted-")
    except OSError:
        return False
    os.close(fd)
    os.unlink(tmp)
    return True


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("drafts_dir")
    parser.add_argument("numbers", nargs="+")
    parser.add_argument("--label", required=True)
    args = parser.parse_args(argv)
    drafts_dir = Path(args.drafts_dir)

    if bad := [n for n in args.numbers if not re.fullmatch(r"[0-9]+", n)]:
        return _fail(f"not a draft number: {', '.join(bad)}")
    by_number: dict[int, list[Path]] = {}
    for n, path in numbered(drafts_dir):
        by_number.setdefault(n, []).append(path)
    wanted = list(dict.fromkeys(int(n) for n in args.numbers))
    if missing := [f"{n:02d}" for n in wanted if n not in by_number]:
        return _fail(f"no draft {', '.join(missing)} in {drafts_dir}")
    if clashes := [paths for n in wanted if len(paths := by_number[n]) > 1]:
        names = "; ".join(" and ".join(p.name for p in paths) for paths in clashes)
        return _fail(f"more than one draft has the same number: {names}; rename one")
    chosen = {n: by_number[n][0] for n in wanted}
    broken = [
        f"draft {n:02d}: {p}"
        for n in wanted
        for p in problems(chosen[n].read_text(encoding="utf-8", errors="replace"))
    ]
    if broken:
        return _fail("drafts fail the format check, nothing filed:\n" + "\n".join(broken))

    posted_file = drafts_dir / "posted.json"
    try:
        posted = json.loads(posted_file.read_text(encoding="utf-8")) if posted_file.exists() else {}
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return _fail(UNREADABLE.format(posted_file))
    if not isinstance(posted, dict):
        return _fail(UNREADABLE.format(posted_file))
    if not _writable(drafts_dir):
        return _fail(f"{drafts_dir} isn't writable, so filed drafts couldn't be recorded")

    try:
        auth = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
    except FileNotFoundError:
        return _fail("gh is not installed")
    if auth.returncode != 0:
        return _fail("gh is not logged in; run `gh auth login`, then post again")

    for n in wanted:
        key, path = f"{n:02d}", chosen[n]
        if key in posted:
            print(f"{key}: already filed as {posted[key]}, skipped")
            continue
        result = subprocess.run(
            ["gh", "issue", "create", "--title", title(path), "--body-file", str(path),
             "--label", args.label],
            capture_output=True, text=True, encoding="utf-8",
        )
        if result.returncode != 0:
            reason = (result.stderr.strip().splitlines() or ["no message"])[-1]
            return _fail(f"draft {key} not filed: {reason}. Drafts filed before it are recorded.")
        url = (result.stdout.strip().splitlines() or [""])[-1]
        print(f"{key}: {url}", flush=True)
        posted[key] = url
        try:
            _record(posted_file, posted)
        except OSError as exc:
            return _fail(
                f"draft {key} was filed as {url} but not recorded in {posted_file} ({exc}); "
                f"add it there by hand before posting again"
            )
    return 0


if __name__ == "__main__":
    sys.exit(_main())
