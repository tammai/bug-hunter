"""Append one agent run to a contracts C7 run log (cost.jsonl)."""

import argparse
import importlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "contracts" / "v1"))
contracts = importlib.import_module("contracts")  # vendored: importable only after the insert


def line(args: argparse.Namespace) -> str:
    tokens = None if args.tokens_total.lower() == "none" else args.tokens_total
    if tokens is not None and not (tokens.isascii() and tokens.isdigit() and len(tokens) <= 15):
        raise ValueError("--tokens-total must be a whole number of tokens or 'none'")
    row = {
        "ts": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "plugin": "bug-hunter",
        "stage": args.stage,
        "agent": args.agent,
        "tier": args.tier,
        "wall_s": args.wall_s,
        "turns": args.turns,
        # The host reports one total, not an input/output split; C7 wants null for what it lacks.
        "tokens_in": None,
        "tokens_out": None,
        "tokens_total": None if tokens is None else int(tokens),
        "result": args.result,
    }
    text = json.dumps(row, ensure_ascii=False)
    problems = [m for s, m in contracts.check_cost(text) if s != "warning"]
    if problems:
        raise ValueError(problems[0])
    return text + "\n"


def _main(argv: list[str] | None = None) -> int:
    # Windows Python before 3.15 writes in the ANSI code page; the commands read UTF-8.
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors=stream.errors)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True, type=Path)
    parser.add_argument("--stage", required=True, choices=["hunt", "verify"])
    parser.add_argument("--agent", required=True)
    parser.add_argument("--tier", required=True, help="the model the agent ran on, or 'session'")
    parser.add_argument("--wall-s", required=True)
    parser.add_argument("--turns", required=True)
    parser.add_argument("--tokens-total", required=True, help="total tokens reported, or 'none'")
    parser.add_argument("--result", required=True)
    args = parser.parse_args(argv)
    try:
        args.wall_s = float(args.wall_s)
        if args.wall_s != args.wall_s or args.wall_s in (float("inf"), float("-inf")):
            raise ValueError("--wall-s must be a finite number of seconds")
        if not (args.turns.isascii() and args.turns.isdigit() and len(args.turns) <= 9):
            raise ValueError("--turns must be a whole number")
        args.turns = int(args.turns)
        text = line(args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    try:
        with args.file.open("ab+") as f:
            if f.seek(0, 2):
                f.seek(-1, 2)
                if f.read(1) != b"\n":
                    text = "\n" + text
            f.write(text.encode("utf-8"))
    except OSError as exc:
        print(f"error: cannot append to the run log: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(_main())
