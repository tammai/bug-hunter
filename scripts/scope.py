"""Split a repo's tracked source files into parts, one hunter each, with the expected cost."""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

PART_SIZE = 5
TOKENS_PER_HUNTER = 100_000
STACKS = json.loads((Path(__file__).resolve().parent / "stacks.json").read_text(encoding="utf-8"))
SOURCE_EXTENSIONS = set(STACKS["other_extensions"]).union(
    *(stack["extensions"] for stack in STACKS["stacks"])
)
TEST_SUFFIXES = tuple(suffix for stack in STACKS["stacks"] for suffix in stack["test_suffixes"])
TEST_DIRS = {"test", "tests", "__tests__", "spec", "specs"}


def _natural_key(text: str) -> list:
    # Splitting on a digit group alternates text and numbers, so positions compare like with like.
    parts = re.split(r"(\d+)", text.casefold())
    return [int(p) if i % 2 else p for i, p in enumerate(parts)]


def _is_test(path: PurePosixPath) -> bool:
    name = path.name
    return (
        any(part in TEST_DIRS for part in path.parts[:-1])
        or (name.startswith("test_") and name.endswith(".py"))
        or name.endswith(TEST_SUFFIXES)
        or ".test." in name
        or ".spec." in name
    )


def _tracked_files(repo: str) -> tuple[list[str], int] | None:
    """Tracked file names, and how many were skipped for not being UTF-8."""
    result = subprocess.run(["git", "-C", repo, "ls-files", "-z"], capture_output=True)
    if result.returncode != 0:
        return None
    names, skipped = [], 0
    for raw in result.stdout.split(b"\0"):
        try:
            name = raw.decode("utf-8")
        except UnicodeDecodeError:
            skipped += 1
            continue
        if name:
            names.append(name)
    return names, skipped


def _relative(path: str, repo: Path) -> str | None:
    """A path argument as repo-relative POSIX text ("" for the whole repo), or None if outside."""
    path = path.replace("\\", "/")
    if Path(path).is_absolute():
        try:
            path = Path(path).resolve().relative_to(repo).as_posix()
        except ValueError:
            return None
    path = path.rstrip("/")
    while path.startswith("./"):
        path = path[2:]
    return "" if path in ("", ".") else path


def _under(file: str, paths: list[str]) -> bool:
    return any(p == "" or file == p or file.startswith(p + "/") for p in paths)


def _tag(part: dict) -> dict:
    suffixes = {PurePosixPath(f).suffix for f in part["files"]}
    stacks = [s for s in STACKS["stacks"] if suffixes & set(s["extensions"])]
    part["stacks"] = [s["name"] for s in stacks]
    part["edge_inputs"] = ["generic", *(s["edge_inputs"] for s in stacks)]
    return part


def _safe_folder(folder: PurePosixPath) -> bool:
    # The folder goes into a shell step inside single quotes, so anything that could end the
    # quotes, expand, or read as an option is refused rather than escaped.
    text = str(folder)
    return text.isprintable() and not set(text) & set("'\"$`\\") and not any(
        part.startswith("-") for part in folder.parts
    )


def _installs(files: list[str], rules: list[dict] | None = None) -> list[dict]:
    """The command for each tracked lockfile outside test and fixture folders."""
    tracked = set(files)
    skip_dirs = TEST_DIRS | set(STACKS["fixture_dirs"])
    found: dict[tuple[str, str], dict] = {}
    for f in files:
        path = PurePosixPath(f)
        folder = path.parent
        if any(part in skip_dirs for part in folder.parts):
            continue
        for rule in rules if rules is not None else STACKS["installs"]:
            if path.name != rule["lockfile"]:
                continue
            marker = (folder / rule.get("when", rule.get("unless", ""))).as_posix()
            if "when" in rule and marker not in tracked:
                continue
            if "unless" in rule and marker in tracked:
                continue
            if not _safe_folder(folder):
                continue
            dir_, command = str(folder), rule["command"]
            step = command if dir_ == "." else f"(cd '{dir_}' && {command})"
            found[(dir_, command)] = {"dir": dir_, "command": command, "step": step}
    return sorted(found.values(), key=lambda i: (_natural_key(i["dir"]), i["command"]))


SECURITY = STACKS["security"]


LOCKFILES = {rule["lockfile"] for rule in STACKS["installs"] + STACKS["audits"]}


