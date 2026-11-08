"""Render a finding-v1 draft's Steps from its JSON, and write it as a contracts C6 file."""

import argparse
import importlib
import json
import re
import sys
from pathlib import Path

from drafts import fenced

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "contracts" / "v1"))
contracts = importlib.import_module("contracts")  # vendored: importable only after the insert

# Case-insensitive: on Windows and macOS `bh-0001.json` takes the name `BH-0001.json`.
FINDING_NAME = re.compile(r"^BH-(\d+)\.json$", re.I)
MAX_NUMBER = 999_999_999
SEVERITY = re.compile(r"^Severity:[ \t]*(\S+)[ \t]*$", re.M | re.I)
ENV_NAME = re.compile(r"`([A-Z][A-Z0-9_]*)`")
LEADING_BACKTICKS = re.compile(r" {0,3}(`+)")
STEPS_HEADING = "## Steps to reproduce"
WHERE = "## Repro (finding-v1)"


class BadDraft(ValueError):
    pass


def _sections(text: str) -> dict[str, str]:
    bodies: dict[str, list[str]] = {}
    current = None
    for line, in_fence in fenced(text.splitlines()):
        if line.startswith("## ") and not in_fence:
            current = line[3:].strip().rstrip(":").casefold()
            bodies.setdefault(current, [])
        elif current is not None:
            bodies[current].append(line)
    return {name: "\n".join(lines).strip() for name, lines in bodies.items()}


def repro_steps(sections: dict[str, str]) -> list[dict]:
    """The hunter's JSON steps: the source of the repro and of the draft's visible Steps."""
    if WHERE[3:].casefold() not in sections:
        raise BadDraft(f"missing {WHERE} (a fenced JSON list of steps)")
    inner = [line for line, in_fence in fenced(sections[WHERE[3:].casefold()].splitlines())
             if in_fence]
    try:
        steps = json.loads("\n".join(inner[1:-1])) if len(inner) >= 2 else None
    except ValueError:
        steps = None
    if not isinstance(steps, list) or not steps:
        raise BadDraft(f"{WHERE} is not one fenced JSON list of steps")
    for n, step in enumerate(steps, 1):
        if (not isinstance(step, dict) or set(step) != {"command", "stdout"}
                or not all(isinstance(v, str) for v in step.values())
                or not step["command"].split("\n")[0].strip()):
            raise BadDraft(f"{WHERE} step {n} is not {{\"command\": <text>, \"stdout\": <text>}} "
                           "with a command on its first line")
        if step["command"].startswith("$ "):
            raise BadDraft(f"{WHERE} step {n}: its command starts with a `$ ` prompt")
    return steps


def _steps_block(steps: list[dict]) -> list[str]:
    body = []
    for step in steps:
        command = step["command"].split("\n")
        body += ["$ " + command[0], *command[1:]]
        if step["stdout"]:
            body += step["stdout"].removesuffix("\n").split("\n")
    # Longer than any backtick run that opens a line of output, so the output can't close it.
    # splitlines: a lone `\r` in output becomes a line break when the draft is read back.
    longest = max((len(m[1]) for line in body for piece in line.splitlines()
                   if (m := LEADING_BACKTICKS.match(piece))), default=0)
    fence = "`" * max(3, longest + 1)
    return [STEPS_HEADING, fence, *body, fence, ""]


def render(text: str) -> str:
    """The draft with its Steps section replaced by one block written from its JSON steps."""
    block = _steps_block(repro_steps(_sections(text)))
    lines = text.split("\n")
    headings = [i for i, (line, in_fence) in enumerate(fenced(lines))
                if line.startswith("## ") and not in_fence]
    names = {i: lines[i][3:].strip().rstrip(":").casefold() for i in headings}
    steps_at = [i for i in headings if names[i] == STEPS_HEADING[3:].casefold()]
    if len(steps_at) > 1:
        raise BadDraft(f"more than one {STEPS_HEADING}; the Repro section is the only repro")
    start = steps_at[0] if steps_at else None
    if start is None:
        start = end = next(i for i in headings if names[i] == WHERE[3:].casefold())
    else:
        end = next((i for i in headings if i > start), len(lines))
    return "\n".join(lines[:start] + block + lines[end:])


