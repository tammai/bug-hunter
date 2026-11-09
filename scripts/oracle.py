"""Scope a hunt by a spec's features (`--oracle`), riskiest first, each with its spec brief."""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

import scope

MAX_FILES = 8
CRITERION = re.compile(r"\bF-[A-Z][A-Z0-9]*-[0-9]+\.AC[0-9]+\b")
STORY_LINE = re.compile(
    r"\*\*(F-[A-Z][A-Z0-9]*-[0-9]+\.AC[0-9]+)\*\*\s*(.*?)\s*(?:`\[[^\]]*\]`\s*)*$")
BACKTICKED = re.compile(r"`([^`\n]+)`")
NO_FILES = "no source files: no sdlc state or commit names its criteria"
NO_ROUTES = "its files define no HTTP routes"


class BadOracle(ValueError):
    pass


def _git(repo: str, *args: str) -> str:
    # Pinned so a user's config can't change what is parsed (quoting, renames, colour).
    result = subprocess.run(
        ["git", "-C", repo, "-c", "core.quotepath=off", "-c", "color.ui=never", *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return result.stdout if result.returncode == 0 else ""


def _section(text: str, heading: str) -> list[str]:
    """The lines under `## heading`, up to the next `## `."""
    lines, inside = [], False
    for line in text.splitlines():
        if line.startswith("## "):
            inside = line[3:].strip().casefold() == heading.casefold()
        elif inside:
            lines.append(line)
    return lines


def _linked(root: Path, path: Path) -> bool:
    """Whether `path`, or a folder between `root` and it, is a symlink (or it is outside root)."""
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return True
    # Junctions too: Windows' directory links, which islink doesn't report.
    return any(os.path.islink(p) or os.path.isjunction(p)
               for p in (root.joinpath(*parts[:i]) for i in range(1, len(parts) + 1)))


def _read(path: Path, root: Path) -> str:
    # Never through a link: the hunted repo could point one at a file outside it.
    if _linked(root, path):
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def load_lock(spec: Path) -> list[dict]:
    """The lock's criteria: {id, feature, file, level}; a bad lock is one BadOracle."""
    lock = spec / "criteria.lock.json"
    if _linked(spec, lock) or not lock.is_file():
        raise BadOracle(f"no criteria.lock.json in {spec}")
    try:
        data = json.loads(lock.read_text(encoding="utf-8"))
        criteria = data["criteria"]
        return [{"id": str(c["id"]), "feature": str(c["feature"]), "file": str(c["file"]),
                 "level": c["level"] if isinstance(c["level"], int) else 0,
                 "priority": c.get("priority")} for c in criteria]
    except (OSError, UnicodeDecodeError, ValueError, KeyError, TypeError) as exc:
        raise BadOracle(f"criteria.lock.json can't be read ({type(exc).__name__})") from None


def domain_headings(spec: Path) -> list[str]:
    return [line[3:].strip() for line in _read(spec / "domain.md", spec).splitlines()
            if line.startswith("## ") and line[3:].strip()]


def rule_citations(text: str, headings: list[str]) -> tuple[list[str], int]:
    """The headings `text` cites as `domain.md §<heading>` (domain.md order), and how many
    citations name no heading."""
    def norm(s: str) -> str:
        return re.sub(r"\s+", " ", s).casefold()

    lowered = norm(text)
    keys = {h: norm(h) for h in headings}  # casefold can change length (ß → ss)
    found, unknown = set(), 0
    for match in re.finditer(r"domain\.md §\s*", lowered):
        rest = lowered[match.end():]
        # The longest heading that ends at a word boundary: `§Roles-admin` isn't `§Roles`.
        fits = [h for h, k in keys.items() if k and rest.startswith(k)
                and not re.match(r"[\w-]", rest[len(k):len(k) + 1])]
        if fits:
            found.add(max(fits, key=lambda h: len(keys[h])))
        else:
            unknown += 1
    return [h for h in headings if h in found], unknown


def cited_rules(text: str, headings: list[str]) -> list[str]:
    return rule_citations(text, headings)[0]


def is_spec_gap(text: str) -> bool:
    """The draft is marked `Oracle: spec-gap` under its title."""
    return bool(re.search(r"^Oracle:[ \t]*spec-gap[ \t]*$", text.split("\n## ", 1)[0],
                          re.M | re.I))


def _inside(spec: Path, rel: str) -> Path | None:
    """`spec/rel` when rel is a plain relative path inside the spec; the lock is untrusted."""
    path = PurePosixPath(rel.replace("\\", "/"))
    if not path.parts or path.is_absolute() or ".." in path.parts or ":" in path.as_posix():
        return None
    return spec / path


def _operations(spec: Path) -> dict[str, list[str]]:
    try:
        paths = json.loads(_read(spec / "openapi.json", spec) or "{}").get("paths", {})
    except (ValueError, AttributeError):
        return {}
    found: dict[str, list[str]] = {}
    for item in paths.values() if isinstance(paths, dict) else []:
        for op in item.values() if isinstance(item, dict) else []:
            if isinstance(op, dict) and isinstance(op.get("operationId"), str):
                for feature in op.get("x-features") or []:
                    found.setdefault(str(feature), []).append(op["operationId"])
    return found


def _docs_dir(repo: Path) -> str:
    try:
        docs = json.loads(_read(repo / ".sdlc" / "config.json", repo) or "{}").get("docs_dir")
    except (ValueError, AttributeError):
        docs = None
    docs = _repo_path(docs).strip("/") if isinstance(docs, str) else ""
    return PurePosixPath(docs).as_posix() if docs else "docs/sdlc"


def _repo_path(name: str) -> str:
    name = name.strip().replace("\\", "/")
    while name.startswith("./"):
        name = name[2:]
    return name


def _sdlc_records(repo: Path, tracked: list[str]) -> list[dict]:
    """Each sdlc state or change file: the criteria it names, its Tasks files and change path."""
    records = []
    changes_dir = PurePosixPath(_docs_dir(repo), "changes").as_posix()
    for name in tracked:
        path = PurePosixPath(name)
        is_state = (path.parent.as_posix() == ".sdlc/state" and path.suffix == ".md") or \
            (len(path.parts) == 3 and path.parts[0] == ".sdlc" and path.name == "state.md")
        is_change = path.parent.as_posix() == changes_dir and path.suffix == ".md"
        if not (is_state or is_change):
            continue
        text = _read(repo / name, repo)
        if is_state:
            criteria = set(CRITERION.findall("\n".join(_section(text, "Criteria"))))
            files = [_repo_path(f) for f in BACKTICKED.findall("\n".join(_section(text, "Tasks")))]
            change = re.search(r"^Change:\s*(\S+)", text, re.M)
            records.append({"criteria": criteria, "files": files, "change": (
                PurePosixPath(_repo_path(change[1])).as_posix() if change else None)})
        else:
            cited = set(re.findall(r"→\s*(F-[A-Z][A-Z0-9]*-[0-9]+\.AC[0-9]+)", text))
            records.append({"criteria": cited, "files": [], "change": name})
    return records


def _commits_naming(repo: str, changes: set[str], cache: dict[str, list[str]]) -> list[str]:
    hashes = []
    for change in sorted(changes):
        if change not in cache:
            out = _git(repo, "log", "--format=%H", "--fixed-strings", f"--grep={change}")
            cache[change] = out.split()
        hashes += [h for h in cache[change] if h not in hashes]
    return hashes


def _numstat(repo: str, commits: list[str] | None, files: list[str]) -> dict[str, int]:
    """Added + deleted lines per file, over `commits` (all history when None)."""
    totals = dict.fromkeys(files, 0)
    if not files or commits == []:
        return totals
    walk = ["--no-walk", *commits] if commits else []
    out = _git(repo, "log", "--numstat", "--no-renames", "--format=", *walk, "--", *files)
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and parts[2] in totals:
            totals[parts[2]] += sum(int(n) for n in parts[:2] if n.isdigit() and len(n) < 10)
    return totals


def _files_from_commits(repo: str, commits: list[str]) -> list[str]:
    if not commits:
        return []
    out = _git(repo, "log", "--no-walk", "--no-renames", "--name-only", "--format=", *commits)
    return list(dict.fromkeys(line for line in out.splitlines() if line))


def _hunted(name: str, tracked: set[str]) -> bool:
    path = PurePosixPath(name)
    return name in tracked and path.suffix in scope.SOURCE_EXTENSIONS and not scope._is_test(path)


def build(repo: str, spec: Path, live: bool = False) -> dict:
    """The spec's features as parts; with `live`, only those whose files define routes."""
    # Normalised but unresolved, so a link is seen rather than followed: a spec folder inside
    # the repo (or a folder above it there) committed as a link would read files from outside.
    spec_abs = Path(os.path.abspath(spec))
    for repo_abs in {Path(os.path.abspath(repo)), Path(repo).resolve()}:
        if spec_abs.is_relative_to(repo_abs) and spec_abs != repo_abs \
                and _linked(repo_abs, spec_abs):
            raise BadOracle(f"{spec} is a link inside the repo; name the folder it points to")
    criteria = load_lock(spec)
    listed = scope._tracked_files(repo)
    if listed is None:
        raise BadOracle(f"not a git repo: {repo}")
    tracked_list = listed[0]
    tracked = set(tracked_list)
    root = Path(repo).resolve()
    records = _sdlc_records(root, tracked_list)
    operations = _operations(spec)
    headings = domain_headings(spec)
    try:
        spec_rel = spec.resolve().relative_to(root).as_posix()
    except ValueError:
        spec_rel = spec.resolve().as_posix()

    features: dict[str, list[dict]] = {}
    for c in criteria:
        features.setdefault(c["feature"], []).append(c)
    parts, not_hunted, cache = [], [], {}
    for feature, crits in features.items():
        ids = {c["id"] for c in crits}
        mine = [r for r in records if r["criteria"] & ids]
        changes = {r["change"] for r in mine if r["change"]}
        task_files = [f for r in mine for f in r["files"] if _hunted(f, tracked)]
        commits = _commits_naming(repo, changes, cache)
        files = list(dict.fromkeys(task_files)) or [
            f for f in _files_from_commits(repo, commits) if _hunted(f, tracked)]
        if not files:
            not_hunted.append({"feature": feature, "reason": NO_FILES})
            continue
        lines = _numstat(repo, commits if commits else None, files)
        ranked = sorted(files, key=lambda f: (-lines[f], scope._natural_key(f)))
        kept, left_out = ranked[:MAX_FILES], ranked[MAX_FILES:]
        if live and not _serves_http(root, kept):
            # A route file ranked past the kept ones takes the lowest-ranked kept file's
            # place, so the hunter has a route to hit.
            route = next((f for f in left_out if _serves_http(root, [f])), None)
            if route is None:
                not_hunted.append({"feature": feature, "reason": NO_ROUTES})
                continue
            kept, left_out = [*kept[:-1], route], [kept[-1]] + [f for f in left_out
                                                                if f != route]
        story_rel = crits[0]["file"]
        story_path = _inside(spec, story_rel)
        if story_path is not None and (_linked(spec, story_path) or not story_path.is_file()):
            story_path = None
        story_text = _read(story_path, spec) if story_path else ""
        texts = {m[1]: m[2] for line in story_text.splitlines() if (m := STORY_LINE.search(line))}
        failure_modes = [line for line in _section(story_text, "Failure modes")
                         if line.strip().startswith("- ") and line.strip()[2:].strip().casefold()
                         not in ("none", "")]
        part = {
            "feature": feature,
            "dir": str(PurePosixPath(kept[0]).parent),
            "files": kept,
            "files_left_out": left_out,
            "story": (f"{spec_rel}/{story_path.relative_to(spec).as_posix()}"
                      if story_path else None),
            "criteria": [{"id": c["id"], "level": c["level"], "text": texts.get(c["id"], "")}
                         for c in crits],
            "domain_rules": cited_rules(story_text, headings),
            "operations": operations.get(feature, []),
            "changed_lines": sum(lines[f] for f in kept),
            "failure_modes": len(failure_modes),
            "below_level_2": any(c["level"] < 2 for c in crits if c["priority"] != "Drop"),
        }
        parts.append(scope._tag(part))
    parts.sort(key=lambda p: (not p["below_level_2"], -p["changed_lines"], -p["failure_modes"],
                              scope._natural_key(p["feature"])))
    for number, part in enumerate(parts, 1):
        part["id"] = number
        if scope._calls_third_parties(root, part["files"]):
            part["edge_inputs"].append(scope.INTEGRATIONS["edge_inputs"])
    return {"parts": parts, "not_hunted": not_hunted, "installs": scope._installs(tracked_list)}


def _serves_http(root: Path, files: list[str]) -> bool:
    return scope._any_matches(root, files, scope.SERVES_HTTP, scope.SERVES_HTTP)


def _main(argv: list[str] | None = None) -> int:
    # Windows Python before 3.15 writes in the ANSI code page; the commands read UTF-8.
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors=stream.errors)
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("scope", help="the spec's features as hunt parts, riskiest first")
    s.add_argument("repo")
    s.add_argument("--oracle", required=True, type=Path, help="the folder with criteria.lock.json")
    s.add_argument("--max", type=int, dest="cap", help="at most this many hunters")
    s.add_argument("--budget", type=int, help="pre-approved tokens (worst case per hunter)")
    s.add_argument("--live", action="store_true", help="hunt a running server: add live-http")
    args = parser.parse_args(argv)
    if args.cap is not None and args.cap < 1:
        parser.error("--max must be 1 or more")
    if args.budget is not None and args.budget < scope.WORST_CASE_PER_HUNTER:
        print(f"error: --budget {args.budget} is below one hunter's worst case "
              f"({scope.WORST_CASE_PER_HUNTER} tokens), so nothing would run", file=sys.stderr)
        return 1
    try:
        out = build(args.repo, args.oracle, args.live)
    except BadOracle as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except FileNotFoundError:
        print("error: git is not installed", file=sys.stderr)
        return 1
    parts = out["parts"]
    # As scope.py --live, but only when routes were the reason: no files at all is an
    # empty plan, as without --live.
    if args.live and not parts and any(n["reason"] == NO_ROUTES for n in out["not_hunted"]):
        print("error: no feature's files define HTTP routes, so there is nothing to hunt live",
              file=sys.stderr)
        return 1
    keep = len(parts) if args.cap is None else min(args.cap, len(parts))
    if args.budget is not None:
        after_max = keep
        keep = min(keep, args.budget // scope.WORST_CASE_PER_HUNTER)
        # Only what the budget cut, as scope.py reports it; --max's cut is in `skipped` too.
        out["budget"] = {"tokens": args.budget, "per_hunter": scope.WORST_CASE_PER_HUNTER,
                         "left_out": after_max - keep}
    out["parts"], out["skipped"] = parts[:keep], parts[keep:]
    out["hunters"] = keep
    out["est_tokens"] = keep * scope.TOKENS_PER_HUNTER
    if args.live:
        for part in out["parts"]:
            part["edge_inputs"].append(scope.ROUTES["edge_inputs"])
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(_main())
