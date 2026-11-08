"""Where a repo's drafts live, the next draft number, and the fixed draft format check."""

import argparse
import html
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

JSON_LETTERS = {'"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f", "n": "\n", "r": "\r",
                "t": "\t"}
JSON_ESCAPE = re.compile(r'\\(u[0-9a-fA-F]{4}|["\\/bfnrt])')
HEX_ESCAPE = re.compile(r"\\x([0-9a-fA-F]{2})")
ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")  # terminal colour and cursor codes
MAX_DECODE_ROUNDS = 8
MAX_SPELLINGS = 256

SECTIONS = ["What happens", "Steps to reproduce", "Expected", "Root cause"]
DRAFT_NAME = re.compile(r"^(\d+)\.md$")
URL_ORIGIN = re.compile(r"^[a-z][a-z0-9+.-]*://(?:[^@/]*@)?([^/:]+)(?::\d+)?/(.+)$", re.I)
SCP_ORIGIN = re.compile(r"^(?:[^@/]*@)?([^/:]+):(?!/)(.+)$")


def _origin_parts(url: str) -> list[str] | None:
    match = URL_ORIGIN.match(url) or SCP_ORIGIN.match(url)
    if not match:
        return None
    path = match[2].rstrip("/").removesuffix(".git")
    return [match[1], *path.split("/")]


def drafts_dir(repo: str) -> Path:
    """The repo's drafts folder, outside the repo so hunting leaves nothing in it."""
    result = subprocess.run(
        ["git", "-C", repo, "remote", "get-url", "origin"],
        capture_output=True, text=True, encoding="utf-8",
    )
    parts = _origin_parts(result.stdout.strip()) if result.returncode == 0 else None
    if parts is None:
        parts = ["local", Path(repo).resolve().name]
    # One folder level per URL part, so acme-web/api and acme/web-api never share a folder;
    # a "." or ".." part would climb out of ~/.bug-hunter.
    if any(part in ("", ".", "..") for part in parts):
        raise ValueError(f"origin URL can't name a drafts folder: {result.stdout.strip()}")
    return Path.home().joinpath(".bug-hunter", *parts, "drafts")


def numbered(directory: Path) -> list[tuple[int, Path]]:
    """The `NN.md` drafts in a folder, in numeric order; other files are ignored."""
    if not directory.is_dir():
        return []
    found = [(int(m[1]), p) for p in directory.iterdir() if (m := DRAFT_NAME.match(p.name))]
    return sorted(found)


def title(path: Path) -> str | None:
    """A draft's `# ` title, or None when it has none."""
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip():
            return (line[2:].strip() or None) if line.startswith("# ") else None
    return None


FENCE = re.compile(r" {0,3}(`{3,}|~{3,})(.*)")


def fenced(lines: list[str]):
    """Each line with whether it is part of a code block (its fence lines included)."""
    # CommonMark's rules: a Python traceback's indented `~~~~^^^^` caret line is plain text.
    opener = None
    for line in lines:
        match = FENCE.match(line)
        if opener is None:
            if match and not (match[1][0] == "`" and "`" in match[2]):
                opener = match[1]
            yield line, opener is not None
        else:
            if (match and match[1][0] == opener[0] and len(match[1]) >= len(opener)
                    and not match[2].strip()):
                opener = None
            yield line, True


def problems(text: str) -> list[str]:
    """Every way a draft breaks the fixed format; empty when it's good."""
    lines = text.splitlines()
    found = []
    first = next((line for line in lines if line.strip()), "")
    if not first.startswith("# "):
        found.append("missing a '# ' title line")
    elif not first[2:].strip():
        found.append("empty title after '# '")

    bodies: dict[str, list[str]] = {}
    current = None
    for line, in_fence in fenced(lines):
        if line.startswith("## ") and not in_fence:
            current = line[3:].strip().rstrip(":").casefold()
            bodies.setdefault(current, [])
        elif current is not None:
            bodies[current].append(line)

    order = [s for s in bodies if s in {r.casefold() for r in SECTIONS}]
    for section in SECTIONS:
        key = section.casefold()
        if key not in bodies:
            found.append(f"missing section: ## {section}")
        elif not any(line.strip() for line in bodies[key]):
            found.append(f"empty section: ## {section}")
    if order != [s.casefold() for s in SECTIONS if s.casefold() in bodies]:
        found.append("sections out of order: want " + " · ".join(SECTIONS))

    steps = bodies.get("steps to reproduce", [])
    if steps and not any(in_fence for _, in_fence in fenced(steps)):
        found.append("## Steps to reproduce has no code block with the actual output")
    return found


