"""Split a repo's tracked source files into parts, one hunter each, with the expected cost."""

import argparse
import json
import os
import re
import sys
from pathlib import Path, PurePosixPath

import browser
from secrets_scan import run_git

PART_SIZE = 5
TOKENS_PER_HUNTER = 100_000
# A hunter returns at most 5 drafts, each re-run by one ~20k-token verifier.
WORST_CASE_PER_HUNTER = TOKENS_PER_HUNTER + 5 * 20_000
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
    result = run_git(repo, "ls-files", "-z")
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
            found[(dir_, command)] = {"dir": dir_, "lockfile": path.as_posix(),
                                      "command": command, "step": step}
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
WEB_UI = STACKS["web_ui"]


def _has_ui(part: dict, tracked: list[str]) -> bool:
    """Whether a part holds UI files (components, templates) a browser hunt can reach."""
    # Templates aren't source files, so they're never in a part's files: a server-rendered
    # app's templates sit beside or under the part's folder instead.
    folder = PurePosixPath(part["dir"])
    near = (f for f in tracked if folder == PurePosixPath(".")
            or PurePosixPath(f).is_relative_to(folder))
    return any(PurePosixPath(f).suffix in WEB_UI["extensions"]
               for f in (*part["files"], *near))


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


CHECKLIST_DIR = Path(__file__).resolve().parent.parent / "security"


def _checklists(part: dict, root: Path, tracked: set[str]) -> tuple[list[str], list[str]]:
    """The checklists a part gets, and its detected stacks and frameworks that have none."""
    rule = SECURITY["checklists"]
    wanted = list(part["stacks"])
    for framework in rule["frameworks"]:
        if any(PurePosixPath(f).suffix in framework["extensions"] for f in part["files"]) or (
            "node" in part["stacks"] and _depends_on(
                root, tracked, PurePosixPath(part["dir"]), framework["dependency"])
        ):
            wanted.append(framework["name"])
    found, missing = list(rule["always"]), []
    for name in dict.fromkeys(wanted):
        (found if (CHECKLIST_DIR / f"{name}.md").is_file() else missing).append(name)
    return found, missing


def _git_out(repo: str, *args: str, config: dict[str, str] | None = None) -> bytes | None:
    """A git command's output, or None when it fails or git is missing."""
    try:
        result = run_git(repo, *args, config=config)
    except OSError:
        return None
    return result.stdout if result.returncode == 0 else None


def _blank_filters(repo: str) -> dict[str, str] | None:
    """Config that turns off every filter driver the target's own config defines; None if unread."""
    try:
        # Reading config runs nothing; includes are followed, and an include keeps its scope.
        result = run_git(repo, "config", "--show-scope", "-z", "--name-only", "--get-regexp",
                         r"^filter\.")
    except OSError:
        return None
    if result.returncode not in (0, 1):
        return None
    fields = result.stdout.split(b"\0")
    blank = {}
    for scope, key in zip(fields[::2], fields[1::2], strict=False):
        # The owner's own drivers (git-lfs in ~/.gitconfig) are trusted; the repo's aren't.
        if scope in (b"local", b"worktree") and key.count(b".") >= 2:
            driver = key.decode("utf-8", "surrogateescape")[len("filter."):].rsplit(".", 1)[0]
            for command in ("clean", "smudge", "process"):
                blank[f"filter.{driver}.{command}"] = ""
    return blank


