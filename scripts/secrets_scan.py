"""Find secrets committed to a repo (and local .env files), reporting where, never what."""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

RULES = json.loads((Path(__file__).resolve().parent / "secret_patterns.json").read_text("utf-8"))
PATTERNS = [
    {**p, "compiled": re.compile(p["regex"], re.M | (re.I if p.get("ignore_case", True) else 0))}
    for p in RULES["patterns"]
]
# A reference to another variable or a template slot, not a value.
REFERENCE = re.compile(r"\$\{[^}]*\}|\$\([^)]*\)|\$[A-Za-z_]\w*")
SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def is_placeholder(value: str) -> bool:
    """A value that is a stand-in as a whole; a partly redacted value still counts as real."""
    lowered = value.lower()
    if re.fullmatch(r"<[^<>]*>", lowered) or REFERENCE.fullmatch(value):
        return True
    if "<" in lowered or ">" in lowered:
        return False
    return any(word in lowered for word in RULES["placeholders"])


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
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > RULES["max_bytes"]:
            return None
        data = path.read_bytes()
    except OSError:
        return None
    if b"\0" in data[:8192]:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _severity(pattern: dict, rel: PurePosixPath, value: str, committed: bool) -> str:
    in_tests = any(part in RULES["low_dirs"] for part in rel.parts[:-1])
    return "low" if is_placeholder(value) or in_tests or not committed else pattern["severity"]


def _scan_file(repo: Path, name: str, committed: bool) -> list[dict]:
    rel = PurePosixPath(name)
    if any(part in RULES["skip_dirs"] for part in rel.parts[:-1]):
        return []
    text = _text(repo / name)
    if text is None:
        return []
    found = []
    for number, line in enumerate(text.splitlines(), 1):
        hits = []
        for order, pattern in enumerate(PATTERNS):
            if pattern.get("env_only") and not _is_env(rel.name):
                continue
            for match in pattern["compiled"].finditer(line):
                value = match.groupdict().get("value") or match.group(0)
                if REFERENCE.fullmatch(value):
                    continue
                severity = _severity(pattern, rel, value, committed)
                hits.append((SEVERITY_RANK[severity], order, pattern["name"], len(value),
                             severity))
        if hits:
            # One finding per line, the most severe: a placeholder first on a minified line
            # mustn't hide a real key after it.
            _, _, pattern_name, length, severity = min(hits)
            # Only where and how long: the value, or any slice of it, is never output.
            found.append({"path": str(rel), "line": number, "pattern": pattern_name,
                          "length": length, "committed": committed, "severity": severity})
    return found


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo")
    args = parser.parse_args(argv)
    try:
        tracked = _git_names(args.repo)
        ignored = _git_names(args.repo, "--others", "--ignored", "--exclude-standard",
                             "--directory")
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
