"""Where a repo's drafts live, the next draft number, and the fixed draft format check."""

import argparse
import re
import subprocess
import sys
from pathlib import Path

SECTIONS = ["What happens", "Steps to reproduce", "Expected", "Root cause"]
DRAFT_NAME = re.compile(r"^(\d+)\.md$")
ORIGIN = re.compile(r"[:/]([^/:]+)/([^/]+?)(?:\.git)?/?$")


def drafts_dir(repo: str) -> Path:
    """The repo's drafts folder, outside the repo so hunting leaves nothing in it."""
    result = subprocess.run(
        ["git", "-C", repo, "remote", "get-url", "origin"],
        capture_output=True, text=True, encoding="utf-8",
    )
    match = ORIGIN.search(result.stdout.strip()) if result.returncode == 0 else None
    name = f"{match[1]}-{match[2]}" if match else Path(repo).resolve().name
    return Path.home() / ".bug-hunter" / name / "drafts"


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
            return line[2:].strip() if line.startswith("# ") else None
    return None


def problems(text: str) -> list[str]:
    """Every way a draft breaks the fixed format; empty when it's good."""
    lines = text.splitlines()
    found = []
    first = next((line for line in lines if line.strip()), "")
    if not first.startswith("# "):
        found.append("missing a '# ' title line")

    bodies: dict[str, list[str]] = {}
    current = None
    for line in lines:
        if line.startswith("## "):
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
        print(drafts_dir(args.repo))
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