def _coverage(repo: str, files: list[str], paths: list[str], parts: list[dict],
              unsafe: list[str]) -> dict:
    """What a security audit of this scope can't vouch for, beyond its parts."""
    skip_dirs = TEST_DIRS | set(STACKS["fixture_dirs"])
    in_scope = [f for f in files if (not paths or _under(f, paths))
                and not any(p in skip_dirs for p in PurePosixPath(f).parent.parts)]
    tracked = set(files)
    other: dict[str, int] = {}
    for part in parts:
        for name in part["files"]:
            suffix = PurePosixPath(name).suffix
            if suffix in STACKS["other_extensions"]:
                other[suffix] = other.get(suffix, 0) + 1
    manifests = []
    for name in in_scope:
        path = PurePosixPath(name)
        locks = STACKS["manifests"].get(path.name)
        # A workspace member's lockfile sits in a folder above it.
        if locks is not None and not any(
            (folder / lock).as_posix() in tracked
            for folder in (path.parent, *path.parent.parents) for lock in locks
        ):
            manifests.append(name)
    audited = {a["lockfile"] for a in _installs(files, STACKS["audits"])}
    commit = _git_out(repo, "rev-parse", "--verify", "-q", "HEAD^{commit}")
    # Status re-hashes changed files through their clean filter, a program the target's config
    # can name: blanked, a filtered file reads dirty or a required one fails, both a gap.
    blank = _blank_filters(repo)
    status = None if blank is None else _git_out(
        repo, "status", "--porcelain=v1", "-z", "--untracked-files=normal",
        "--ignore-submodules=none", config=blank)
    return {
        "paths": paths,
        "commit": commit.decode("ascii", "replace").strip() or None if commit else None,
        "dirty": None if status is None else bool(status),
        "unsafe_folders": unsafe,
        "other_files": dict(sorted(other.items())),
        "manifests_without_lockfile": manifests,
        "unaudited_lockfiles": sorted(
            (f for f in in_scope if PurePosixPath(f).name in STACKS["dependency_lockfiles"]
             and f not in audited), key=_natural_key),
    }


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
    parser.add_argument("--budget", type=int,
                        help="pre-approved tokens: start hunters only while their worst case fits")
    parser.add_argument("--browser", action="store_true",
                        help="with --live: also hunt UI parts in a browser, if Playwright is here")
    args = parser.parse_args(argv)
    if args.browser and not args.live:
        parser.error("--browser needs --live: a browser hunt reaches a running server")
    if args.cap is not None and args.cap < 1:
        parser.error("--max must be 1 or more")
    if args.budget is not None and args.budget < WORST_CASE_PER_HUNTER:
        print(f"error: --budget {args.budget} is below one hunter's worst case "
              f"({WORST_CASE_PER_HUNTER} tokens), so nothing would run", file=sys.stderr)
        return 1

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
    browser_info = None
    if args.live:
        serving = [p for p in out["parts"] if _any_matches(root, p["files"], SERVES_HTTP,
                                                            SERVES_HTTP)]
        if args.browser:
            browser_info = browser.detect(args.repo, dict(os.environ))
            installed = {i["dir"] for i in _installs(files)}
            if browser_info["available"] and browser_info["dir"] not in installed:
                browser_info = {**browser_info, "available": False, "reason": (
                    f"{browser_info['dir']} gets no locked install (test and fixture folders "
                    "get none), so a copy can't install Playwright there")}
            if browser_info["available"]:
                # UI parts are hunted in the browser beside the route parts, in scope order.
                serving = [p for p in out["parts"] if p in serving or _has_ui(p, files)]
        if not serving:
            print("error: no part defines HTTP routes, so there is nothing to hunt live",
                  file=sys.stderr)
            return 1
        for number, part in enumerate(serving, 1):
            part["id"] = number
        kept = serving if args.cap is None else serving[: args.cap]
        out = {"parts": kept, "skipped": serving[len(kept):], "hunters": len(kept),
               "est_tokens": len(kept) * TOKENS_PER_HUNTER}
    if args.budget is not None:
        fits = args.budget // WORST_CASE_PER_HUNTER
        kept, left_out = out["parts"][:fits], out["parts"][fits:]
        out = {"parts": kept, "skipped": left_out + out["skipped"], "hunters": len(kept),
               "est_tokens": len(kept) * TOKENS_PER_HUNTER,
               "budget": {"tokens": args.budget, "per_hunter": WORST_CASE_PER_HUNTER,
                          "left_out": len(left_out)}}
    for part in out["parts"]:
        if _calls_third_parties(root, part["files"]):
            part["edge_inputs"].append(INTEGRATIONS["edge_inputs"])
        if args.live:
            part["edge_inputs"].append(ROUTES["edge_inputs"])
        if browser_info and browser_info["available"] and _has_ui(part, files):
            part["edge_inputs"].append(WEB_UI["edge_inputs"])
    if browser_info is not None:
        out["browser"] = browser_info
    if focus:
        tracked_set = set(files)
        for part in out["parts"] + out["skipped"]:
            part["checklists"], part["no_checklist"] = _checklists(part, root, tracked_set)
    # Only an audit names its lockfile: the report checks each one was audited.
    out["installs"] = [{k: v for k, v in i.items() if k != "lockfile"} for i in _installs(files)]
    out["audits"] = _installs(files, STACKS["audits"])
    lockfiles = {r["lockfile"] for r in STACKS["installs"] + STACKS["audits"]}
    unsafe = sorted({
        str(PurePosixPath(f).parent) for f in files
        if PurePosixPath(f).name in lockfiles and not _safe_folder(PurePosixPath(f).parent)
    })
    for folder in unsafe:
        print(f"warning: no install or audit for {folder!r}: unsafe folder name",
              file=sys.stderr)
    if focus:
        out["coverage"] = _coverage(args.repo, files, paths, out["parts"], unsafe)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(_main())
