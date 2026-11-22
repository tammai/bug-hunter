"""Find secrets committed to a repo (and local .env files), reporting where, never what."""

import argparse
import hashlib
import hmac
import json
import os
import re
import stat
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
    prefix = RULES["key_prefix"]
    mask = r"(?:[xX*#•]{3,}|\.{3,}|…+)"
    # Masking alone, or after a key prefix and its version word: sk-xxxx, sk-ant-api03-...
    if re.fullmatch(rf"{prefix}?(?:[a-z]+\d*[-_])?{mask}", value):
        return True
    if re.fullmatch(rf"{prefix}(?:[a-z]+\d*[-_])+", value):
        return True  # the prefix alone, as docs write it: sk-ant-api03-
    lowered = value.lower()
    return bool(
        re.fullmatch(rf"(?:{PLACEHOLDER_WORDS})(?:[-_][a-z]+)*", lowered)
        or re.fullmatch(rf"[a-z]+(?:[-_][a-z]+)*[-_](?:{PLACEHOLDER_WORDS})", lowered)
        or re.fullmatch(r"your[-_][a-z_-]*", lowered)
    )


KEY_LINE = re.compile(r"""\s*["']?([A-Za-z0-9+/]{16,}={0,2})(?:\\n)?["']?\s*[+,;]?\s*""")
TRIVIAL = {"true", "false", "yes", "no", "on", "off", "null", "none"}


def counts(pattern: dict, value: str) -> bool:
    """Whether a pattern's match is a value worth reporting, not a reference or stand-in."""
    if REFERENCE.fullmatch(value) or value.isdigit() or value.lower() in TRIVIAL:
        return False
    if len(value) < 4:
        return False
    if pattern.get("needs_mix") and not (re.search(r"[A-Za-z]", value)
                                         and re.search(r"\d", value)):
        return False
    if pattern.get("not_url") and (_looks_like_path(value) or re.search(r":[a-z]", value)):
        return False  # a URL, a path or a namespaced key like users:v2
    return True


def _looks_like_path(value: str) -> bool:
    """A URL or a lowercase file path; base64 can start with / too, so case matters here."""
    return "://" in value or bool(
        re.fullmatch(r"(?:/[a-z0-9._-]+)+/?", value)
        or re.fullmatch(r"[a-z0-9._-]+(?:/[a-z0-9._-]+)+\.[a-z0-9]{1,5}", value)
    )


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _single_case(text: str) -> bool:
    return text.isalpha() and (text.islower() or text.isupper())


def windows(text: str, size: int = 8) -> list[str]:
    """Slices of one size; at 8, single-case words are left out because prose is full of them."""
    slices = [text[i : i + size] for i in range(len(text) - size + 1)]
    return [w for w in slices if size != 8 or not _single_case(w)]


def _fingerprintable(value: str) -> bool:
    """Worth fingerprinting: long enough, and not a word or setting that prose also uses."""
    if len(value) < 6 or value.isdigit() or value.lower() in TRIVIAL:
        return False
    if _looks_like_path(value):
        return False
    words = re.fullmatch(r"[A-Za-z]+(?:[-_.][A-Za-z]+)*", value)
    return not (words and sum(c.isalpha() for c in value) < 12)


def fingerprints(values: list[str]) -> dict:
    """Hashes of each secret, its 8-character slices and its 12-character single-case slices,
    so findings can be checked without the values themselves."""
    kept = [v for v in values if _fingerprintable(v)]
    return {
        "lengths": sorted({len(v) for v in kept}),
        "values": sorted({_digest(v) for v in kept}),
        "windows": sorted({_digest(w) for v in kept for w in windows(v)}),
        "long_windows": sorted({_digest(w) for v in kept for w in windows(v, 12)
                                if _single_case(w)}),
    }


def load_prints(data: object) -> dict:
    """Fingerprints as sets, checked for shape once."""
    if not isinstance(data, dict):
        raise ValueError("fingerprints must be a JSON object")
    lengths = data.get("lengths")
    if not isinstance(lengths, list) or not all(isinstance(n, int) for n in lengths):
        raise ValueError("fingerprints need a lengths list of numbers")
    loaded: dict = {"lengths": lengths}
    for key in ("values", "windows", "long_windows"):
        items = data.get(key)
        if not isinstance(items, list):
            raise ValueError(f"fingerprints need a {key} list")
        loaded[key] = {str(i) for i in items}
    return loaded