def _security_file(path: PurePosixPath) -> bool:
    """A config, schema or deployment file a security audit reads alongside the source."""
    name = path.name
    # Lockfiles are dependency lists, covered by the dependency audit, not code to read.
    if name in SECURITY["name_excludes"] or name in LOCKFILES or name.endswith(".lock"):
        return False
    return (
        path.suffix in SECURITY["extensions"]
        or name in SECURITY["names"]
        or name.startswith(tuple(SECURITY["name_prefixes"]))
        or any(part in SECURITY["folders"] for part in path.parts[:-1])
    )


def _security_rank(part: dict) -> int:
    """0 for the strongest keyword tier a part's names match; one past the last tier for none."""
    names = " ".join([part["dir"], *part["files"]]).lower()
    words = [w for w in re.split(r"[/._\- ]+", names) if w and w not in SECURITY["not_keywords"]]
    tiers = SECURITY["keywords"]
    # Tiers, not a yes/no match: nearly every web-app part matches a weak word such as
    # `config` or `model`, which would leave --max to plain folder order.
    return next((rank for rank, tier in enumerate(tiers)
                 if any(word.startswith(tuple(tier)) for word in words)), len(tiers))


TOOLING = STACKS["tooling"]


def _tooling_only(part: dict) -> bool:
    """Every file is build or docs tooling, so a hunter there finds little; --max keeps it last."""
    def tooling(path: PurePosixPath) -> bool:
        return (
            path.name in TOOLING["names"]
            or (".config" in path.suffixes and path.suffix in TOOLING["config_suffixes"])
            or any(folder in TOOLING["dirs"] for folder in path.parts[:-1])
        )
    return all(tooling(PurePosixPath(f)) for f in part["files"])


def _build(files: list[str], paths: list[str], cap: int | None, focus: bool = False) -> dict:
    wanted = [PurePosixPath(f) for f in files if not paths or _under(f, paths)]
    wanted = [
        p for p in wanted
        if (p.suffix in SOURCE_EXTENSIONS or (focus and _security_file(p))) and not _is_test(p)
        and not (focus and any(part in SECURITY["exclude_dirs"] for part in p.parts[:-1]))
    ]
    wanted.sort(key=lambda p: (_natural_key(str(p.parent)), _natural_key(p.name)))

    by_dir: dict[str, list[str]] = {}
    for p in wanted:
        by_dir.setdefault(str(p.parent), []).append(str(p))
    parts = []
    for directory, names in by_dir.items():
        for start in range(0, len(names), PART_SIZE):
            parts.append(_tag(
                {"id": len(parts) + 1, "dir": directory, "files": names[start : start + PART_SIZE]}
            ))

    # Stable sorts: within each group the folders keep their natural order.
    parts.sort(key=_security_rank if focus else _tooling_only)
    for number, part in enumerate(parts, 1):
        part["id"] = number
    kept = parts if cap is None else parts[:cap]
    return {
        "parts": kept,
        "skipped": parts[len(kept) :],
        "hunters": len(kept),
        "est_tokens": len(kept) * TOKENS_PER_HUNTER,
    }