def finding(text: str) -> dict:
    """The finding for a draft, numbered BH-0001 until `write` gives it its number."""
    title = next((line for line in text.splitlines() if line.strip()), "")
    if not title.startswith("# ") or not title[2:].strip():
        raise BadDraft("missing a '# ' title line")
    header = text.split("\n## ", 1)[0]  # the lines under the title, before the first section
    severity = SEVERITY.search(header)
    if not severity or severity[1].lower() not in ("high", "medium", "low"):
        raise BadDraft("missing a 'Severity: high|medium|low' line under the title")
    sections = _sections(text)
    if not sections.get("what happens"):
        raise BadDraft("missing ## What happens")
    repro = {"runner": "cli", "steps": repro_steps(sections)}
    setup = next((line for line in header.splitlines()
                  if line.strip().lower().startswith("set before running:")), None)
    if setup:
        repro["env"] = ENV_NAME.findall(setup)
    return {
        "id": "BH-0001",
        "source": "bug-hunter",
        "class": "build-defect",
        "severity": severity[1].lower(),
        "criterion": None,
        "rule": None,
        "repro": repro,
        "observed": {"rebuild": sections["what happens"], "reference": "not run: no --reference"},
        "route": "sdlc",
        "verified_by": {"agent": "repro-verifier", "result": "reproduced"},
        "title": title[2:].strip(),
        "draft": render(text),
    }


def _next_number(out: Path) -> int:
    # Compared by value; one too long to be ours counts as "full", so its name is never retried.
    digits = [m[1].lstrip("0") or "0" for p in out.iterdir() if (m := FINDING_NAME.match(p.name))]
    numbers = [int(d) if len(d) <= len(str(MAX_NUMBER)) else MAX_NUMBER + 1 for d in digits]
    number = max(numbers, default=0) + 1
    if number > MAX_NUMBER:
        raise BadDraft(f"--out already holds BH-{MAX_NUMBER}; use a new folder")
    return number


def write(repo: str, out: Path, draft: Path) -> Path:
    if out.resolve().is_relative_to(Path(repo).resolve()):
        raise BadDraft("--out is inside the repo; findings are written outside it")
    record = finding(draft.read_text(encoding="utf-8"))
    problems = [m for s, m in contracts.check_finding(record) if s != "warning"]
    if problems:
        raise BadDraft(f"not a valid finding-v1: {problems[0]}")
    out.mkdir(parents=True, exist_ok=True)
    record["id"] = f"BH-{_next_number(out):04d}"
    path = out / f"{record['id']}.json"
    try:
        with path.open("x", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
            f.write("\n")
    except FileExistsError:
        raise BadDraft(f"{path.name} already exists in --out; nothing was overwritten") from None
    return path


def _main(argv: list[str] | None = None) -> int:
    # Windows Python before 3.15 writes in the ANSI code page; the commands read UTF-8.
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors=stream.errors)
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    r = sub.add_parser("render", help="rewrite a draft's Steps from its Repro JSON, in place")
    r.add_argument("--draft", required=True, type=Path)
    w = sub.add_parser("write", help="write one verified draft as the next BH-NNNN.json")
    w.add_argument("--repo", required=True, help="the hunted repo; --out must be outside it")
    w.add_argument("--out", required=True, type=Path)
    w.add_argument("--draft", required=True, type=Path, help="a draft its verifier reproduced")
    args = parser.parse_args(argv)
    try:
        if args.command == "render":
            # The same checks as write, so a draft write would refuse never reaches a verifier.
            text = finding(args.draft.read_text(encoding="utf-8"))["draft"]
            args.draft.write_text(text, encoding="utf-8", newline="")
        else:
            print(write(args.repo, args.out, args.draft))
    except BadDraft as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except (OSError, UnicodeDecodeError) as exc:
        print(f"error: cannot {args.command} the draft: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(_main())
