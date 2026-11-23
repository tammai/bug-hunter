"""Scope a hunt by a spec's features (`--oracle`), riskiest first, each with its spec brief."""

import argparse
import importlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

import scope
from drafts import fenced

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "contracts" / "v1"))
contracts = importlib.import_module("contracts")  # vendored: importable only after the insert

MAX_FILES = 8
# C1: a spec-backed `F-<feature>.AC<n>`, or a standalone `AC-<nnn>` not inside a longer ID.
ID = r"(?:F-[A-Z][A-Z0-9]*-[0-9]+\.AC[0-9]+|(?<![\w.-])AC-[0-9]{3,})"
CRITERION = re.compile(rf"\b{ID}\b")
ARROW = re.compile(rf"→\s*({ID})\b")
TAGS = re.compile(r"(?:\s*`\[[^\]`]*\]`)+\s*$")
BACKTICKED = re.compile(r"`([^`\n]+)`")
# The forms sdlc names a change file in its commits: `Record: <change>`, or `… (<change>)`.
RECORD = re.compile(r"^Record: (\S+?)(?: in the workbench \(.*\))?[ \t]*$", re.M)
SUBJECT = re.compile(r"\(([^()\s]+)\)[ \t]*$")
HASH = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?")
NO_FILES = "no source files: no sdlc state or commit names its criteria"
NO_ROUTES = "its files define no HTTP routes"


class BadOracle(ValueError):
    pass


def _git(repo: str, *args: str, stdin: str | None = None) -> str:
    # Pinned so a user's config can't change what is parsed (quoting, renames, colour,
    # signatures, rename following).
    try:
        result = subprocess.run(
            ["git", "-C", repo, "-c", "core.quotepath=off", "-c", "color.ui=never",
             "-c", "log.showSignature=false", "-c", "log.follow=false", *args],
            input=stdin, capture_output=True, text=True, encoding="utf-8", errors="replace",
            env={**os.environ, "LC_ALL": "C"},  # untranslated, so the unborn case is known
        )
    except FileNotFoundError:
        raise
    except OSError as exc:
        raise BadOracle(f"git can't be run ({exc.strerror or type(exc).__name__})") from None
    if result.returncode != 0:
        # Staged files and no commit yet is an empty history, not a failure.
        if args[0] == "log" and "does not have any commits yet" in result.stderr:
            return ""
        # Any other empty answer would read as "no history": refuse rather than rank on nothing.
        lines = result.stderr.strip().splitlines()
        why = next((line for line in lines if line.startswith(("fatal:", "error:"))),
                   lines[0] if lines else "no message")
        raise BadOracle(f"git {args[0]} failed: {why}")
    return result.stdout


def _section(text: str, heading: str) -> list[str]:
    """The lines under `## heading`, up to the next `## `."""
    lines, inside = [], False
    for line, in_fence in fenced(text.splitlines()):
        if line.startswith("## ") and not in_fence:
            inside = line[3:].strip().casefold() == heading.casefold()
        elif inside:
            lines.append(line)
    return lines


_linked = scope._linked


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
                 "text_sha256": c.get("text_sha256"),
                 "priority": c.get("priority")} for c in criteria]
    except (OSError, UnicodeDecodeError, ValueError, KeyError, TypeError,
            RecursionError) as exc:
        raise BadOracle(f"criteria.lock.json can't be read ({type(exc).__name__})") from None


def domain_headings(spec: Path) -> list[str]:
    lines = fenced(_read(spec / "domain.md", spec).splitlines())
    return [line[3:].strip() for line, in_fence in lines
            if not in_fence and line.startswith("## ") and line[3:].strip()]


def rule_citations(text: str, headings: list[str]) -> tuple[list[str], int]:
    """The headings `text` cites as `domain.md §<heading>` (domain.md order), and how many
    citations name no heading."""
    def norm(s: str) -> str:
        return re.sub(r"\s+", " ", s).casefold()

    lowered = norm(text)
    keys = {h: norm(h) for h in headings}  # casefold can change length (ß → ss)
    found, unknown = set(), 0
    # Between the file name and § only markup and punctuation: `domain.md`, **domain.md**,
    # `domain.md: §`, `domain.md (§`, `domain.md — §`.
    # Not the end of another name (`docs/domain.md`, `mydomain.md`); `_` may be markup.
    for match in re.finditer(r"(?<![^\W_])(?<![./-])domain\.md[`*_\s,:(\-–—]*§\s*", lowered):
        rest = lowered[match.end():]
        # The longest heading that ends at a word boundary: `§Roles-admin` isn't `§Roles`.
        fits = [h for h, k in keys.items() if k and rest.startswith(k)
                and not re.match(r"[\w-]", rest[len(k):len(k) + 1])]
        if fits:
            found.add(max(fits, key=lambda h: len(keys[h])))
        else:
            unknown += 1
    return [h for h in headings if h in found], unknown


