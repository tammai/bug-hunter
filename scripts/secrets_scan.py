"""Find secrets committed to a repo (and local .env files), reporting where, never what."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath

RULES = json.loads(
    (Path(__file__).resolve().parent / "secret_patterns.json").read_text(encoding="utf-8")
)
PATTERNS = [
    {**p, "compiled": re.compile(p["regex"], re.M | (re.I if p.get("ignore_case", True) else 0))}
    for p in RULES["patterns"]
]
# A reference to another variable or a template slot, not a value.
REFERENCE = re.compile(r"\$\{[^}]*\}|\$\([^)]*\)|\$[A-Za-z_]\w*")
SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}


PLACEHOLDER_WORDS = "|".join(map(re.escape, RULES["placeholders"]))


def is_placeholder(value: str) -> bool:
    """A value that is a stand-in as a whole; anything partly real counts as real."""
    if REFERENCE.fullmatch(value) or re.fullmatch(r"<[^<>]*>", value):
        return True
    if value.startswith("<") and ">" not in value:
        return True  # `<your api key>` cut at its first space
    if "<" in value or ">" in value:
        return False
    if re.fullmatch(rf"{RULES['key_prefix']}?[xX*#•]{{3,}}", value):
        return True  # masking alone, or after a known key prefix: sk-xxxx, AKIAXXXX
    lowered = value.lower()
    return bool(
        re.fullmatch(rf"(?:{PLACEHOLDER_WORDS})(?:[-_][a-z]+)*", lowered)
        or re.fullmatch(rf"[a-z]+(?:[-_][a-z]+)*[-_](?:{PLACEHOLDER_WORDS})", lowered)
        or re.fullmatch(r"your[-_][a-z_-]*", lowered)
    )


def counts(pattern: dict, value: str) -> bool:
    """Whether a pattern's match is a value worth reporting, not a reference or stand-in."""
    if REFERENCE.fullmatch(value):
        return False
    if pattern.get("needs_mix") and not (re.search(r"[A-Za-z]", value)
                                         and re.search(r"\d", value)):
        return False
    return True


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def windows(text: str) -> list[str]:
    """The 8-character slices fingerprinted and checked; single-case words are left out
    because ordinary prose is full of them."""
    return [
        text[i : i + 8] for i in range(len(text) - 7)
        if not (text[i : i + 8].isalpha()
                and (text[i : i + 8].islower() or text[i : i + 8].isupper()))
    ]


def fingerprints(values: list[str]) -> dict:
    """Hashes of each secret and of its slices, so findings can be checked without the values."""
    return {
        "tokens": sorted({_digest(v) for v in values}),
        "windows": sorted({_digest(w) for v in values for w in windows(v)}),
    }


def known_secret_in(text: str, prints: dict) -> bool:
    tokens = set(prints.get("tokens", []))
    slices = set(prints.get("windows", []))
    if any(_digest(t) in tokens for t in re.split(r"[\s'\"=:,;|`()\[\]{}<>]+", text) if t):
        return True
    return any(_digest(w) in slices for w in windows(text))


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


def _scan_file(repo: Path, name: str, committed: bool,
               values: list[str] | None = None) -> list[dict]:
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
                if not counts(pattern, value):
                    continue
                if values is not None and not is_placeholder(value):
                    values.append(value)
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
    parser.add_argument("--fingerprints", help="also write hashes of the found values here")
    args = parser.parse_args(argv)
    try:
        tracked = _git_names(args.repo)
        ignored = _git_names(args.repo, "--others", "--ignored", "--exclude-standard",
                             "--directory")
        untracked = _git_names(args.repo, "--others", "--exclude-standard")
        # --directory collapses an ignored folder to one entry; this finds .env files in it.
        ignored_env = _git_names(
            args.repo, "--others", "--ignored", "--exclude-standard", "--", ":(glob)**/.env*",
            *(f":(exclude,glob)**/{d}/**" for d in RULES["skip_dirs"]),
        )
    except FileNotFoundError:
        print("error: git is not installed", file=sys.stderr)
        return 1
    if tracked is None or ignored is None or untracked is None or ignored_env is None:
        print(f"error: not a git repo: {args.repo}", file=sys.stderr)
        return 1

    repo = Path(args.repo)
    local_env = sorted({
        n for n in ignored + untracked + ignored_env if _is_env(PurePosixPath(n).name)
    })
    values: list[str] = []
    found = [f for n in tracked for f in _scan_file(repo, n, True, values)]
    found += [f for n in local_env for f in _scan_file(repo, n, False, values)]
    if args.fingerprints:
        out = Path(args.fingerprints)
        fd, tmp = tempfile.mkstemp(dir=out.parent, prefix=".fingerprints-")
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(fingerprints(values), handle)
        os.replace(tmp, out)
    found.sort(key=lambda f: (f["path"], f["line"]))
    print(json.dumps(found, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(_main())