def _home_problems(text: str) -> list[str]:
    """The owner's home folder in a draft: it names their account in a public issue."""
    home = Path.home().as_posix().rstrip("/").lower()
    forms = {home, home.replace("/", "\\"), home.replace("/", "\\\\")}
    if home[1:2] == ":":
        forms.add("/" + home[0] + home[2:])  # Git Bash: C:/Users/x -> /c/Users/x
    lowered = text.lower()
    if len(home) > 3 and any(form in lowered for form in forms):
        return ["contains your home folder's path, which names your account"]
    return []


def _live_problems(text: str, target: dict, variable: str = "BASE",
                   replay: bool = False) -> list[str]:
    """Ways a live draft would leak the target's host or a login into a public issue."""
    found = leaks(text, target, variable, replay)
    setup = next((line for line in text.splitlines()
                  if line.strip().lower().startswith("set before running:")), None)
    if setup is None or not re.search(rf"\b{variable}\b", setup):
        found.append(f"missing a 'Set before running:' line naming {variable}")
    return found


def leaks(text: str, target: dict, variable: str = "BASE", replay: bool = False) -> list[str]:
    """The target's host, the proxy's account header or a login in `text`, never echoed."""
    # An HTTP-replay draft (a reference run) logs in through ACCEPT_ACCOUNT_<NAME>, not curl.
    def login(name: str) -> str:
        return f"ACCEPT_ACCOUNT_{name}" if replay else f'-H "${name}_AUTH"'
    from live_proxy import LOCAL_HOSTS, _secrets  # live_proxy imports this module

    found = []
    # Every check runs on every decoded spelling, so no encoding layer hides a value.
    spellings = _spellings(text)
    patterns = _host_patterns(urlsplit(target["url"]), LOCAL_HOSTS)
    if any(re.search(p, t, re.I) for p in patterns for t in spellings):
        whose = "target's" if variable == "BASE" else "reference's"
        found.append(f"names the {whose} host: write \"${variable}\" instead")
    if any("x-bug-hunter-account" in t.lower() for t in spellings):
        found.append(f"writes the proxy's account header: write {login('<ACCOUNT>')} instead")
    for name, headers in target["accounts"].items():
        # Every form the proxy masks: as sent, JSON-escaped, percent-encoded, HTML entities and
        # a Basic login decoded; pieces under 6 characters would match ordinary words.
        forms = _secrets({"url": target["url"], "accounts": {name: headers}})
        if any(form in t for form in forms for t in spellings):
            found.append(f"holds a login value of account {name}: "
                         f"write {login(name.upper())} instead")
    return found


def _spellings(text: str) -> set[str]:
    """`text` and what it decodes to (JSON escapes, HTML entities, %xx), to any depth."""
    found = frontier = {text}
    # Each decoding is applied again to what it gave until nothing new comes out; bounded,
    # since every round can triple the set.
    for _ in range(MAX_DECODE_ROUNDS):
        frontier = {d for t in frontier
                    for d in (unquote(t), html.unescape(t), _json_unescaped(t),
                              HEX_ESCAPE.sub(lambda m: chr(int(m[1], 16)), t),
                              ANSI.sub("", t))} - found
        if not frontier or len(found) > MAX_SPELLINGS:
            break
        found = found | frontier
    return found


def _json_unescaped(text: str) -> str:
    # One left-to-right pass, as a JSON parser reads a string: `\\n` is a backslash then n.
    return JSON_ESCAPE.sub(lambda m: chr(int(m[1][1:], 16)) if m[1][0] == "u"
                           else JSON_LETTERS[m[1]], text)