def is_spec_gap(text: str) -> bool:
    """The draft is marked `Oracle: spec-gap` under its title (bold or backticked too)."""
    return bool(re.search(r"^[ \t*_`]*Oracle:[ \t*_`]*spec-gap[ \t*_`]*$",
                          text.split("\n## ", 1)[0], re.M | re.I))


def _removed(line: str) -> bool:
    crit = contracts.CRIT_LINE.match(line.rstrip("\r"))
    return bool(crit) and crit["body"].startswith("~~")


def _story(text: str) -> tuple[dict[str, str], dict[str, str], str]:
    """Criteria texts and hashes as the lock's producer reads them; the story minus removed ones."""
    texts, hashes = {}, {}
    for _, line in contracts._section(text, "Acceptance criteria"):
        crit = contracts.CRIT_LINE.match(line)
        active = contracts.ACTIVE.match(crit["body"]) if crit and not _removed(line) else None
        if active and active["id"].strip() not in texts:
            texts[active["id"].strip()] = TAGS.sub("", active["rest"]).strip()
            hashes[active["id"].strip()] = contracts.criterion_text_sha256(line)
    return texts, hashes, "\n".join(line for line in text.split("\n") if not _removed(line))


def _load_story(spec: Path, rel: str) -> tuple[Path | None, tuple[dict, dict, str]]:
    path = _inside(spec, rel)
    if path is not None and (_linked(spec, path) or not path.is_file()):
        path = None
    return path, _story(_read(path, spec) if path else "")


def _inside(spec: Path, rel: str) -> Path | None:
    """`spec/rel` when rel is a plain relative path inside the spec; the lock is untrusted."""
    path = PurePosixPath(rel.replace("\\", "/"))
    if not path.parts or path.is_absolute() or ".." in path.parts or ":" in path.as_posix():
        return None
    return spec / path


def _operations(spec: Path) -> dict[str, list[str]]:
    try:
        paths = json.loads(_read(spec / "openapi.json", spec) or "{}").get("paths", {})
    except (ValueError, AttributeError, RecursionError):
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
    except (ValueError, AttributeError, RecursionError):
        docs = None
    docs = _repo_path(docs).strip("/") if isinstance(docs, str) else ""
    return PurePosixPath(docs).as_posix() if docs else "docs/sdlc"


def _repo_path(name: str) -> str:
    # Text only, unlike scope._relative: a path the hunted repo wrote is never resolved.
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
            cited = set(ARROW.findall("\n".join(_section(text, "Acceptance criteria"))))
            records.append({"criteria": cited, "files": [], "change": name})
    return records


def _commits_by_change(repo: str) -> dict[str, list[str]]:
    """The commits naming each change file the way sdlc does, newest first."""
    fields = _git(repo, "log", "-z", "--format=%H%x00%B").split("\0")
    named: dict[str, list[str]] = {}
    for commit, message in zip(fields[0::2], fields[1::2], strict=False):
        commit = commit.strip()
        if not HASH.fullmatch(commit):
            continue
        names = set(RECORD.findall(message))
        if subject := SUBJECT.search(message.split("\n", 1)[0]):
            names.add(subject[1])
        for name in names:
            named.setdefault(name, []).append(commit)
    return named


def _numstat(repo: str, *args: str, stdin: str | None = None,
             keep: set[str] | None = None) -> dict[str, dict[str, int]]:
    """Added + deleted lines per file (only `keep`'s, when given), per commit."""
    out = _git(repo, "log", "-z", "--numstat", "--no-renames", "--format=%x01%H", *args,
               stdin=stdin)
    per: dict[str, dict[str, int]] = {}
    lines: dict[str, int] = {}
    for chunk in out.split("\0"):
        chunk = chunk.lstrip("\n")
        if chunk.startswith("\x01"):
            header = chunk[1:].strip()
            lines = per.setdefault(header, {}) if HASH.fullmatch(header) else {}
            continue
        fields = chunk.split("\t", 2)
        if len(fields) == 3 and (keep is None or fields[2] in keep):
            lines[fields[2]] = lines.get(fields[2], 0) + sum(
                int(n) for n in fields[:2] if n.isascii() and n.isdigit() and len(n) < 10)
    return per


def _hunted(name: str, tracked: set[str]) -> bool:
    path = PurePosixPath(name)
    return name in tracked and path.suffix in scope.SOURCE_EXTENSIONS and not scope._is_test(path)


