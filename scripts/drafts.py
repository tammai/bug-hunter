"""Where a repo's drafts live, the next draft number, and the fixed draft format check."""

import argparse
import re
import subprocess
import sys
from pathlib import Path

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
    in_fence = False
    for line in lines:
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
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
    if steps and not any(line.lstrip().startswith(("```", "~~~")) for line in steps):
        found.append("## Steps to reproduce has no code block with the actual output")
    return found


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("dir", help="print the repo's drafts folder").add_argument("repo")
    sub.add_parser("next", help="print the next free draft number").add_argument("dir")
    sub.add_parser("check", help="check a draft's format").add_argument("file")
    args = parser.parse_args(argv)

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
    found = problems(text)
    for problem in found:
        print(problem)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(_main())