def known_secret_in(text: str, prints: dict) -> bool:
    """Whether text holds a known secret anywhere, or one of its fingerprinted slices."""
    for length in prints["lengths"]:
        if any(_digest(text[i : i + length]) in prints["values"]
               for i in range(len(text) - length + 1)):
            return True
    if any(_digest(w) in prints["windows"] for w in windows(text)):
        return True
    return any(_digest(w) in prints["long_windows"] for w in windows(text, 12)
               if _single_case(w))


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
    in_key = False
    for number, line in enumerate(text.splitlines(), 1):
        if in_key:
            # A key's body is the secret, not just its BEGIN header. Body lines may be bare
            # or quoted and joined in code ("...\n" +); legacy encrypted keys put headers
            # and a blank line first. Anything else ends the body and is scanned normally.
            body = KEY_LINE.fullmatch(line)
            if body:
                if values is not None:
                    values.append(body[1])
                continue
            if not line.strip() or re.match(r"\s*(?:Proc-Type|DEK-Info):", line):
                continue
            in_key = False
            if "-----END" in line:
                continue
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
                if pattern["name"] == "private-key":
                    rest = line[match.end():].split("-----END")[0]
                    if values is not None:
                        # A one-line key (GCP JSON, .env) holds its body after the header,
                        # with literal \n escapes between the base64 lines.
                        values += re.findall(r"[A-Za-z0-9+/]{16,}={0,2}",
                                             rest.replace("\\n", "\n"))
                    in_key = "-----END" not in line[match.end():]
                severity = _severity(pattern, rel, value, committed)
                hits.append((SEVERITY_RANK[severity], order, pattern["name"], len(value),
                             severity, value))
        if hits:
            # One finding per line, the most severe: a placeholder first on a minified line
            # mustn't hide a real key after it.
            _, _, pattern_name, length, severity, value = min(hits)
            # Only where and how long: the value, or any slice of it, is never output; _main
            # turns it into a keyed id and drops it.
            found.append({"path": str(rel), "line": number, "pattern": pattern_name,
                          "length": length, "committed": committed, "severity": severity,
                          "value": value})
    return found


def _read_key(path: Path) -> bytes:
    """An existing key: a plain file only the owner can read, never through a link."""
    st = os.lstat(path)
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
        raise ValueError(f"{path} is a link or not a plain file; refusing it")
    if os.name != "nt" and st.st_mode & 0o077:
        raise ValueError(f"{path} isn't private (mode {stat.S_IMODE(st.st_mode):o}); "
                         "make it chmod 600")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0))
    with os.fdopen(fd, "rb") as handle:
        key = handle.read()
    if len(key) < 32:
        raise ValueError(f"{path} holds {len(key)} bytes, fewer than a 32-byte key")
    return key


def _id_key(path: Path) -> bytes:
    """The owner's random key for secret ids, made on first use with mode 0600."""
    try:
        return _read_key(path)
    except FileNotFoundError:
        pass
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    # Written whole under a temp name, then linked in: a kill mid-write never leaves a short
    # key, and of two first runs the second reads the key the first linked.
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".secret-id-")
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(os.urandom(32))
            out.flush()
            os.fsync(out.fileno())
        try:
            os.link(tmp, path)
        except FileExistsError:
            pass
    finally:
        Path(tmp).unlink(missing_ok=True)
    return _read_key(path)


def _secret_id(key: bytes, value: str) -> str:
    # Keyed, so the id tells two runs' secrets apart without a hash anyone could test guesses
    # against: without the key, which never leaves the owner's folder, it says nothing.
    return hmac.new(key, value.encode("utf-8", "surrogatepass"), hashlib.sha256).hexdigest()[:16]


def _main(argv: list[str] | None = None) -> int:
    # Windows Python before 3.15 writes in the ANSI code page; the commands read UTF-8.
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors=stream.errors)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo")
    parser.add_argument("--fingerprints", help="also write hashes of the found values here")
    parser.add_argument("--id-key", help="give each finding an id keyed with this file's key "
                                         "(made if missing), stable across runs")
    args = parser.parse_args(argv)
    try:
        key = _id_key(Path(args.id_key)) if args.id_key else None
    except (OSError, ValueError) as exc:
        print(f"error: can't use the id key: {exc}", file=sys.stderr)
        return 1
    try:
        tracked = _git_names(args.repo)
        ignored = _git_names(args.repo, "--others", "--ignored", "--exclude-standard",
                             "--directory")
        untracked = _git_names(args.repo, "--others", "--exclude-standard")
        # --directory collapses an ignored folder to one entry; this finds .env files in it.
        ignored_env = _git_names(
            args.repo, "--others", "--ignored", "--exclude-standard", "--", ":(glob)**/.env*",
            *(f":(exclude,glob)**/{d}/**"
              for d in RULES["skip_dirs"] + RULES["env_glob_excludes"]),
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
    for item in found:
        value = item.pop("value")
        if key is not None:
            item["id"] = _secret_id(key, value)
    found.sort(key=lambda f: (f["path"], f["line"]))
    print(json.dumps(found, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(_main())