def _host_patterns(url, local_hosts: set[str]) -> list[str]:
    """Where `url`'s host names the target in decoded text."""
    # No left boundary anywhere: whatever stands before a host (an undecoded escape, `_`, a
    # letter of another script) must never hide it; over-refusing is the safe side. A right
    # boundary only after a digit, so a longer port or address (the proxy's own listener at
    # 127.0.0.1:50003, 10.0.0.12) isn't the target.
    host, port = (url.hostname or "").lower(), url.port
    scheme = r"[a-z][a-z0-9+.-]*://(?:[^\s/@]*@)?"  # a URL's host position, with any user@
    if host in local_hosts:
        # Any loopback spelling with exactly the target's port; a bare "localhost" gives
        # nothing away.
        alias = r"(?:localhost|127\.0\.0\.1|\[::1\]|::1)"
        if port:
            return [rf"{alias}:{port}(?!\d)"]
        return [rf"{scheme}{alias}(?![\w.-]|:\d)"]
    if "." in host or ":" in host:  # a domain, IPv4 or IPv6: anywhere, subdomains included
        tail = r"(?![0-9a-f])" if ":" in host else r"(?!\d)" if host[-1].isdigit() else ""
        return [re.escape(host) + tail]
    # A plain name ("ref") only after a scheme (and any user@) or with its port: elsewhere
    # every draft's own words ($REF_BASE, "reference", a /ref or //ref path, an @ref
    # decorator, qa@ref.com) would match. Known limit: a protocol-relative //ref is missed.
    name = re.escape(host)
    found = [rf"{scheme}{name}(?![\w-]|\.\w)"]
    if port:
        found.append(rf"{name}:{port}(?!\d)")
    return found


def expected_body(text: str) -> str:
    """The text of a draft's `## Expected` section."""
    expected, current = [], None
    for line, in_fence in fenced(text.splitlines()):
        if line.startswith("## ") and not in_fence:
            current = line[3:].strip().rstrip(":").casefold()
        elif current == "expected":
            expected.append(line)
    return "\n".join(expected)


def oracle_problems(text: str, spec: Path) -> list[str]:
    """Ways a draft's Expected fails to rest on the spec: an unknown criterion or rule, or none."""
    from oracle import (  # oracle imports scope
        CRITERION,
        domain_headings,
        is_spec_gap,
        load_lock,
        rule_citations,
    )

    known = {c["id"] for c in load_lock(spec)}
    body = expected_body(text)
    found = []
    ids = CRITERION.findall(body)
    if set(ids) - known:
        found.append("Expected cites a criterion that isn't in criteria.lock.json: "
                     + ", ".join(sorted(set(ids) - known)))
    rules, unknown = rule_citations(body, domain_headings(spec))
    if unknown:
        found.append("Expected cites a domain.md § that isn't a section of domain.md")
    if not is_spec_gap(text) and not (set(ids) & known or rules):
        found.append("Expected cites no criterion or domain.md rule (if none covers it, put "
                     "'Oracle: spec-gap' under the title)")
    return found


def _main(argv: list[str] | None = None) -> int:
    # Windows Python before 3.15 writes in the ANSI code page; the commands read UTF-8.
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors=stream.errors)
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("dir", help="print the repo's drafts folder").add_argument("repo")
    sub.add_parser("next", help="print the next free draft number").add_argument("dir")
    check = sub.add_parser("check", help="check a draft's format")
    check.add_argument("file")
    check.add_argument("--repo", help="with --target: the repo whose targets.json to read")
    check.add_argument("--target", help="a live draft: hide this target's host and logins")
    check.add_argument("--reference", help="also hide this reference's host and logins")
    check.add_argument("--oracle", type=Path, help="the spec folder Expected must cite")
    args = parser.parse_args(argv)
    if getattr(args, "reference", None) and not args.target:
        print("error: --reference needs --target", file=sys.stderr)
        return 1

    if args.command == "dir":
        try:
            print(drafts_dir(args.repo))
        except FileNotFoundError:
            print("error: git is not installed", file=sys.stderr)
            return 1
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        return 0
    if args.command == "next":
        drafts = numbered(Path(args.dir))
        print(f"{(drafts[-1][0] if drafts else 0) + 1:02d}")
        return 0
    try:
        text = Path(args.file).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"error: cannot read {args.file}: {exc}", file=sys.stderr)
        return 1
    found = problems(text) + _home_problems(text)
    if args.oracle:
        from oracle import BadOracle

        try:
            found += oracle_problems(text, args.oracle)
        except BadOracle as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
    if args.target:
        from live_proxy import BadTarget, load_target  # live_proxy imports this module

        try:
            replay = bool(args.reference)
            found += _live_problems(text, load_target(args.repo or ".", args.target),
                                    replay=replay)
            if args.reference:
                found += _live_problems(text, load_target(args.repo or ".", args.reference),
                                        "REF_BASE", replay)
        except BadTarget as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
    for problem in dict.fromkeys(found):
        print(problem)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(_main())