def build(repo: str, spec: Path, live: bool = False) -> dict:
    """The spec's features as parts; with `live`, only those whose files define routes."""
    # Normalised but unresolved, so a link is seen rather than followed: a spec folder inside
    # the repo (or a folder above it there) committed as a link would read files from outside.
    # Each link's parent is resolved, not compared as text, so a path spelled another way (an
    # 8.3 short name, a link above the repo) can't make it look outside the repo.
    repo_real = Path(repo).resolve()
    spec_abs = Path(os.path.abspath(spec))
    for folder in (*reversed(spec_abs.parents), spec_abs):
        if (os.path.islink(folder) or os.path.isjunction(folder)) \
                and folder.parent.resolve().is_relative_to(repo_real):
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
    named = _commits_by_change(repo)
    plans = {}
    for feature, crits in features.items():
        ids = {c["id"] for c in crits}
        mine = [r for r in records if r["criteria"] & ids]
        changes = sorted({r["change"] for r in mine if r["change"]})
        commits = list(dict.fromkeys(h for c in changes for h in named.get(c, [])))
        plans[feature] = (commits, list(dict.fromkeys(
            f for r in mine for f in r["files"] if _hunted(f, tracked))))
    # One walk over every feature's commits (a merge as its first-parent diff), and one over
    # all history for the files of features no commit names (merges left out: counted once;
    # no pathspec, so no file list on the command line).
    walked = sorted({h for commits, _ in plans.values() for h in commits})
    by_commit = _numstat(repo, "--no-walk", "-m", "--first-parent", "--stdin",
                         stdin="\n".join(walked) + "\n") if walked else {}
    unnamed = {f for commits, files in plans.values() if not commits for f in files}
    history = _numstat(repo, keep=unnamed) if unnamed else {}
    stories: dict[str, tuple] = {}

    parts, not_hunted = [], []
    for feature, crits in features.items():
        commits, task_files = plans[feature]
        files = task_files or [f for f in dict.fromkeys(
            f for h in commits for f in by_commit.get(h, {})) if _hunted(f, tracked)]
        if not files:
            not_hunted.append({"feature": feature, "reason": NO_FILES})
            continue
        counted = [by_commit.get(h, {}) for h in commits] if commits else list(history.values())
        lines = {f: sum(c.get(f, 0) for c in counted) for f in files}
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
        for c in crits:
            if c["file"] not in stories:
                stories[c["file"]] = _load_story(spec, c["file"])
        story_path, (_, _, story_text) = stories[crits[0]["file"]]
        texts = {c["id"]: stories[c["file"]][1][0].get(c["id"], "") for c in crits}
        hashes = {c["id"]: stories[c["file"]][1][1].get(c["id"]) for c in crits}
        # C3: a criterion whose line changed since the lock (or can't be read) is at level 0.
        level = {c["id"]: c["level"] if hashes[c["id"]] is not None
                 and hashes[c["id"]] == c["text_sha256"] else 0 for c in crits}
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
            "criteria": [{"id": c["id"], "level": level[c["id"]], "text": texts[c["id"]]}
                         for c in crits],
            "domain_rules": rule_citations(story_text, headings)[0],
            "operations": operations.get(feature, []),
            "changed_lines": sum(lines[f] for f in kept),
            "failure_modes": len(failure_modes),
            "below_level_2": any(level[c["id"]] < 2 for c in crits
                                 if c["priority"] != "Drop"),
        }
        parts.append(scope._tag(part))
    parts.sort(key=lambda p: (not p["below_level_2"], -p["changed_lines"], -p["failure_modes"],
                              scope._natural_key(p["feature"])))
    for number, part in enumerate(parts, 1):
        part["id"] = number
    warnings = [f"skipped {listed[1]} tracked files whose names aren't UTF-8"] if listed[1] else []
    warnings += [f"no install or audit for {folder!r}: unsafe folder name" for folder in sorted({
        str(PurePosixPath(f).parent) for f in tracked_list
        if PurePosixPath(f).name in scope.LOCKFILES
        and not scope._safe_folder(PurePosixPath(f).parent)
    })]
    return {"parts": parts, "not_hunted": not_hunted, "installs": scope._installs(tracked_list),
            "warnings": warnings}


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
    except OSError as exc:
        print(f"error: git can't be run ({exc.strerror or type(exc).__name__})", file=sys.stderr)
        return 1
    for warning in out.pop("warnings"):
        print(f"warning: {warning}", file=sys.stderr)
    parts = out["parts"]
    if not parts:
        # As scope.py: nothing to hunt is an error, named by why.
        if any(n["reason"] == NO_ROUTES for n in out["not_hunted"]):
            print("error: no feature's files define HTTP routes, so there is nothing to hunt "
                  "live", file=sys.stderr)
        else:
            print("error: no feature has source files: no sdlc state or commit names its "
                  "criteria", file=sys.stderr)
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
    root = Path(args.repo).resolve()
    for part in out["parts"]:
        if scope._calls_third_parties(root, part["files"]):
            part["edge_inputs"].append(scope.INTEGRATIONS["edge_inputs"])
        if args.live:
            part["edge_inputs"].append(scope.ROUTES["edge_inputs"])
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(_main())
