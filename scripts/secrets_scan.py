"""Find secrets committed to a repo (and local .env files), reporting where, never what."""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

RULES = json.loads((Path(__file__).resolve().parent / "secret_patterns.json").read_text("utf-8"))
PATTERNS = [
    {**p, "compiled": re.compile(p["regex"], re.I | re.M)} for p in RULES["patterns"]
]


def _git_names(repo: str, *args: str) -> list[str] | None:
    result = subprocess.run(["git", "-C", repo, "ls-files", "-z", *args], capture_output=True)
    if result.returncode != 0:
        return None
    names = []
    for raw in result.stdout.split(b"\0"):
        try:
            names.append(raw.decode("utf-8"))
        except UnicodeDecodeError:
            continue
    return [n for n in names if n]


def _is_env(name: str) -> bool:
    return name.startswith(".env") and name not in (".env.example", ".env.sample")


def _text(path: Path) -> str | None:
    """A regular, small, UTF-8 text file's contents; None for anything to skip."""
    if path.is_symlink() or not path.is_file() or path.stat().st_size > RULES["max_bytes"]:
        return None
    data = path.read_bytes()
    if b"\0" in data[:8192]:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _severity(pattern: dict, rel: PurePosixPath, matched: str, committed: bool) -> str:
    placeholder = any(p in matched.lower() for p in RULES["placeholders"])
    in_tests = any(part in RULES["low_dirs"] for part in rel.parts[:-1])
    return "low" if placeholder or in_tests or not committed else pattern["severity"]


def _scan_file(repo: Path, name: str, committed: bool) -> list[dict]:
    rel = PurePosixPath(name)
    if any(part in RULES["skip_dirs"] for part in rel.parts[:-1]):
        return []
    text = _text(repo / name)
    if text is None:
        return []
    found = []
    for number, line in enumerate(text.splitlines(), 1):
        for pattern in PATTERNS:
            if pattern.get("env_only") and not _is_env(rel.name):
                continue
            match = pattern["compiled"].search(line)
            if not match:
                continue
            value = match.groupdict().get("value") or match.group(0)
            if value.startswith("$"):
                continue
            # Only where and how long: the value, or any slice of it, is never output.
            found.append({
                "path": name, "line": number, "pattern": pattern["name"], "length": len(value),
                "committed": committed,
                "severity": _severity(pattern, rel, match.group(0), committed),
            })
            break
    return found


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo")
    args = parser.parse_args(argv)
    try:
        tracked = _git_names(args.repo)
        ignored = _git_names(args.repo, "--others", "--ignored", "--exclude-standard")
        untracked = _git_names(args.repo, "--others", "--exclude-standard")
    except FileNotFoundError:
        print("error: git is not installed", file=sys.stderr)
        return 1
    if tracked is None or ignored is None or untracked is None:
        print(f"error: not a git repo: {args.repo}", file=sys.stderr)
        return 1

    repo = Path(args.repo)
    local_env = sorted({n for n in ignored + untracked if _is_env(PurePosixPath(n).name)})
    found = [f for n in tracked for f in _scan_file(repo, n, committed=True)]
    found += [f for n in local_env for f in _scan_file(repo, n, committed=False)]
    found.sort(key=lambda f: (f["path"], f["line"]))
    print(json.dumps(found, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(_main())
