"""Split a repo's tracked source files into parts, one hunter each, with the expected cost."""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

PART_SIZE = 5
TOKENS_PER_HUNTER = 100_000
SOURCE_EXTENSIONS = {
    ".py", ".sh", ".bash", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".go", ".rs", ".rb",
    ".java", ".kt", ".php", ".cs", ".swift", ".c", ".h", ".cc", ".cpp", ".hpp", ".lua", ".pl",
}
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
        or name.endswith(("_test.py", "_test.go"))
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


def _build(files: list[str], paths: list[str], cap: int | None) -> dict:
    wanted = [PurePosixPath(f) for f in files if not paths or _under(f, paths)]
    wanted = [p for p in wanted if p.suffix in SOURCE_EXTENSIONS and not _is_test(p)]
    wanted.sort(key=lambda p: (_natural_key(str(p.parent)), _natural_key(p.name)))

    by_dir: dict[str, list[str]] = {}
    for p in wanted:
        by_dir.setdefault(str(p.parent), []).append(str(p))
    parts = []
    for directory, names in by_dir.items():
        for start in range(0, len(names), PART_SIZE):
            parts.append(
                {"id": len(parts) + 1, "dir": directory, "files": names[start : start + PART_SIZE]}
            )

    kept = parts if cap is None else parts[:cap]
    return {
        "parts": kept,
        "skipped": parts[len(kept) :],
        "hunters": len(kept),
        "est_tokens": len(kept) * TOKENS_PER_HUNTER,
    }


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo")
    parser.add_argument("paths", nargs="*", help="limit to files under these repo-relative paths")
    parser.add_argument("--max", type=int, dest="cap", help="at most this many hunters")
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
    empty = [p for p in paths or [""] if not _build(files, [p], None)["parts"]]
    if empty:
        where = ", ".join(p or "." for p in empty) if paths else args.repo
        print(f"error: no tracked source files under: {where}", file=sys.stderr)
        return 1
    out = _build(files, paths, args.cap)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(_main())