def _depends_on(root: Path, tracked: set[str], folder: PurePosixPath, package: str) -> bool:
    """Whether the nearest tracked package.json above folder lists package as a dependency."""
    for candidate in (folder, *folder.parents):
        manifest = (candidate / "package.json").as_posix().removeprefix("./")
        if manifest not in tracked:
            continue
        try:
            data = json.loads((root / manifest).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return False
        if not isinstance(data, dict):
            return False
        return any(
            isinstance(deps, dict) and package in deps
            for deps in (data.get(k) for k in ("dependencies", "devDependencies",
                                                "peerDependencies"))
        )
    return False


INTEGRATIONS = STACKS["integrations"]
CALLS_OUT = re.compile("|".join(INTEGRATIONS["markers"]), re.M)
# A bare fetch( is only an HTTP call in JavaScript; elsewhere it's Hash#fetch, a cache method.
CALLS_OUT_JS = re.compile("|".join(INTEGRATIONS["markers"] + INTEGRATIONS["js_markers"]), re.M)


ROUTES = STACKS["routes"]
SERVES_HTTP = re.compile("|".join(ROUTES["markers"]), re.M)


def _calls_third_parties(root: Path, files: list[str]) -> bool:
    """Whether any file uses an HTTP client or a third-party SDK."""
    return _any_matches(root, files, CALLS_OUT, CALLS_OUT_JS)


def _any_matches(root: Path, files: list[str], markers: re.Pattern,
                 js_markers: re.Pattern) -> bool:
    for name in files:
        path = root / name
        try:
            if path.is_symlink() or path.stat().st_size > INTEGRATIONS["max_bytes"]:
                continue
            # A marker search, not a parse: a stray Latin-1 byte mustn't hide a client call.
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        found = js_markers if path.suffix in INTEGRATIONS["js_extensions"] else markers
        if found.search(text):
            return True
    return False


def _checklists(part: dict, root: Path, tracked: set[str]) -> list[str]:
    rule = SECURITY["checklists"]
    found = list(rule["always"])
    found += [rule["stacks"][s] for s in part["stacks"] if s in rule["stacks"]]
    vue = rule["vue"]
    if any(PurePosixPath(f).suffix in vue["extensions"] for f in part["files"]) or (
        "node" in part["stacks"]
        and _depends_on(root, tracked, PurePosixPath(part["dir"]), vue["dependency"])
    ):
        found.append("vue")
    return found


def _main(argv: list[str] | None = None) -> int:
    # Windows Python before 3.15 writes in the ANSI code page; the commands read UTF-8.
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors=stream.errors)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo")
    parser.add_argument("paths", nargs="*", help="limit to files under these repo-relative paths")
    parser.add_argument("--max", type=int, dest="cap", help="at most this many hunters")
    parser.add_argument("--focus", choices=["security"],
                        help="security audit: config and schema files too, security parts first")
    parser.add_argument("--live", action="store_true",
                        help="only parts that serve HTTP routes, for hunting a running server")
    args = parser.parse_args(argv)
    if args.cap is not None and args.cap < 1:
        parser.error("--max must be 1 or more")

    try:
        tracked = _tracked_files(args.repo)
    except FileNotFoundError:
        print("error: git is not installed", file=sys.stderr)
        return 1
    if tracked is None:
        print(f"error: not a git repo: {args.repo}", file=sys.stderr)
        return 1
    files, skipped = tracked
    if skipped:
        print(f"warning: skipped {skipped} tracked files whose names aren't UTF-8", file=sys.stderr)

    root = Path(args.repo).resolve()
    paths = [_relative(p, root) for p in args.paths]
    if None in paths:
        outside = [a for a, p in zip(args.paths, paths, strict=True) if p is None]
        print(f"error: not inside the repo: {', '.join(outside)}", file=sys.stderr)
        return 1
    focus = args.focus == "security"
    empty = [p for p in paths or [""] if not _build(files, [p], None, focus)["parts"]]
    if empty:
        where = ", ".join(p or "." for p in empty) if paths else args.repo
        print(f"error: no tracked source files under: {where}", file=sys.stderr)
        return 1
    out = _build(files, paths, None if args.live else args.cap, focus)
    if args.live:
        serving = [p for p in out["parts"] if _any_matches(root, p["files"], SERVES_HTTP,
                                                            SERVES_HTTP)]
        if not serving:
            print("error: no part defines HTTP routes, so there is nothing to hunt live",
                  file=sys.stderr)
            return 1
        for number, part in enumerate(serving, 1):
            part["id"] = number
        kept = serving if args.cap is None else serving[: args.cap]
        out = {"parts": kept, "skipped": serving[len(kept):], "hunters": len(kept),
               "est_tokens": len(kept) * TOKENS_PER_HUNTER}
    for part in out["parts"]:
        if _calls_third_parties(root, part["files"]):
            part["edge_inputs"].append(INTEGRATIONS["edge_inputs"])
        if args.live:
            part["edge_inputs"].append(ROUTES["edge_inputs"])
    if focus:
        tracked_set = set(files)
        for part in out["parts"] + out["skipped"]:
            part["checklists"] = _checklists(part, root, tracked_set)
    out["installs"] = _installs(files)
    out["audits"] = _installs(files, STACKS["audits"])
    lockfiles = {r["lockfile"] for r in STACKS["installs"] + STACKS["audits"]}
    for folder in sorted({
        PurePosixPath(f).parent for f in files
        if PurePosixPath(f).name in lockfiles and not _safe_folder(PurePosixPath(f).parent)
    }, key=str):
        print(f"warning: no install or audit for {str(folder)!r}: unsafe folder name",
              file=sys.stderr)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(_main())
